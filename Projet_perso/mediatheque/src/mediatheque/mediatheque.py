from datetime import date
from pathlib import Path

from . import stockage_sqlite
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
        self._source = None

    def ajouter_document(self, document):
        if document.id in self._documents:
            raise MediathequeError(f"identifiant de document deja utilise : {document.id}")
        self._documents[document.id] = document

    def ajouter_adherent(self, adherent):
        if adherent.numero in self._adherents:
            raise MediathequeError(f"numero d'adherent deja utilise : {adherent.numero}")
        self._adherents[adherent.numero] = adherent

    def ajouter_emprunt(self, emprunt):
        if emprunt.id_document not in self._documents:
            raise DocumentInconnuError(emprunt.id_document)
        if emprunt.numero_adherent not in self._adherents:
            raise AdherentInconnuError(emprunt.numero_adherent)
        self._emprunts.append(emprunt)

    @staticmethod
    def _est_sqlite(source):
        return Path(source).suffix in (".db", ".sqlite", ".sqlite3")

    @classmethod
    def charger(cls, source):
        """Charge depuis une base SQLite (`*.db`) ou un dossier de CSV."""
        source = Path(source)
        if cls._est_sqlite(source):
            documents, adherents, emprunts = stockage_sqlite.charger(source)
        else:
            documents = lire_documents(source / "documents.csv")
            adherents = lire_adherents(source / "adherents.csv")
            emprunts = lire_emprunts(source / "emprunts.csv")
        m = cls()
        m._source = source
        for document in documents:
            m.ajouter_document(document)
        for adherent in adherents:
            m.ajouter_adherent(adherent)
        for emprunt in emprunts:
            m.ajouter_emprunt(emprunt)
        return m

    def sauvegarder(self, destination=None):
        destination = Path(destination) if destination is not None else self._source
        if destination is None:
            raise ValueError("aucune destination de sauvegarde indiquee")
        if self._est_sqlite(destination):
            destination.parent.mkdir(parents=True, exist_ok=True)
            stockage_sqlite.sauvegarder(destination, self._documents.values(),
                                        self._adherents.values(), self._emprunts)
            return
        destination.mkdir(parents=True, exist_ok=True)
        ecrire_documents(destination / "documents.csv", self._documents.values())
        ecrire_adherents(destination / "adherents.csv", self._adherents.values())
        ecrire_emprunts(destination / "emprunts.csv", self._emprunts)

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
