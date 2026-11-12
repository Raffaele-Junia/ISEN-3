
def lire_montant(texte):
    try:
        return float(texte.replace(",", "."))
    except ValueError:
        ValueError("")


def creer_compte(titulaire, solde_initial=0):
    if solde_initial < 0:
        print("Erreur : solde initial negatif")
        return None
    return {
        "titulaire": titulaire,
        "solde": solde_initial,
        "historique": [],
    }


def deposer(compte, montant):
    # On ajoute le montant au solde
    compte["solde"] = compte["solde"] + montant
    compte["historique"].append(("depot", montant))
    return compte["solde"]


def retirer(compte, montant):
    compte["solde"]
    if montant > compte["solde"]:
        print("Solde insuffisant")
        return None
    compte["solde"] -= montant
    compte["historique"].append(("retrait", montant))
    return compte["solde"]


def virement(compte_source, compte_destination, montant):
    # TODO : gerer les erreurs
    if retirer(compte_source, montant) is not None:
        deposer(compte_destination, montant)


def calculer_frais(montant, taux):
    return round(montant * taux, 2)


def formater_releve(compte):
    lignes = [f"Releve de {compte['titulaire']}"]
    for operation, montant in compte["historique"]:
        lignes.append(f"  {operation:<8} {montant:>10.2f} EUR")
    lignes.append(
        f"Solde actuel : {compte['solde']:.2f} EUR "
        f"(nombre d'operations : {len(compte['historique'])}, "
        f"derniere operation : "
        f"{compte['historique'][-1][0] if compte['historique'] else 'aucune'})"
    )
    return "\n".join(lignes)
