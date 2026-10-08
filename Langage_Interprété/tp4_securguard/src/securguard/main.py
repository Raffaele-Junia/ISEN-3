"""Interface en ligne de commande de secuguard."""

import argparse
from html import parser

from .analyzer import analyser_mot_de_passe
from .generator import generer_mot_de_passe

def construire_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="secuguard",description="Générateur et analyseur de mots de passe.")
    parser.add_argument("-c", "--check",type=str,default=None,metavar="MOT_DE_PASSE",help="Vérifie la solidité du mot de passe fourni.")
    parser.add_argument("-l", "--length",type=int,default=12,metavar="N",help="Longueur du mot de passe à générer (par défaut : 12).")
    parser.add_argument("--no-digits",action="store_false",dest="avec_chiffres",default=True,help="Exclut les chiffres du mot de passe généré.")
    parser.add_argument("--no-symbols",action="store_false",dest="avec_symboles",default=True,help="Exclut les symboles du mot de passe généré.")

    return parser

if __name__ == "__main__":
    parser = construire_parser()
    args = parser.parse_args()

    if args.check is not None:
        analyse = analyser_mot_de_passe(args.check)
        print(f"Analyse du mot de passe '{args.check}': {analyse}")
    else:
        mot_de_passe = generer_mot_de_passe(
            args.length,
            args.avec_chiffres,
            args.avec_symboles,
        )
        print(f"Mot de passe genere : {mot_de_passe}")
