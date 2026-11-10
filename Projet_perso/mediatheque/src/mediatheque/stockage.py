import csv
from .documents import Document
from .adherents import Adherent
from .emprunt import Emprunt

def lire_documents(chemin):
    with open(chemin, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for ligne in reader:
            yield(Document.from_csv_row(ligne))

def lire_adherents(chemin):
    with open(chemin, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for ligne in reader:
            yield(Adherent.from_csv_row(ligne))

def lire_emprunts(chemin):
    with open(chemin, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for ligne in reader:
            yield(Emprunt.from_csv_row(ligne))

def ecrire_documents(chemin,documents):
    with open(chemin, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f,fieldnames=["id","type","titre","annee","extra"])
        writer.writeheader()
        for document in documents:
            writer.writerow(document.to_csv_row())

def ecrire_adherents(chemin,adherents):
    with open(chemin, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f,fieldnames=["numero","nom","prenom","type"])
            writer.writeheader()
            for adherent in adherents:
                writer.writerow(adherent.to_csv_row())

def ecrire_emprunts(chemin,emprunts):
    with open(chemin, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f,fieldnames=["id_document","numero_adherent","date_emprunt","date_retour"])
            writer.writeheader()
            for emprunt in emprunts:
                writer.writerow(emprunt.to_csv_row())
