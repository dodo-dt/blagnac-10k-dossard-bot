"""Self-check du parsing sur des extraits réels des pages Chrono-Start. Lancer : python test_monitor.py"""
from monitor import parse_bourse, parse_detail

DETAIL = """21 KM ET 10 KM DE BLAGNAC
BOURSE AUX ECHANGES
Nombre d'inscription(s) disponible(s): 1
10 KM DE BLAGNAC  19€ *
Course Individuelle
Inscriptions Internet Fermées  (COMPLET)
21 KM DE BLAGNAC  29€ *
Course Individuelle
Inscriptions Internet Fermées  (COMPLET)
MARCHE 6 KM  5€ *
Epreuve Individuelle
Clôture des inscriptions le 04/03/2027 à 12:00:00"""

BOURSE = """ 	21 KM ET 10 KM DE BLAGNAC
Bourse aux échanges
 		21 KM DE BLAGNAC
Inscriptions Fermées  (COMPLET)
Participant	Dossard	Demandes	Action
DOE jane	67	236	Postuler
Conditions générale de vente"""

BOURSE_10K = BOURSE.replace("Conditions", """10 KM DE BLAGNAC
Inscriptions Fermées  (COMPLET)
Participant	Dossard	Demandes	Action
DUPONT jean	12	3	Postuler
MARTIN paul	44	0	Postuler
Conditions""")

assert parse_detail(DETAIL) is False
# Le 21 km qui rouvre ne doit pas déclencher d'alerte 10 km.
assert parse_detail(DETAIL.replace("Fermées  (COMPLET)\n21", "XX\n21", 0).replace(
    "21 KM DE BLAGNAC  29€ *\nCourse Individuelle\nInscriptions Internet Fermées  (COMPLET)",
    "21 KM DE BLAGNAC  29€ *\nCourse Individuelle\nInscriptions ouvertes")) is False
assert parse_detail(DETAIL.replace(
    "10 KM DE BLAGNAC  19€ *\nCourse Individuelle\nInscriptions Internet Fermées  (COMPLET)",
    "10 KM DE BLAGNAC  19€ *\nCourse Individuelle\nClôture des inscriptions le 04/03/2027")) is True
assert parse_bourse(BOURSE) == 0  # l'offre 21 km ne compte pas
assert parse_bourse(BOURSE_10K) == 2
for bad in ("", "Chargement..."):
    try:
        parse_detail(bad)
        raise AssertionError("page vide acceptée")
    except ValueError:
        pass
print("OK")
