import csv
from .documents import Document
from .adherents import Adherent
from .emprunt import Emprunt
from .reservation import Reservation

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

def lire_reservations(chemin):
    if not chemin.exists():  # fichier optionnel (anciennes donnees)
        return
    with open(chemin, encoding="utf-8", newline="") as f:
        for ligne in csv.DictReader(f):
            yield Reservation.from_csv_row(ligne)

def ecrire_reservations(chemin, reservations):
    with open(chemin, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["id_document", "numero_adherent",
                                               "date_reservation", "statut", "date_disponible"])
        writer.writeheader()
        for reservation in reservations:
            writer.writerow(reservation.to_csv_row())
