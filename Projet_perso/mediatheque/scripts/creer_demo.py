"""Cree une base de DEMONSTRATION avec des comptes de test (jamais en production).

    uv run python scripts/creer_demo.py [chemin.db]

Comptes crees (mots de passe de test, a ne jamais reutiliser ailleurs) :
    admin / Demo1234  (responsable)
    lea   / Demo1234  (adherente A001)
    hugo  / Demo1234  (adherent A002)
    ines  / Demo1234  (adherente A003)
"""
import sys
from datetime import date, timedelta
from pathlib import Path

from mediatheque.auth import ADHERENT, RESPONSABLE
from mediatheque.mediatheque import Mediatheque

MDP_DEMO = "Demo1234"


def main():
    cible = Path(sys.argv[1] if len(sys.argv) > 1 else "demo.db")
    if cible.exists():
        sys.exit(f"{cible} existe deja")
    m = Mediatheque.charger(Path(__file__).resolve().parent.parent / "data")
    m.creer_compte("admin", MDP_DEMO, RESPONSABLE)
    for ident, numero in (("lea", "A001"), ("hugo", "A002"), ("ines", "A003")):
        m.creer_compte(ident, MDP_DEMO, ADHERENT, numero)
    hier = date.today() - timedelta(days=1)
    for id_doc, numero in (("D004", "A002"), ("D003", "A003"), ("D001", "A003")):
        try:
            m.reserver(id_doc, numero, hier)
        except Exception as e:  # selon l'etat des donnees
            print(f"reservation {id_doc}/{numero} ignoree : {e}")
    m.sauvegarder(cible)
    print(f"Base de demo creee : {cible}")


if __name__ == "__main__":
    main()
