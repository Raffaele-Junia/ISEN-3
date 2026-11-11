"""Session utilisateur : SEULE porte d'entree de l'interface graphique.

Chaque operation verifie le role du compte connecte ici, dans la couche
metier. Masquer un bouton dans l'interface ne suffit jamais.
- adherent    : consulte le catalogue et SON compte, reserve / annule pour LUI.
- responsable : tout, y compris agir pour un adherent donne.

Les objets renvoyes (documents, adherents, emprunts, reservations) sont des
COPIES : les modifier n'a aucun effet sur l'etat metier (Z5). Les comptes et
les entrees du journal sont immuables (frozen).
"""
import re
import unicodedata
from copy import copy
from datetime import date
from functools import wraps

from .adherents import Adherent
from .auth import ADHERENT, RESPONSABLE
from .documents import CHAMPS_FICHE, Document
from . import recommandations
from .exceptions import AccesRefuseError, DocumentInconnuError, MediathequeError
from .rapports import retards, top_emprunteurs


_FORMAT_ID_DOCUMENT = re.compile(r"D\d+")


def _sans_accents(texte):
    """« Émile Zola » -> « emile zola » (recherche tolerante)."""
    return unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode().lower()


# Mots courants des lecteurs -> termes du catalogue (sans accents). Un mot de la
# recherche correspond si l'UNE de ses variantes apparait (N10).
SYNONYMES = {
    "sf": ("science-fiction",),
    "scifi": ("science-fiction",),
    "bd": ("bande dessinee",),
    "comics": ("bande dessinee",),
    "manga": ("bande dessinee", "manga"),
    "anime": ("animation",),
    "animes": ("animation",),
    "dessin": ("dessin", "animation"),
    "polar": ("policier", "polar", "thriller"),
    "policier": ("policier", "thriller"),
    "film": ("film", "dvd"),
    "films": ("film", "dvd"),
    "magazine": ("presse", "magazine", "revue"),
    "journal": ("presse", "journal"),
    "enfant": ("jeunesse", "enfant"),
    "enfants": ("jeunesse", "enfant"),
    "jeunesse": ("jeunesse",),
    "ado": ("ado",),
    "ados": ("ado",),
    "python": ("python",),
}


def _ponctuation(texte):
    """Tirets, apostrophes, ponctuation -> espaces (« science-fiction » = « science fiction »)."""
    return " ".join(re.sub(r"[^a-z0-9]+", " ", texte).split())


def _variantes(mot):
    """Les variantes d'un mot ; un mot de 1-2 lettres sans synonyme n'est cherche
    qu'en mot entier (evite « sf » trouve au milieu de « transformer »)."""
    if mot in SYNONYMES:
        return SYNONYMES[mot]
    return (f" {mot} ",) if len(mot) <= 2 else (mot,)
_JETON = object()  # seul ouvrir_session peut construire une Session (S4)


