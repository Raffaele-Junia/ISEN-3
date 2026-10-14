import yaml
import json
import csv
from .models import Config, Catalogue, Commande

def charger_config(chemin: str) -> Config:
    with open(chemin, 'r', encoding='utf-8') as fichier:
        user_config = yaml.safe_load(fichier)
    return Config.model_validate(user_config)

def charger_catalogue(chemin: str) -> Catalogue:
    with open(chemin, 'r', encoding='utf-8') as fichier:
        user_catalogue = json.load(fichier)
    return Catalogue.model_validate(user_catalogue)

def lire_commandes(chemin: str) -> list[dict]:
    with open(chemin, mode="r", newline="", encoding="utf-8") as fichier:
        lecteur = csv.DictReader(fichier)
        return list(lecteur)

def valider_commandes(lignes: list[dict]) -> list[Commande]:
    return [Commande.model_validate(ligne) for ligne in lignes]