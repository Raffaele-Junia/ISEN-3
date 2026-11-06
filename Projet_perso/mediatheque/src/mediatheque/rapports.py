import csv
from collections import Counter


def par_auteur(nom):
    def filtre(document):
        return hasattr(document, "auteur") and nom.lower() in document.auteur.lower()
    return filtre


def parue_apres(annee):
    def filtre(document):
        return document.annee > annee
    return filtre


def du_type(classe):
    def filtre(document):
        return isinstance(document, classe)
    return filtre


def retards(m, aujourdhui):
    for emprunt in m.emprunts:
        if not emprunt.en_cours:
            continue
        document = m[emprunt.id_document]
        jours = emprunt.jours_retard(document.duree_pret_jour, aujourdhui)
        if jours > 0:
            yield emprunt, document, jours


def top_emprunteurs(m, n=3):
    compteur = Counter(e.numero_adherent for e in m.emprunts)
    return compteur.most_common(n)


def export_retards_csv(chemin, retards):
    nb = 0
    with open(chemin, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=["id_document", "numero_adherent", "jours_retard"])
        writer.writeheader()
        for emprunt, document, jours in retards:
            writer.writerow({
                "id_document": emprunt.id_document,
                "numero_adherent": emprunt.numero_adherent,
                "jours_retard": jours,
            })
            nb += 1
    return nb