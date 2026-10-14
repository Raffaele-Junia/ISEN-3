import os
import json
import csv
from datetime import datetime
from shopcheck.models import Commande, Catalogue, Config

def calculer_rapport(commandes: list[Commande], catalogue: Catalogue, config: Config) -> dict:
    total_ht = 0.0
    par_statut = {"payee": 0, "expediee": 0, "annulee": 0}

    for cmd in commandes:
        if cmd.statut in par_statut:
            par_statut[cmd.statut] += 1
        if cmd.statut != "annulee":
            total_ht += cmd.quantite * cmd.prix_unitaire

    total_ht = round(total_ht, 2)
    tva = round(total_ht * config.tva, 2)
    ttc = round(total_ht + tva, 2)

    alertes_stock = []
    for produit in catalogue.produits:
        if produit.stock < config.seuil_alerte_stock:
            alertes_stock.append({"ref": produit.ref, "stock": produit.stock})

    rapport = {
        "genere_le": datetime.now().isoformat(),
        "nb_commandes": len(commandes),
        "chiffre_affaires": {
            "ht": total_ht,
            "tva": tva,
            "ttc": ttc
        },
        "par_statut": par_statut,
        "alertes_stock": alertes_stock
    }

    return rapport

def exporter_rapport_json(rapport: dict, chemin: str) -> None:
    dossier = os.path.dirname(chemin)
    if dossier:
        os.makedirs(dossier, exist_ok=True)
    with open(chemin, mode="w", encoding="utf-8") as fichier:
        json.dump(rapport, fichier, indent=2, ensure_ascii=False)

def exporter_expeditions_csv(commandes: list[Commande], chemin: str) -> None:
    dossier = os.path.dirname(chemin)
    if dossier:
        os.makedirs(dossier, exist_ok=True)

    commandes_payees = [cmd for cmd in commandes if cmd.statut == "payee"]
    champs = ["id_commande", "client_email", "ref", "quantite"]

    with open(chemin, mode="w", newline="", encoding="utf-8-sig") as fichier:
        writer = csv.DictWriter(fichier, fieldnames=champs)
        writer.writeheader()
        for cmd in commandes_payees:
            ligne = {
                "id_commande": cmd.id_commande,
                "client_email": cmd.client_email,
                "ref": cmd.ref,
                "quantite": cmd.quantite
            }
            writer.writerow(ligne)