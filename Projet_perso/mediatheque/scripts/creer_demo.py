"""Cree une base de DEMONSTRATION avec des comptes de test (jamais en production).

    uv run python scripts/creer_demo.py [chemin.db] [--depuis data_demo]

Par defaut, elle part du jeu genere par scripts/generer_donnees.py (data_demo/).
Comptes crees (mots de passe de test, a ne jamais reutiliser ailleurs) :
    admin             / Demo1234  (responsable)
    prenom.nom        / Demo1234  pour CHAQUE adherent, sans accents
                                  (ex. lea.martin, hugo.durand, ines.petit)
Compter ~0,5 s par compte : le hachage scrypt est volontairement lent.
"""
import argparse
import re
import sys
import unicodedata
from pathlib import Path

from mediatheque.auth import ADHERENT, RESPONSABLE
from mediatheque.mediatheque import Mediatheque

MDP_DEMO = "Demo1234"
RACINE = Path(__file__).resolve().parent.parent


def identifiant(adherent):
    brut = f"{adherent.prenom}.{adherent.nom}"
    sans_accents = unicodedata.normalize("NFKD", brut).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9.]+", "-", sans_accents.lower()).strip("-")[:32]


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("cible", nargs="?", default="demo.db")
    parser.add_argument("--depuis", default=str(RACINE / "data_demo"))
    args = parser.parse_args()

    cible = Path(args.cible)
    if cible.exists():
        sys.exit(f"{cible} existe deja")
    m = Mediatheque.charger(args.depuis)
    m.creer_compte("admin", MDP_DEMO, RESPONSABLE)
    for a in m.adherents:
        m.creer_compte(identifiant(a), MDP_DEMO, ADHERENT, a.numero)
    m.sauvegarder(cible)
    print(f"Base de demo creee : {cible} ({len(m)} documents, "
          f"{len(m.adherents)} adherents, {len(m.comptes)} comptes)")


if __name__ == "__main__":
    main()