def ouvrir_session(mediatheque, identifiant, mot_de_passe):
    compte = mediatheque.comptes.authentifier(identifiant, mot_de_passe)
    if compte.role == RESPONSABLE:  # tracer les connexions du personnel
        mediatheque.journaliser(compte.identifiant, "connexion")
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

    def _noter(self, action, cible="", detail=""):
        """Trace une action reussie du personnel (jamais de mot de passe)."""
        self._m.journaliser(self.compte.identifiant, action, cible, detail)

    def _retour_prevu(self, id_document):
        """Date limite du pret en cours (jamais QUI l'a emprunte), ou None."""
        e = self._m._emprunt_en_cours(id_document)
        return e.date_limite(self._m[id_document].duree_pret_jour) if e else None

    def _statut(self, id_document):
        if self._m.disponible(id_document, self.compte.numero_adherent):
            return "disponible"
        if self._m._emprunt_en_cours(id_document):
            return "emprunte"
        return "reserve"

    # ---------------------------------------------------------------- communs
    @connexion_requise
    def catalogue(self, texte="", type_doc=None, genre=None, public=None):
        """Liste de (document, statut) filtree par texte, type, genre et public.

        La recherche ignore accents et majuscules (« emile zola », « miserables »),
        et chaque mot doit apparaitre dans l'identifiant, le titre, l'auteur ou le
        detail, le genre, les themes, le resume, l'editeur ou le public."""
        mots = [tuple(_ponctuation(v) if v.strip() == v else v for v in _variantes(m))
                for m in _ponctuation(_sans_accents(texte)).split()]
        resultat = []
        for d in sorted(self._m):
            if type_doc and d.CLE != type_doc:
                continue
            if genre and d.genre != genre:
                continue
            if public and d.public != public:
                continue
            if mots:
                botte = " " + _ponctuation(_sans_accents(" ".join((
                    d.id, d.titre, str(d.detail), d.createur, d.genre, d.TYPE, *d.themes, d.resume,
                    d.editeur, d.public)))) + " "
                if not all(any(v in botte for v in variantes) for variantes in mots):
                    continue
            resultat.append((copy(d), self._statut(d.id)))
        return resultat

    @connexion_requise
    def compteurs(self):
        """(nombre de documents, nombre disponibles pour ce lecteur) : le bandeau
        du catalogue sans recopier tout le fonds (Z2)."""
        dispo = sum(1 for d in self._m if self._statut(d.id) == "disponible")
        return len(self._m), dispo

    @connexion_requise
    def publics(self):
        """Publics presents dans le fonds, avec leur nombre de documents."""
        compteur = {}
        for d in self._m:
            if d.public:
                compteur[d.public] = compteur.get(d.public, 0) + 1
        return sorted(compteur.items())

    @connexion_requise
    def genres(self, type_doc=None, public=None):
        """Genres presents dans le fonds (pour un type et un public donnes),
        avec leur nombre de documents."""
        compteur = {}
        for d in self._m:
            if (type_doc and d.CLE != type_doc) or (public and d.public != public):
                continue
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
        d = self._m[id_document]
        exclure = {x.id for x in self._m if d.createur and x.createur == d.createur}
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
                "retour_prevu": self._retour_prevu(r.id_document),  # C6
            })
        return {
            "adherent": copy(adherent),
            "emprunts": emprunts,
            "quota_restant": adherent.quota - len(emprunts),
            "reservations": reservations,
        }

    @connexion_requise
    def reserver(self, id_document, numero=None, jour=None):
        return copy(self._m.reserver(id_document, self._numero_cible(numero),
                                     self._jour(jour)))

    @connexion_requise
    def annuler_reservation(self, id_document, numero=None, jour=None):
        return copy(self._m.annuler_reservation(id_document, self._numero_cible(numero),
                                                self._jour(jour)))

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
                f"N° d'inventaire invalide : {id_document!r} (attendu : D suivi de chiffres, ex. D137).")
        if not str(annee).strip().isdigit():
            raise MediathequeError("L'année doit être un nombre, par exemple 2024.")
        try:
            document = Document.from_csv_row({"id": id_document, "type": type_doc,
                                              "titre": titre, "annee": annee, "extra": extra})
        except ValueError:
            raise MediathequeError(
                "Pour un film, indiquez la durée en minutes (par exemple 125) ; "
                "pour une revue, le numéro (par exemple 1296).") from None
        inconnus = set(fiche) - set(CHAMPS_FICHE)
        if inconnus:  # erreur de programmation, pas de saisie : on la laisse remonter
            raise ValueError(f"champ de fiche inconnu : {', '.join(sorted(inconnus))}")
        try:
            document.completer_fiche(**fiche)
        except ValueError as e:
            raise MediathequeError(f"Fiche invalide : {e}.") from None
        self._m.ajouter_document(document)
        self._noter("ajout_document", document.id, f"« {document.titre} » ({document.TYPE})")
        return copy(document)

    @responsable_requis
    def supprimer_document(self, id_document):
        d = self._m.supprimer_document(id_document)
        self._noter("retrait_document", d.id, f"« {d.titre} »")
        return copy(d)

    @responsable_requis
    def adherents(self):
        return tuple(copy(a) for a in self._m.adherents)  # copies (Z5)

    @responsable_requis
    def ajouter_adherent(self, numero, nom, prenom, type_adherent,
                         identifiant=None, mot_de_passe=None):
        """Avec `identifiant`, cree aussi son compte adherent. Tout est valide
        AVANT la premiere modification (W4) : pas d'adherent cree sans compte."""
        adherent = Adherent(numero, nom, prenom, type_adherent)  # valide
        if identifiant:
            self._m.comptes.verifier_nouveau(identifiant, mot_de_passe or "")
        self._m.ajouter_adherent(adherent)
        self._noter("ajout_lecteur", numero, f"{adherent.nom_complet}, carte {type_adherent}")
        if identifiant:
            c = self._m.creer_compte(identifiant, mot_de_passe, ADHERENT, numero)
            self._noter("creation_compte", c.identifiant, f"compte lecteur de {numero}")
        return copy(adherent)

    @responsable_requis
    def creer_compte(self, identifiant, mot_de_passe, role, numero_adherent=None):
        c = self._m.creer_compte(identifiant, mot_de_passe, role, numero_adherent)
        self._noter("creation_compte", c.identifiant,
                    f"compte {role}" + (f" de {numero_adherent}" if numero_adherent else ""))
        return c

    @responsable_requis
    def reinitialiser_mot_de_passe(self, identifiant, nouveau):
        compte = self._m.comptes.reinitialiser_mot_de_passe(identifiant, nouveau)
        self._noter("reinit_mdp", compte.identifiant)
        if compte.identifiant == self._compte.identifiant:
            self._compte = compte  # sa propre session reste valide

    @responsable_requis
    def enregistrer_emprunt(self, id_document, numero, jour=None):
        e = self._m.emprunter(id_document, numero, jour)
        self._noter("pret", e.id_document,
                    f"« {self._m[e.id_document].titre} » à {self._m.adherent(numero).nom_complet} ({numero})")
        return copy(e)

    @responsable_requis
    def enregistrer_retour(self, id_document, jour=None, numero=None):
        """Avec `numero` (retour depuis la fiche d'un lecteur), refuse si le pret
        en cours n'est pas chez ce lecteur : page perimee, double clic (Z4)."""
        if numero is not None:
            en_cours = self._m._emprunt_en_cours(id_document)
            if en_cours is not None and en_cours.numero_adherent != numero:
                raise MediathequeError("Ce document n'est pas chez ce lecteur.")
        e = self._m.retourner(id_document, jour)
        self._noter("retour", e.id_document,
                    f"« {self._m[e.id_document].titre} », rendu par {e.numero_adherent}")
        return copy(e)

    @responsable_requis
    def fiche_lecteur(self, numero, aujourdhui=None):
        """Vue du personnel sur un lecteur : sa carte (comme mon_compte), tout son
        historique de prets et son compte en ligne (identifiant seulement)."""
        compte = self.mon_compte(numero, aujourdhui)
        historique = []
        for e in reversed(self._m.emprunts):
            if e.numero_adherent == numero:
                d = self._m[e.id_document]
                historique.append({"document": copy(d), "date_emprunt": e.date_emprunt,
                                   "date_retour": e.date_retour,
                                   "jours_retard": e.jours_retard(d.duree_pret_jour,
                                                                  aujourdhui or date.today())})
        c = self._m.comptes.compte_de_adherent(numero)
        return {**compte, "historique": historique,
                "identifiant": c.identifiant if c else None}

    @responsable_requis
    def modifier_lecteur(self, numero, nom, prenom, type_adherent):
        try:
            changements = self._m.modifier_adherent(numero, nom, prenom, type_adherent)
        except ValueError:
            raise MediathequeError("Formule inconnue : choisissez standard ou premium.") from None
        if changements:
            self._noter("modif_lecteur", numero, " ; ".join(changements))
        return changements

    @responsable_requis
    def annuler_reservation_pour(self, id_document, numero):
        r = self._m.annuler_reservation(id_document, self._numero_cible(numero))
        self._noter("annul_reservation", id_document,
                    f"« {self._m[id_document].titre} » pour {numero}")
        return copy(r)

    @responsable_requis
    def journal(self, page=1, par_page=50, action=None):
        """Entrees du journal, des plus recentes aux plus anciennes : (entrees, total)."""
        entrees = [j for j in reversed(self._m.journal) if not action or j.action == action]
        page = max(1, int(page))
        return entrees[(page - 1) * par_page: page * par_page], len(entrees)

    @responsable_requis
    def mis_de_cote_pour(self, id_document):
        """Lecteur (Adherent, copie) pour qui le document est mis de cote, ou None."""
        r = self._m._mise_de_cote(id_document)
        return copy(self._m.adherent(r.numero_adherent)) if r else None

    @responsable_requis
    def retards(self, aujourdhui=None):
        return [(copy(e), copy(d), j) for e, d, j in retards(self._m, aujourdhui or date.today())]

    @responsable_requis
    def statistiques(self, n=5):
        return top_emprunteurs(self._m, n)

    @responsable_requis
    def sauvegarder(self):
        self._m.sauvegarder()
