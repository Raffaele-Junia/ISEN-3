"""Purge du journal des actions : supprime les entrees plus anciennes que la
duree de conservation (CONSERVATION_JOURNAL_JOURS, 365 jours par defaut).

Usage : uv run --system-certs python -m mediatheque.purge_journal --db mediatheque.db
        [--responsable admin] [--jours 365]
Jamais automatique. Le mot de passe d'un compte RESPONSABLE est demande au
clavier, et la purge est elle-meme inscrite au journal. A lancer site arrete
(ou, a defaut, redemarrer le site ensuite pour qu'il relise le journal purge).
"""
import argparse
import getpass
import sys

from .exceptions import AuthentificationError, MediathequeError
from .journal import CONSERVATION_JOURNAL_JOURS
from .mediatheque import Mediatheque


def purger(db, identifiant, mot_de_passe, jours=CONSERVATION_JOURNAL_JOURS):
    """Authentifie le responsable puis purge. Renvoie le nombre d'entrees supprimees."""
    m = Mediatheque.charger(db)
    compte = m.comptes.authentifier(identifiant, mot_de_passe)
    return m.purger_journal(compte, jours)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", default="mediatheque.db", help="base SQLite")
    parser.add_argument("--responsable", default="admin", help="identifiant du responsable")
    parser.add_argument("--jours", type=int, default=CONSERVATION_JOURNAL_JOURS,
                        help="duree de conservation en jours")
    args = parser.parse_args(argv)
    mdp = getpass.getpass(f"Mot de passe de '{args.responsable}' : ")
    try:
        n = purger(args.db, args.responsable, mdp, args.jours)
    except (AuthentificationError, MediathequeError) as e:
        print(f"Erreur : {e}", file=sys.stderr)
        return 1
    print(f"Journal purgé : {n} entrée(s) de plus de {args.jours} jours supprimée(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
