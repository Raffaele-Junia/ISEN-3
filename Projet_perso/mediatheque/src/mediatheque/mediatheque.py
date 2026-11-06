from datetime import date
from pathlib import Path

from .emprunt import Emprunt
from .exceptions import (AdherentInconnuError, DocumentIndisponibleError,
                         DocumentInconnuError, QuotaDepasseError, MediathequeError)
from .stockage import (lire_adherents, lire_documents, lire_emprunts,
                       ecrire_adherents, ecrire_documents, ecrire_emprunts)


class Mediatheque:

    def __init__(self):
        self._documents = {}
        self._adherents = {}
        self._emprunts = []
        self._dossier = None

    def ajouter_document(self, document):
        self._documents[document.id] = document

    def ajouter_adherent(self, adherent):
        self._adherents[adherent.numero] = adherent

    def ajouter_emprunt(self, emprunt):
        self._emprunts.append(emprunt)

    @classmethod
    def charger(cls, dossier):
        dossier = Path(dossier)
        m = cls()
        m._dossier = dossier
        for document in lire_documents(dossier / "documents.csv"):
            m.ajouter_document(document)
        for adherent in lire_adherents(dossier / "adherents.csv"):
            m.ajouter_adherent(adherent)
        for emprunt in lire_emprunts(dossier / "emprunts.csv"):
            m.ajouter_emprunt(emprunt)
        return m

    def sauvegarder(self, dossier=None):
        dossier = Path(dossier) if dossier is not None else self._dossier
        if dossier is None:
            raise ValueError("aucun dossier de sauvegarde indique")
        dossier.mkdir(parents=True, exist_ok=True)
        ecrire_documents(dossier / "documents.csv", self._documents.values())
        ecrire_adherents(dossier / "adherents.csv", self._adherents.values())
        ecrire_emprunts(dossier / "emprunts.csv", self._emprunts)

    @property
    def emprunts(self):
        return tuple(self._emprunts)

    def disponible(self, id_document):
        if id_document not in self._documents:
            raise DocumentInconnuError(id_document)
        return not any(e.id_document == id_document and e.en_cours
                       for e in self._emprunts)

    def emprunter(self, id_document, numero, date_emprunt=None):
        if id_document not in self._documents:
            raise DocumentInconnuError(id_document)
        if numero not in self._adherents:
            raise AdherentInconnuError(numero)
        if not self.disponible(id_document):
            raise DocumentIndisponibleError(self._documents[id_document].titre)

        quota = self._adherents[numero].quota
        nb_en_cours = sum(1 for e in self._emprunts
                          if e.numero_adherent == numero and e.en_cours)
        if nb_en_cours >= quota:
            raise QuotaDepasseError(nb_en_cours, quota)

        emprunt = Emprunt(id_document, numero, date_emprunt or date.today())
        self.ajouter_emprunt(emprunt)
        return emprunt

    def retourner(self, id_document, date_retour=None):
        if id_document not in self._documents:
            raise DocumentInconnuError(id_document)
        for emprunt in self._emprunts:
            if emprunt.id_document == id_document and emprunt.en_cours:
                emprunt.date_retour = date_retour or date.today()
                return emprunt
        raise MediathequeError(f"aucun emprunt en cours pour : {id_document}")

    def rechercher(self,critere):
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
