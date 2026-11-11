from collections import Counter
from datetime import date, datetime
from pathlib import Path

from . import stockage_sqlite
from .auth import ADHERENT, GestionComptes
from .emprunt import Emprunt
from .journal import EntreeJournal
from .exceptions import (AdherentInconnuError, DocumentIndisponibleError,
                         DocumentInconnuError, QuotaDepasseError, MediathequeError,
                         ReservationImpossibleError)
from .reservation import (ANNULEE, DISPONIBLE, EN_ATTENTE, EXPIREE, HONOREE,
                          MAX_RESERVATIONS, Reservation)
from .stockage import (lire_adherents, lire_documents, lire_emprunts, lire_reservations,
                       ecrire_adherents, ecrire_documents, ecrire_emprunts,
                       ecrire_reservations)


MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
        "septembre", "octobre", "novembre", "décembre"]


class Mediatheque:
    """Moteur metier. Ne fait AUCUN controle d'acces : c'est le role de
    `session.Session`, seule porte d'entree autorisee pour l'interface."""

    def __init__(self):
        self._documents = {}
        self._adherents = {}
        self._emprunts = []
        self._reservations = []
        self.comptes = GestionComptes()
        self._journal = []
        self._source = None

    # ------------------------------------------------------------------ ajout
    def ajouter_document(self, document):
        if document.id in self._documents:
            raise MediathequeError(f"Ce n° d'inventaire est déjà utilisé : {document.id}.")
        self._documents[document.id] = document

    def ajouter_adherent(self, adherent):
        if adherent.numero in self._adherents:
            raise MediathequeError(f"Ce n° de carte est déjà utilisé : {adherent.numero}.")
        self._adherents[adherent.numero] = adherent

    def modifier_adherent(self, numero, nom, prenom, type_adherent):
        """Corrige l'identite ou change la formule. Renvoie la liste des changements."""
        a = self.adherent(numero)
        nom, prenom = " ".join(str(nom).split()), " ".join(str(prenom).split())
        if not nom or not prenom or len(nom) > 60 or len(prenom) > 60:
            raise MediathequeError("Nom et prénom sont obligatoires (60 caractères au plus).")
        changements = []
        if type_adherent != a.type:
            ancien = a.type
            a.type = type_adherent  # le setter refuse une formule inconnue
            changements.append(f"formule {ancien} → {type_adherent}")
        if (nom, prenom) != (a.nom, a.prenom):
            changements.append(f"identité {a.prenom} {a.nom} → {prenom} {nom}")
            a.nom, a.prenom = nom, prenom
        return changements

    def ajouter_emprunt(self, emprunt):
        self._verifier_references(emprunt.id_document, emprunt.numero_adherent)
        self._emprunts.append(emprunt)

    def ajouter_reservation(self, reservation):
        self._verifier_references(reservation.id_document, reservation.numero_adherent)
        self._reservations.append(reservation)

    def ajouter_compte(self, compte):
        if compte.numero_adherent is not None and compte.numero_adherent not in self._adherents:
            raise AdherentInconnuError(compte.numero_adherent)
        if compte.role == ADHERENT and self.comptes.compte_de_adherent(compte.numero_adherent):
            raise MediathequeError(
                f"Le lecteur {compte.numero_adherent} a déjà un compte en ligne.")
        self.comptes.ajouter(compte)

    def creer_compte(self, identifiant, mot_de_passe, role, numero_adherent=None):
        if numero_adherent is not None:
            self.adherent(numero_adherent)  # leve AdherentInconnuError
            if self.comptes.compte_de_adherent(numero_adherent):
                raise MediathequeError(f"Le lecteur {numero_adherent} a déjà un compte en ligne.")
        return self.comptes.creer(identifiant, mot_de_passe, role, numero_adherent)

    def supprimer_document(self, id_document):
        if id_document not in self._documents:
            raise DocumentInconnuError(id_document)
        if (any(e.id_document == id_document for e in self._emprunts)
                or any(r.id_document == id_document for r in self._reservations)):
            raise MediathequeError(
                "Ce document a déjà circulé : on garde son historique, il ne peut pas être retiré.")
        return self._documents.pop(id_document)

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
        m._journal = list(donnees.get("journal", ()))
        for compte in donnees.get("comptes", ()):
            m.ajouter_compte(compte)
        m._verifier_coherence()
        return m

    def _verifier_coherence(self):
        """Regles metier sur les donnees chargees (base eventuellement falsifiee) :
        leve MediathequeError a la premiere incoherence."""
        en_cours = Counter(e.id_document for e in self._emprunts if e.en_cours)
        if any(n > 1 for n in en_cours.values()):
            raise MediathequeError("document emprunte deux fois simultanement")
        for a in self._adherents.values():
            if len(self.emprunts_de(a.numero)) > a.quota:
                raise MediathequeError(f"quota depasse pour {a.numero}")
        for e in self._emprunts:
            if e.date_retour is not None and e.date_retour < e.date_emprunt:
                raise MediathequeError("date de retour anterieure a l'emprunt")
        for r in self._reservations:
            # une reservation honoree/expiree/annulee garde sa date de mise de cote
            if (r.statut == DISPONIBLE and r.date_disponible is None
                    or r.statut == EN_ATTENTE and r.date_disponible is not None):
                raise MediathequeError("reservation incoherente : statut et date de mise de cote")
        mises = Counter(r.id_document for r in self._reservations if r.statut == DISPONIBLE)
        if any(n > 1 for n in mises.values()):
            raise MediathequeError("document mis de cote pour deux adherents")

    def recharger(self):
        """Remet l'etat en memoire au contenu de la source, EN PLACE (W4) : les
        objets qui gardent une reference a cette mediatheque (sessions ouvertes)
        voient l'etat recharge. Les comptes inchanges gardent leur identite
        (les sessions restent valides) et les compteurs d'echecs sont conserves."""
        if self._source is None:
            raise ValueError("aucune source a recharger")
        neuf = type(self).charger(self._source)
        self._documents, self._adherents = neuf._documents, neuf._adherents
        self._emprunts, self._reservations = neuf._emprunts, neuf._reservations
        self._journal = neuf._journal
        if self._est_sqlite(self._source):  # les CSV ne contiennent pas les comptes
            self.comptes.synchroniser(neuf.comptes)

    def sauvegarder(self, destination=None):
        destination = Path(destination) if destination is not None else self._source
        if destination is None:
            raise ValueError("aucune destination de sauvegarde indiquee")
        if self._est_sqlite(destination):
            destination.parent.mkdir(parents=True, exist_ok=True)
            stockage_sqlite.sauvegarder(destination, self._documents.values(),
                                        self._adherents.values(), self._emprunts,
                                        self._reservations, self.comptes, self._journal)
            return
        if len(self.comptes) or self._journal:
            raise MediathequeError(
                "les comptes ne peuvent etre sauvegardes qu'en SQLite (fichier .db)")
        destination.mkdir(parents=True, exist_ok=True)
        ecrire_documents(destination / "documents.csv", self._documents.values())
        ecrire_adherents(destination / "adherents.csv", self._adherents.values())
        ecrire_emprunts(destination / "emprunts.csv", self._emprunts)
        if self._reservations or (destination / "reservations.csv").exists():
            ecrire_reservations(destination / "reservations.csv", self._reservations)

    # ---------------------------------------------------------------- journal
    def journaliser(self, acteur, action, cible="", detail="", quand=None):
        """Ajoute une entree au journal (jamais de mot de passe)."""
        entree = EntreeJournal(quand or datetime.now().replace(microsecond=0),
                               acteur, action, cible, detail[:300])
        self._journal.append(entree)
        return entree

    @property
    def journal(self):
        return tuple(self._journal)

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
            titre = self._documents[id_document].titre
            reservee = self._mise_de_cote(id_document)
            if reservee is not None and not self._emprunt_en_cours(id_document):
                limite = reservee.date_limite_retrait
                raise DocumentIndisponibleError(titre, (
                    f"« {titre} » est mis de côté pour un autre lecteur (réservation) : "
                    f"lui seul peut l'emprunter jusqu'au {limite.day} {MOIS[limite.month - 1]}."))
            raise DocumentIndisponibleError(titre)

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
            raise MediathequeError(f"Ce document n'est pas sorti : rien à rendre ({id_document}).")
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
                "Ce document est en rayon : vous pouvez venir l'emprunter directement.")
        en_cours = self._emprunt_en_cours(id_document)
        if en_cours is not None and en_cours.numero_adherent == numero:
            raise ReservationImpossibleError("Vous avez déjà ce document chez vous.")
        if any(r.numero_adherent == numero for r in self.file_attente(id_document)):
            raise ReservationImpossibleError("Vous avez déjà réservé ce document.")
        if len(self.reservations_de(numero)) >= MAX_RESERVATIONS:
            raise ReservationImpossibleError(
                f"Vous avez déjà {MAX_RESERVATIONS} réservations : annulez-en une pour en faire une nouvelle.")
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
        raise ReservationImpossibleError("Vous n'avez pas de réservation pour ce document.")

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
