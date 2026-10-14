import argparse
import sys
from pydantic import ValidationError

from .loaders import charger_config, charger_catalogue, lire_commandes, valider_commandes
from .exporters import calculer_rapport, exporter_rapport_json, exporter_expeditions_csv

def main():
    parser = argparse.ArgumentParser(description="Outil de traitement des commandes TechShop")
    parser.add_argument("-c", "--config", type=str, default="config.yaml")
    parser.add_argument("-i", "--input", type=str, default=None)
    parser.add_argument("-k", "--catalogue", type=str, default=None)

    args = parser.parse_args()

    try:
        config = charger_config(args.config)

        if args.input:
            config.commandes = args.input
        if args.catalogue:
            config.catalogue = args.catalogue

        catalogue = charger_catalogue(config.catalogue)
        lignes_commandes = lire_commandes(config.commandes)
        commandes = valider_commandes(lignes_commandes)

        print(f"[OK] {len(commandes)} commandes validees")

        rapport = calculer_rapport(commandes, catalogue, config)
        for alerte in rapport["alertes_stock"]:
            print(f"[ALERTE] stock bas {alerte['ref']} ({alerte['stock']} en stock)")

        ca = rapport["chiffre_affaires"]
        print(f"Chiffre d'affaires {ca['ht']:.2f} EUR HT {ca['ttc']:.2f} EUR TTC")

        chemin_rapport = f"{config.sortie}/rapport.json"
        chemin_expeditions = f"{config.sortie}/expeditions.csv"

        exporter_rapport_json(rapport, chemin_rapport)
        exporter_expeditions_csv(commandes, chemin_expeditions)

        print(f"Rapport {chemin_rapport}")
        print(f"Expeditions {chemin_expeditions}")

    except (ValidationError, Exception) as e:
        print(f"Erreur : {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()