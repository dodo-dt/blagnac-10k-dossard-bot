# Bot dossard — 10 KM DE BLAGNAC (07/03/2027)

Vérifie toutes les 5 min (GitHub Actions) la page Chrono-Start de l'épreuve et sa bourse aux échanges, et envoie une alerte WhatsApp et/ou Telegram (tous les canaux configurés) quand :
- le bloc `10 KM DE BLAGNAC` n'est plus `COMPLET` / `Inscriptions Internet Fermées` ;
- le nombre de dossards 10 km proposés sur la bourse augmente.

L'état est stocké dans `state.json`, commité par le workflow (une fois par jour au minimum, ce qui évite aussi la désactivation automatique des crons après 60 jours sans activité).

## Secrets
- `WHATSAPP_PHONE` (ex. `+33612345678`) et `CALLMEBOT_APIKEY` : [CallMeBot](https://www.callmebot.com/blog/free-api-whatsapp-messages/).
- `TELEGRAM_USER` (ex. `@monpseudo`) : envoyer `/start` à `@CallMeBot_txtbot` sur Telegram d'abord.
- Optionnel `WHATSAPP_WEBHOOK_URL` : remplace CallMeBot, reçoit un `POST {"message": "..."}`.

## Local
```
pip install -r requirements.txt && playwright install chromium
python test_monitor.py && python monitor.py
python monitor.py --test-whatsapp
```
