"""Session utilisateur : SEULE porte d'entree de l'interface graphique.

Chaque operation verifie le role du compte connecte ici, dans la couche
metier. Masquer un bouton dans l'interface ne suffit jamais.
- adherent    : consulte le catalogue et SON compte, reserve / annule pour LUI.
- responsable : tout, y compris agir pour un adherent donne.

Les objets renvoyes (documents, adherent) sont des COPIES : les modifier n'a
aucun effet sur l'etat metier. Le compte de la session est immuable.
"""
import re
from copy import copy
from datetime import date
from functools import wraps

from .adherents import Adherent
from .auth import ADHERENT, RESPONSABLE
from .documents import Document
from . import recommandations
from .exceptions import AccesRefuseError, DocumentInconnuError, MediathequeError
from .rapports import retards, top_emprunteurs


_FORMAT_ID_DOCUMENT = re.compile(r"D\d+")
_JETON = object()  # seul ouvrir_session peut construire une Session (S4)


def ouvrir_session(mediatheque, identifiant, mot_de_passe):
    compte = mediatheque.comptes.authentifier(identifiant, mot_de_passe)
    return Session(mediatheque, compte, _jeton=_JETON)


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

    def __init__(self, mediatheque, compte, *, _jeton=None):
        if _jeton is not _JETON:
            raise AccesRefuseError("une session s'ouvre uniquement par ouvrir_session()")
        self._m = mediatheque
        self._compte = compte
        self._ouverte = True

    @property
    def compte(self):
        """Compte connecte (immuable, non reaffectable)."""
        return self._compte

    # ------------------------------------------------------------- utilitaires
    @property
    def est_responsable(self):
        return self.compte.role == RESPONSABLE

    def fermer(self):
        self._ouverte = False

    def _verifier_ouverte(self):
        if not self._ouverte:
            raise AccesRefuseError("session fermee : reconnectez-vous")
        # Revocation : compte supprime, ou remplace (role, numero, mot de passe
        # reinitialise...) depuis l'ouverture de la session.
        if self._m.comptes.get(self._compte.identifiant) is not self._compte:
            self._ouverte = False
            raise AccesRefuseError("session revoquee : reconnectez-vous")

    def _jour(self, jour):
        """Seul le responsable peut antidater ou postdater une operation (S1)."""
        if jour is not None and not self.est_responsable:
            raise AccesRefuseError("la date est fixee par le systeme")
        return jour or date.today()

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

    def _statut(self, id_document):
        if self._m.disponible(id_document, self.compte.numero_adherent):
            return "disponible"
        if self._m._emprunt_en_cours(id_document):
            return "emprunte"
        return "reserve"

    # ---------------------------------------------------------------- communs
    @connexion_requise
    def catalogue(self, texte="", type_doc=None, genre=None):
        """Liste de (document, statut) filtree par texte, type et genre.
        Le texte cherche dans l'identifiant, le titre, le detail, le genre et les themes."""
        texte = texte.strip().lower()
        resultat = []
        for d in sorted(self._m):
            if type_doc and d.CLE != type_doc:
                continue
            if genre and d.genre != genre:
                continue
            if texte and texte not in " ".join(
                    (d.id, d.titre, str(d.detail), d.genre, *d.themes)).lower():
                continue
            resultat.append((copy(d), self._statut(d.id)))
        return resultat

    @connexion_requise
    def genres(self):
        """Genres presents dans le fonds, avec leur nombre de documents."""
        compteur = {}
        for d in self._m:
            if d.genre:
                compteur[d.genre] = compteur.get(d.genre, 0) + 1
        return sorted(compteur.items())

    @connexion_requise
    def fiche(self, id_document):
        """Tout ce qu'il faut pour la page d'un document.

        Le lecteur voit la date de retour prevue d'un document sorti, jamais
        QUI l'a emprunte. Le responsable voit en plus l'historique des prets."""
        if id_document not in self._m:
            raise DocumentInconnuError(id_document)
        d = self._m[id_document]
        en_cours = self._m._emprunt_en_cours(id_document)
        fiche = {
            "document": copy(d),
            "statut": self._statut(id_document),
            "attente": len(self._m.file_attente(id_document)),
            "retour_prevu": en_cours.date_limite(d.duree_pret_jour) if en_cours else None,
            "nb_prets": sum(1 for e in self._m.emprunts if e.id_document == id_document),
            "meme_createur": [(copy(x), self._statut(x.id)) for x in sorted(self._m)
                              if d.createur and x.createur == d.createur and x.id != d.id][:6],
            "historique": None,
        }
        if self.est_responsable:
            fiche["historique"] = [
                {"numero": e.numero_adherent, "nom": self._m.adherent(e.numero_adherent).nom_complet,
                 "date_emprunt": e.date_emprunt, "date_retour": e.date_retour}
                for e in reversed(self._m.emprunts) if e.id_document == id_document][:15]
        return fiche

    @connexion_requise
    def similaires(self, id_document, n=6):
        """Documents dans la meme veine : liste de (document, statut)."""
        if id_document not in self._m:
            raise DocumentInconnuError(id_document)
        exclure = {x.id for x, _ in self.fiche(id_document)["meme_createur"]}
        return [(copy(x), self._statut(x.id))
                for x in recommandations.similaires(self._m, id_document, n, exclure,
                                                          numero=self.compte.numero_adherent)]

    @connexion_requise
    def pour_moi(self, numero=None, n=8):
        """Suggestions personnelles : liste de dicts {document, statut, raison}.
        Un adherent ne peut obtenir que les siennes."""
        numero = self._numero_cible(numero)
        return [{"document": copy(d), "statut": self._statut(d.id), "raison": raison}
                for d, raison in recommandations.pour_adherent(self._m, numero, n)]

    @connexion_requise
    def file_attente(self, id_document):
        return len(self._m.file_attente(id_document))

    @connexion_requise
    def mon_compte(self, numero=None, aujourdhui=None):
        numero = self._numero_cible(numero)
        aujourdhui = self._jour(aujourdhui)
        self._m.actualiser_reservations(aujourdhui)
        adherent = self._m.adherent(numero)
        emprunts = []
        for e in self._m.emprunts_de(numero):
            duree = self._m[e.id_document].duree_pret_jour
            emprunts.append({
                "document": copy(self._m[e.id_document]),
                "date_emprunt": e.date_emprunt,
                "date_limite": e.date_limite(duree),
                "jours_retard": e.jours_retard(duree, aujourdhui),
            })
        reservations = []
        for r in self._m.reservations_de(numero):
            file = self._m.file_attente(r.id_document)
            reservations.append({
                "document": copy(self._m[r.id_document]),
                "statut": r.statut,
                "rang": file.index(r) + 1,
                "date_limite_retrait": r.date_limite_retrait,
            })
        return {
            "adherent": copy(adherent),
            "emprunts": emprunts,
            "quota_restant": adherent.quota - len(emprunts),
            "reservations": reservations,
        }

    @connexion_requise
    def reserver(self, id_document, numero=None, jour=None):
        return self._m.reserver(id_document, self._numero_cible(numero),
                                self._jour(jour))

    @connexion_requise
    def annuler_reservation(self, id_document, numero=None, jour=None):
        return self._m.annuler_reservation(id_document, self._numero_cible(numero),
                                           self._jour(jour))

    @connexion_requise
    def changer_mot_de_passe(self, ancien, nouveau):
        self._compte = self._m.comptes.changer_mot_de_passe(
            self.compte.identifiant, ancien, nouveau)

    # ------------------------------------------------------------ responsable
    @responsable_requis
    def ajouter_document(self, type_doc, id_document, titre, annee, extra, **fiche):
        """`fiche` : genre, themes, resume, editeur, pages, isbn, public (optionnels)."""
        if not isinstance(id_document, str) or not _FORMAT_ID_DOCUMENT.fullmatch(id_document):
            raise MediathequeError(
                f"identifiant de document invalide : {id_document!r} (attendu : D suivi de chiffres)")
        document = Document.from_csv_row({"id": id_document, "type": type_doc,
                                          "titre": titre, "annee": annee, "extra": extra})
        document.completer_fiche(**fiche)
        self._m.ajouter_document(document)
        return document

    @responsable_requis
    def supprimer_document(self, id_document):
        return self._m.supprimer_document(id_document)

    @responsable_requis
    def adherents(self):
        return self._m.adherents

    @responsable_requis
    def ajouter_adherent(self, numero, nom, prenom, type_adherent,
                         identifiant=None, mot_de_passe=None):
        """Avec `identifiant`, cree aussi son compte adherent. Tout est valide
        AVANT la premiere modification (W4) : pas d'adherent cree sans compte."""
        adherent = Adherent(numero, nom, prenom, type_adherent)  # valide
        if identifiant:
            self._m.comptes.verifier_nouveau(identifiant, mot_de_passe or "")
        self._m.ajouter_adherent(adherent)
        if identifiant:
            self._m.creer_compte(identifiant, mot_de_passe, ADHERENT, numero)
        return adherent

    @responsable_requis
    def creer_compte(self, identifiant, mot_de_passe, role, numero_adherent=None):
        return self._m.creer_compte(identifiant, mot_de_passe, role, numero_adherent)

    @responsable_requis
    def reinitialiser_mot_de_passe(self, identifiant, nouveau):
        compte = self._m.comptes.reinitialiser_mot_de_passe(identifiant, nouveau)
        if compte.identifiant == self._compte.identifiant:
            self._compte = compte  # sa propre session reste valide

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
