"""Session utilisateur : SEULE porte d'entree de l'interface graphique.

Chaque operation verifie le role du compte connecte ici, dans la couche
metier. Masquer un bouton dans l'interface ne suffit jamais.
- adherent    : consulte le catalogue et SON compte, reserve / annule pour LUI.
- responsable : tout, y compris agir pour un adherent donne.
"""
from datetime import date
from functools import wraps

from .adherents import Adherent
from .auth import ADHERENT, RESPONSABLE
from .documents import Document
from .exceptions import AccesRefuseError, MediathequeError
from .rapports import retards, top_emprunteurs


def ouvrir_session(mediatheque, identifiant, mot_de_passe):
    compte = mediatheque.comptes.authentifier(identifiant, mot_de_passe)
    return Session(mediatheque, compte)


def responsable_requis(methode):
    @wraps(methode)
    def verifiee(self, *args, **kwargs):
        self._verifier_ouverte()
        if self.compte.role != RESPONSABLE:
            raise AccesRefuseError("action reservee au responsable de la mediatheque")
        return methode(self, *args, **kwargs)
    return verifiee


def connexion_requise(methode):
    @wraps(methode)
    def verifiee(self, *args, **kwargs):
        self._verifier_ouverte()
        return methode(self, *args, **kwargs)
    return verifiee


class Session:

    def __init__(self, mediatheque, compte):
        self._m = mediatheque
        self.compte = compte
        self._ouverte = True

    # ------------------------------------------------------------- utilitaires
    @property
    def est_responsable(self):
        return self.compte.role == RESPONSABLE

    def fermer(self):
        self._ouverte = False

    def _verifier_ouverte(self):
        if not self._ouverte:
            raise AccesRefuseError("session fermee : reconnectez-vous")

    def _numero_cible(self, numero):
        """Un adherent n'agit que pour lui-meme ; le responsable pour qui il veut."""
        if self.compte.role == ADHERENT:
            if numero is not None and numero != self.compte.numero_adherent:
                raise AccesRefuseError("vous ne pouvez agir que sur votre propre compte")
            return self.compte.numero_adherent
        if numero is None:
            raise MediathequeError("numero d'adherent requis")
        self._m.adherent(numero)
        return numero

    # ---------------------------------------------------------------- communs
    @connexion_requise
    def catalogue(self, texte="", type_doc=None):
        """Liste de (document, statut) filtree par texte et type."""
        texte = texte.strip().lower()
        numero = self.compte.numero_adherent
        resultat = []
        for d in sorted(self._m):
            if type_doc and d.CLE != type_doc:
                continue
            if texte and texte not in f"{d.id} {d.titre} {d.detail}".lower():
                continue
            if self._m.disponible(d.id, numero):
                statut = "disponible"
            elif self._m._emprunt_en_cours(d.id):
                statut = "emprunte"
            else:
                statut = "reserve"
            resultat.append((d, statut))
        return resultat

    @connexion_requise
    def file_attente(self, id_document):
        return len(self._m.file_attente(id_document))

    @connexion_requise
    def mon_compte(self, numero=None, aujourdhui=None):
        numero = self._numero_cible(numero)
        aujourdhui = aujourdhui or date.today()
        self._m.actualiser_reservations(aujourdhui)
        adherent = self._m.adherent(numero)
        emprunts = []
        for e in self._m.emprunts_de(numero):
            duree = self._m[e.id_document].duree_pret_jour
            emprunts.append({
                "document": self._m[e.id_document],
                "date_emprunt": e.date_emprunt,
                "date_limite": e.date_limite(duree),
                "jours_retard": e.jours_retard(duree, aujourdhui),
            })
        reservations = []
        for r in self._m.reservations_de(numero):
            file = self._m.file_attente(r.id_document)
            reservations.append({
                "document": self._m[r.id_document],
                "statut": r.statut,
                "rang": file.index(r) + 1,
                "date_limite_retrait": r.date_limite_retrait,
            })
        return {
            "adherent": adherent,
            "emprunts": emprunts,
            "quota_restant": adherent.quota - len(emprunts),
            "reservations": reservations,
        }

    @connexion_requise
    def reserver(self, id_document, numero=None, jour=None):
        return self._m.reserver(id_document, self._numero_cible(numero), jour)

    @connexion_requise
    def annuler_reservation(self, id_document, numero=None, jour=None):
        return self._m.annuler_reservation(id_document, self._numero_cible(numero), jour)

    @connexion_requise
    def changer_mot_de_passe(self, ancien, nouveau):
        self._m.comptes.changer_mot_de_passe(self.compte.identifiant, ancien, nouveau)

    # ------------------------------------------------------------ responsable
    @responsable_requis
    def ajouter_document(self, type_doc, id_document, titre, annee, extra):
        document = Document.from_csv_row({"id": id_document, "type": type_doc,
                                          "titre": titre, "annee": annee, "extra": extra})
        self._m.ajouter_document(document)
        return document

    @responsable_requis
    def supprimer_document(self, id_document):
        return self._m.supprimer_document(id_document)

    @responsable_requis
    def adherents(self):
        return self._m.adherents

    @responsable_requis
    def ajouter_adherent(self, numero, nom, prenom, type_adherent):
        adherent = Adherent(numero, nom, prenom, type_adherent)
        self._m.ajouter_adherent(adherent)
        return adherent

    @responsable_requis
    def creer_compte(self, identifiant, mot_de_passe, role, numero_adherent=None):
        return self._m.creer_compte(identifiant, mot_de_passe, role, numero_adherent)

    @responsable_requis
    def reinitialiser_mot_de_passe(self, identifiant, nouveau):
        self._m.comptes.reinitialiser_mot_de_passe(identifiant, nouveau)

    @responsable_requis
    def enregistrer_emprunt(self, id_document, numero, jour=None):
        return self._m.emprunter(id_document, numero, jour)

    @responsable_requis
    def enregistrer_retour(self, id_document, jour=None):
        return self._m.retourner(id_document, jour)

    @responsable_requis
    def retards(self, aujourdhui=None):
        return list(retards(self._m, aujourdhui or date.today()))

    @responsable_requis
    def statistiques(self, n=5):
        return top_emprunteurs(self._m, n)

    @responsable_requis
    def sauvegarder(self):
        self._m.sauvegarder()
