"""Surveille les dossards du 10 KM DE BLAGNAC (07/03/2027) sur Chrono-Start et alerte sur WhatsApp."""
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

DETAIL_URL = "https://chrono-start.fr/Inscription/Course/detail/c/5162"
BOURSE_URL = "https://chrono-start.fr/Inscription/Course/bourse/c/5162"
RACE = "10 KM DE BLAGNAC"
STATE_FILE = Path(__file__).with_name("state.json")
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
# Un en-tête d'épreuve ("21 KM DE BLAGNAC  29€ *", "MARCHE 6 KM") ou le pied de page clôt le bloc courant.
BLOCK_END = re.compile(r"^(\d+ KM\b|MARCHE\b|Conditions g)", re.IGNORECASE)
FAILURE_ALERT_AT = 12  # ~1 h d'échecs consécutifs avec un cron de 5 min


def send_whatsapp(message: str) -> bool:
    """Envoie `message` sur WhatsApp. Renvoie True si l'envoi a réussi.

    - WHATSAPP_WEBHOOK_URL défini : POST JSON {"message": ...} vers ce webhook (votre propre endpoint).
    - Sinon CallMeBot avec WHATSAPP_PHONE et CALLMEBOT_APIKEY.
    """
    webhook = os.environ.get("WHATSAPP_WEBHOOK_URL")
    if webhook:
        req = urllib.request.Request(
            webhook,
            data=json.dumps({"message": message}).encode(),
            headers={"Content-Type": "application/json"},
        )
    else:
        phone, apikey = os.environ.get("WHATSAPP_PHONE"), os.environ.get("CALLMEBOT_APIKEY")
        if not (phone and apikey):
            print("WhatsApp non configuré (WHATSAPP_PHONE / CALLMEBOT_APIKEY absents). Message :\n" + message)
            return False
        query = urllib.parse.urlencode({"phone": phone, "text": message, "apikey": apikey})
        req = urllib.request.Request(f"https://api.callmebot.com/whatsapp.php?{query}")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            print(f"WhatsApp envoyé (HTTP {resp.status})")
            return True
    except Exception as exc:  # une alerte ratée ne doit pas faire planter la surveillance
        print(f"::warning::Échec d'envoi WhatsApp : {exc}")
        return False


def race_block(text: str) -> list[str] | None:
    """Lignes du bloc '10 KM DE BLAGNAC' (sans le titre '21 KM ET 10 KM ...'), ou None s'il est absent."""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    for i, line in enumerate(lines):
        if line.upper().startswith(RACE):
            end = next((j for j in range(i + 1, len(lines)) if BLOCK_END.match(lines[j])), len(lines))
            return lines[i:end]
    return None


def parse_detail(text: str) -> bool:
    """True si le 10 km n'est plus COMPLET ni fermé."""
    block = race_block(text)
    if block is None:
        raise ValueError(f"Bloc '{RACE}' introuvable sur la page détail")
    body = " ".join(block).upper()
    return "COMPLET" not in body and "FERMÉES" not in body and "FERMEES" not in body


def parse_bourse(text: str) -> int:
    """Nombre de dossards 10 km proposés sur la bourse (0 si la section n'existe pas)."""
    if "Bourse aux" not in text or RACE not in text.upper():
        raise ValueError("Page bourse incomplète (rendu JS non terminé ?)")
    block = race_block(text) or []
    return sum(1 for l in block if l.endswith("Postuler"))


def fetch_texts() -> tuple[str, str]:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        # BROWSER_CHANNEL=chrome réutilise le Chrome préinstallé du runner GitHub (pas de téléchargement).
        browser = p.chromium.launch(headless=True, channel=os.environ.get("BROWSER_CHANNEL") or None)
        texts = []
        for url in (DETAIL_URL, BOURSE_URL):
            for attempt in range(3):
                # Contexte neuf à chaque fois : enchaîner deux pages dans la même session déclenche
                # la page anti-bot "Vérification de sécurité en cours".
                context = browser.new_context(user_agent=USER_AGENT, locale="fr-FR")
                page = context.new_page()
                try:
                    page.goto(url, wait_until="load", timeout=60_000)
                    # La bourse ne devient jamais "networkidle" : on attend le texte rendu par JS.
                    page.wait_for_function(
                        "t => document.body.innerText.toUpperCase().includes(t)", arg=RACE, timeout=20_000
                    )
                    page.wait_for_timeout(1_500)
                    texts.append(page.inner_text("body"))
                    break
                except Exception:
                    if attempt == 2:
                        raise
                    page.wait_for_timeout(10_000)
                finally:
                    context.close()
        browser.close()
    return texts[0], texts[1]


def load_state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {"detail_open": False, "bourse_10k": 0, "failures": 0}


def main() -> int:
    state = load_state()
    new = dict(state, day=datetime.now(timezone.utc).date().isoformat())  # heartbeat quotidien (voir README)
    try:
        detail_text, bourse_text = fetch_texts()
        detail_open = parse_detail(detail_text)
        bourse_10k = parse_bourse(bourse_text)
    except Exception as exc:
        new["failures"] = state.get("failures", 0) + 1
        print(f"::warning::Vérification impossible ({new['failures']} échec(s) d'affilée) : {exc}")
        if new["failures"] == FAILURE_ALERT_AT:
            send_whatsapp(f"⚠️ Bot 10 km Blagnac : {FAILURE_ALERT_AT} vérifications échouées d'affilée. Dernière erreur : {exc}")
        STATE_FILE.write_text(json.dumps(new, indent=2) + "\n", encoding="utf-8")
        return 0

    print(f"10 km ouvert : {detail_open} | dossards 10 km sur la bourse : {bourse_10k}")
    if detail_open and not state.get("detail_open"):
        send_whatsapp(f"🏃 10 KM DE BLAGNAC : les inscriptions semblent RÉOUVERTES !\n{DETAIL_URL}")
    if bourse_10k > state.get("bourse_10k", 0):
        send_whatsapp(f"🎽 10 KM DE BLAGNAC : {bourse_10k} dossard(s) sur la bourse aux échanges !\n{BOURSE_URL}")

    new.update(detail_open=detail_open, bourse_10k=bourse_10k, failures=0)
    STATE_FILE.write_text(json.dumps(new, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    if sys.argv[1:] == ["--test-whatsapp"]:
        sys.exit(0 if send_whatsapp("✅ Test du bot 10 km Blagnac : les alertes WhatsApp fonctionnent.") else 1)
    sys.exit(main())
