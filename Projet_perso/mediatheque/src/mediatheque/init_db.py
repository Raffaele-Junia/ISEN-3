"""Cree la base SQLite a partir des CSV et le premier compte responsable.

Usage : uv run mediatheque-init [--depuis data] [--db mediatheque.db] [--admin admin]
Le mot de passe est demande au clavier (jamais en argument : il resterait
dans l'historique du terminal).
"""
import argparse
import getpass
import sys
from pathlib import Path

from .auth import RESPONSABLE
from .exceptions import MediathequeError
from .mediatheque import Mediatheque


def initialiser(depuis, db, admin, mot_de_passe):
    db = Path(db)
    if db.exists():
        raise MediathequeError(f"{db} existe deja : supprimez-le ou choisissez un autre nom")
    m = Mediatheque.charger(depuis)
    m.creer_compte(admin, mot_de_passe, RESPONSABLE)
    m.sauvegarder(db)
    return m


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--depuis", default="data", help="dossier des CSV a importer")
    parser.add_argument("--db", default="mediatheque.db", help="base SQLite a creer")
    parser.add_argument("--admin", default="admin", help="identifiant du responsable")
    args = parser.parse_args(argv)

    mdp = getpass.getpass(f"Mot de passe pour '{args.admin}' : ")
    if getpass.getpass("Confirmez : ") != mdp:
        print("Les mots de passe ne correspondent pas.", file=sys.stderr)
        return 1
    try:
        m = initialiser(args.depuis, args.db, args.admin, mdp)
    except MediathequeError as e:
        print(f"Erreur : {e}", file=sys.stderr)
        return 1
    print(f"Base {args.db} creee : {len(m)} documents, {len(m.adherents)} adherents, "
          f"compte responsable '{args.admin}'.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
