from datetime import date
from pathlib import Path

from . import stockage_sqlite
from .emprunt import Emprunt
from .exceptions import (AdherentInconnuError, DocumentIndisponibleError,
                         DocumentInconnuError, QuotaDepasseError, MediathequeError,
                         ReservationImpossibleError)
from .reservation import (ANNULEE, DISPONIBLE, EN_ATTENTE, EXPIREE, HONOREE,
                          MAX_RESERVATIONS, Reservation)
from .stockage import (lire_adherents, lire_documents, lire_emprunts, lire_reservations,
                       ecrire_adherents, ecrire_documents, ecrire_emprunts,
                       ecrire_reservations)


class Mediatheque:
    """Moteur metier. Ne fait AUCUN controle d'acces : c'est le role de
    `session.Session`, seule porte d'entree autorisee pour l'interface."""

    def __init__(self):
        self._documents = {}
        self._adherents = {}
        self._emprunts = []
        self._reservations = []
        self._source = None

    # ------------------------------------------------------------------ ajout
    def ajouter_document(self, document):
        if document.id in self._documents:
            raise MediathequeError(f"identifiant de document deja utilise : {document.id}")
        self._documents[document.id] = document

    def ajouter_adherent(self, adherent):
        if adherent.numero in self._adherents:
            raise MediathequeError(f"numero d'adherent deja utilise : {adherent.numero}")
        self._adherents[adherent.numero] = adherent

    def ajouter_emprunt(self, emprunt):
        self._verifier_references(emprunt.id_document, emprunt.numero_adherent)
        self._emprunts.append(emprunt)

    def ajouter_reservation(self, reservation):
        self._verifier_references(reservation.id_document, reservation.numero_adherent)
        self._reservations.append(reservation)

    def _verifier_references(self, id_document, numero):
        if id_document not in self._documents:
            raise DocumentInconnuError(id_document)
        if numero not in self._adherents:
            raise AdherentInconnuError(numero)

    # ------------------------------------------------------------ persistance
    @staticmethod
    def _est_sqlite(source):
        return Path(source).suffix in (".db", ".sqlite", ".sqlite3")

    @classmethod
    def charger(cls, source):
        """Charge depuis une base SQLite (`*.db`) ou un dossier de CSV."""
        source = Path(source)
        if cls._est_sqlite(source):
            donnees = stockage_sqlite.charger(source)
        else:
            donnees = {
                "documents": lire_documents(source / "documents.csv"),
                "adherents": lire_adherents(source / "adherents.csv"),
                "emprunts": lire_emprunts(source / "emprunts.csv"),
                "reservations": lire_reservations(source / "reservations.csv"),
            }
        m = cls()
        m._source = source
        for document in donnees["documents"]:
            m.ajouter_document(document)
        for adherent in donnees["adherents"]:
            m.ajouter_adherent(adherent)
        for emprunt in donnees["emprunts"]:
            m.ajouter_emprunt(emprunt)
        for reservation in donnees["reservations"] or ():
            m.ajouter_reservation(reservation)
        return m

    def sauvegarder(self, destination=None):
        destination = Path(destination) if destination is not None else self._source
        if destination is None:
            raise ValueError("aucune destination de sauvegarde indiquee")
        if self._est_sqlite(destination):
            destination.parent.mkdir(parents=True, exist_ok=True)
            stockage_sqlite.sauvegarder(destination, self._documents.values(),
                                        self._adherents.values(), self._emprunts,
                                        self._reservations)
            return
        destination.mkdir(parents=True, exist_ok=True)
        ecrire_documents(destination / "documents.csv", self._documents.values())
        ecrire_adherents(destination / "adherents.csv", self._adherents.values())
        ecrire_emprunts(destination / "emprunts.csv", self._emprunts)
        if self._reservations or (destination / "reservations.csv").exists():
            ecrire_reservations(destination / "reservations.csv", self._reservations)

    # ----------------------------------------------------------- consultation
    @property
    def emprunts(self):
        return tuple(self._emprunts)

    @property
    def reservations(self):
        return tuple(self._reservations)

    def adherent(self, numero):
        try:
            return self._adherents[numero]
        except KeyError:
            raise AdherentInconnuError(numero) from None

    @property
    def adherents(self):
        return tuple(self._adherents.values())

    def emprunts_de(self, numero, en_cours_seulement=True):
        return [e for e in self._emprunts if e.numero_adherent == numero
                and (e.en_cours or not en_cours_seulement)]

    def reservations_de(self, numero, actives_seulement=True):
        return [r for r in self._reservations if r.numero_adherent == numero
                and (r.active or not actives_seulement)]

    def file_attente(self, id_document):
        """Reservations actives du document, dans l'ordre d'arrivee."""
        return [r for r in self._reservations
                if r.id_document == id_document and r.active]

    def _emprunt_en_cours(self, id_document):
        return next((e for e in self._emprunts
                     if e.id_document == id_document and e.en_cours), None)

    def _mise_de_cote(self, id_document):
        return next((r for r in self._reservations
                     if r.id_document == id_document and r.statut == DISPONIBLE), None)

    def disponible(self, id_document, numero=None):
        """Libre en rayon. Un document mis de cote n'est disponible que pour
        l'adherent qui l'a reserve (`numero`)."""
        if id_document not in self._documents:
            raise DocumentInconnuError(id_document)
        if self._emprunt_en_cours(id_document):
            return False
        reservee = self._mise_de_cote(id_document)
        return reservee is None or reservee.numero_adherent == numero

    # ---------------------------------------------------------------- emprunt
    def emprunter(self, id_document, numero, date_emprunt=None):
        jour = date_emprunt or date.today()
        self._verifier_references(id_document, numero)
        self.actualiser_reservations(jour)
        if not self.disponible(id_document, numero):
            raise DocumentIndisponibleError(self._documents[id_document].titre)

        quota = self._adherents[numero].quota
        nb_en_cours = len(self.emprunts_de(numero))
        if nb_en_cours >= quota:
            raise QuotaDepasseError(nb_en_cours, quota)

        reservee = self._mise_de_cote(id_document)
        if reservee is not None:
            reservee.statut = HONOREE
        emprunt = Emprunt(id_document, numero, jour)
        self._emprunts.append(emprunt)
        return emprunt

    def retourner(self, id_document, date_retour=None):
        if id_document not in self._documents:
            raise DocumentInconnuError(id_document)
        emprunt = self._emprunt_en_cours(id_document)
        if emprunt is None:
            raise MediathequeError(f"aucun emprunt en cours pour : {id_document}")
        emprunt.date_retour = date_retour or date.today()
        self._promouvoir_suivant(id_document, emprunt.date_retour)
        return emprunt

    # ----------------------------------------------------------- reservations
    def reserver(self, id_document, numero, jour=None):
        jour = jour or date.today()
        self._verifier_references(id_document, numero)
        self.actualiser_reservations(jour)
        if self.disponible(id_document, numero):
            raise ReservationImpossibleError(
                "document disponible : il peut etre emprunte directement")
        en_cours = self._emprunt_en_cours(id_document)
        if en_cours is not None and en_cours.numero_adherent == numero:
            raise ReservationImpossibleError("vous avez deja ce document en emprunt")
        if any(r.numero_adherent == numero for r in self.file_attente(id_document)):
            raise ReservationImpossibleError("vous avez deja reserve ce document")
        if len(self.reservations_de(numero)) >= MAX_RESERVATIONS:
            raise ReservationImpossibleError(
                f"limite de {MAX_RESERVATIONS} reservations actives atteinte")
        reservation = Reservation(id_document, numero, jour)
        self._reservations.append(reservation)
        return reservation

    def annuler_reservation(self, id_document, numero, jour=None):
        jour = jour or date.today()
        for r in self.file_attente(id_document):
            if r.numero_adherent == numero:
                etait_de_cote = r.statut == DISPONIBLE
                r.statut = ANNULEE
                if etait_de_cote:
                    self._promouvoir_suivant(id_document, jour)
                return r
        raise ReservationImpossibleError("aucune reservation active pour ce document")

    def actualiser_reservations(self, aujourdhui):
        """Expire les mises de cote non retirees et passe la main au suivant."""
        for r in list(self._reservations):
            if r.statut == DISPONIBLE and aujourdhui > r.date_limite_retrait:
                r.statut = EXPIREE
                self._promouvoir_suivant(r.id_document, aujourdhui)

    def _promouvoir_suivant(self, id_document, jour):
        if self._emprunt_en_cours(id_document) or self._mise_de_cote(id_document):
            return
        suivant = next((r for r in self._reservations
                        if r.id_document == id_document and r.statut == EN_ATTENTE), None)
        if suivant is not None:
            suivant.mettre_de_cote(jour)

    # -------------------------------------------------------------- recherche
    def rechercher(self, critere):
        return [document for document in self._documents.values()
                if critere(document)]

    def __len__(self):
        return len(self._documents)

    def __contains__(self, id_document):
        return id_document in self._documents

    def __getitem__(self, id_document):
        return self._documents[id_document]

    def __iter__(self):
        return iter(self._documents.values())

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self.sauvegarder()
        return False
