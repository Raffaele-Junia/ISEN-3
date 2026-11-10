"""Audit securite P1 : controle d'acces via Session.

Convention : un test marque xfail(strict=True) PROUVE une faille ouverte.
Quand la faille sera corrigee, il passera et pytest le signalera (XPASS strict
= echec) : il suffira alors de retirer le marqueur.
"""
from datetime import date, timedelta

import pytest

from mediatheque.adherents import Adherent
from mediatheque.auth import ADHERENT, RESPONSABLE, Compte
from mediatheque.exceptions import AccesRefuseError, MediathequeError
from mediatheque.reservation import DISPONIBLE
from mediatheque.session import Session, ouvrir_session

MDP = "Secret123"


@pytest.fixture
def mc(m):
    m.ajouter_adherent(Adherent("A003", "Petit", "Ines", "standard"))
    m.creer_compte("admin", MDP, RESPONSABLE)
    m.creer_compte("lea", MDP, ADHERENT, "A001")
    m.creer_compte("hugo", MDP, ADHERENT, "A002")
    return m


@pytest.fixture
def admin(mc):
    return ouvrir_session(mc, "admin", MDP)


@pytest.fixture
def lea(mc):
    return ouvrir_session(mc, "lea", MDP)


@pytest.fixture
def hugo(mc):
    return ouvrir_session(mc, "hugo", MDP)


# ------------------------------------------------- protections verifiees (OK)
@pytest.mark.parametrize("numero", ["A002", "A001 ", " A001", "a001", ""])
@pytest.mark.parametrize("methode", ["reserver", "annuler_reservation"])
def test_adherent_ne_cible_que_son_propre_numero(lea, numero, methode):
    with pytest.raises(AccesRefuseError):
        getattr(lea, methode)("D001", numero=numero)


@pytest.mark.parametrize("numero", ["A002", "A001 ", "a001"])
def test_adherent_ne_consulte_pas_un_autre_compte(lea, numero):
    with pytest.raises(AccesRefuseError):
        lea.mon_compte(numero)


def test_responsable_ne_cible_pas_un_numero_inexistant(admin):
    with pytest.raises(MediathequeError):
        admin.reserver("D001", numero="A999")


# --------------------------------------------- S1 : date imposee par l'appelant
def _mise_de_cote_pour_lea(admin, lea, hugo):
    """D001 emprunte par A003, reserve par lea puis hugo, rendu aujourd'hui :
    il est mis de cote pour lea pendant 3 jours."""
    aujourdhui = date.today()
    admin.enregistrer_emprunt("D001", "A003", aujourdhui - timedelta(days=1))
    admin.enregistrer_emprunt("D002", "A003", aujourdhui - timedelta(days=1))
    resa_lea = lea.reserver("D001")  # un adherent ne choisit pas la date (S1)
    hugo.reserver("D001")
    admin.enregistrer_retour("D001", aujourdhui)
    assert resa_lea.statut == DISPONIBLE
    return resa_lea


def test_s1_adherent_ne_fait_pas_expirer_la_reservation_d_un_autre(admin, lea, hugo):
    resa_lea = _mise_de_cote_pour_lea(admin, lea, hugo)
    try:
        hugo.mon_compte(aujourdhui=date.today() + timedelta(days=365))
    except AccesRefuseError:
        pass
    assert resa_lea.statut == DISPONIBLE


def test_s1_reserver_avec_date_future_sans_effet_sur_les_autres(admin, lea, hugo):
    resa_lea = _mise_de_cote_pour_lea(admin, lea, hugo)
    try:
        hugo.reserver("D002", jour=date.today() + timedelta(days=365))
    except (AccesRefuseError, MediathequeError):
        pass
    assert resa_lea.statut == DISPONIBLE


@pytest.mark.parametrize("appel", [
    lambda s: s.mon_compte(aujourdhui=date.today()),
    lambda s: s.reserver("D001", jour=date.today()),
    lambda s: s.annuler_reservation("D001", jour=date.today()),
])
def test_s1_adherent_ne_peut_pas_passer_de_date(lea, appel):
    with pytest.raises(AccesRefuseError):
        appel(lea)


def test_s1_responsable_peut_passer_une_date(admin):
    admin.enregistrer_emprunt("D001", "A003", date.today())
    resa = admin.reserver("D001", numero="A001", jour=date.today() - timedelta(days=1))
    assert resa.date_reservation == date.today() - timedelta(days=1)
    assert admin.mon_compte("A001", aujourdhui=date.today())["reservations"]


# ------------------------------------ S2 : objets metier mutables exposes
def test_s2_adherent_ne_peut_pas_s_auto_promouvoir(mc, lea):
    try:
        lea.compte.role = RESPONSABLE
    except AttributeError:  # dataclass(frozen=True) -> FrozenInstanceError
        pass
    with pytest.raises(AccesRefuseError):
        lea.adherents()
    stocke = next(c for c in mc.comptes if c.identifiant == "lea")
    assert stocke.role == ADHERENT


def test_s2_adherent_ne_peut_pas_changer_de_numero(mc, lea):
    try:
        lea.compte.numero_adherent = "A002"
    except AttributeError:
        pass
    with pytest.raises(AccesRefuseError):
        lea.mon_compte("A002")


def test_s2_mon_compte_ne_permet_pas_de_changer_son_type(mc, lea):
    try:
        lea.mon_compte()["adherent"].type = "premium"
    except (AttributeError, TypeError):
        pass
    assert mc.adherent("A001").type == "standard"


def test_s2_catalogue_ne_permet_pas_de_modifier_un_document(mc, lea):
    document, _ = next(iter(lea.catalogue("Fluent")))
    try:
        document.titre = "pirate"
    except (AttributeError, TypeError):
        pass
    assert mc["D001"].titre == "Fluent Python"


def test_s2_compte_de_session_non_reaffectable(lea, mc):
    with pytest.raises(AttributeError):
        lea.compte = next(c for c in mc.comptes if c.identifiant == "admin")
    assert not lea.est_responsable


def test_s2_documents_de_mon_compte_sont_des_copies(mc, admin, lea):
    admin.enregistrer_emprunt("D001", "A001", date.today())
    lea.mon_compte()["emprunts"][0]["document"].titre = "pirate"
    assert mc["D001"].titre == "Fluent Python"


def test_s2_changement_de_mot_de_passe_remplace_le_compte(mc, lea):
    ancien = lea.compte
    lea.changer_mot_de_passe(MDP, "Nouveau456")
    assert lea.compte is not ancien and lea.compte.role == ADHERENT
    assert ouvrir_session(mc, "lea", "Nouveau456").compte.numero_adherent == "A001"


# ------------------------- S4 : Session falsifiable et non revocable
def test_s4_session_forgee_refusee(mc):
    faux = Compte("pirate", b"x" * 32, b"y" * 16, RESPONSABLE)
    with pytest.raises((AccesRefuseError, TypeError, ValueError)):
        Session(mc, faux).adherents()


def test_s4_session_revoquee_apres_suppression_du_compte(mc, lea):
    mc.comptes.supprimer("lea")
    with pytest.raises(AccesRefuseError):
        lea.mon_compte()


def test_s4_session_forgee_avec_un_vrai_compte_refusee(mc):
    vrai = mc.comptes.get("admin")
    with pytest.raises(AccesRefuseError):
        Session(mc, vrai)


def test_s4_session_revoquee_apres_reinitialisation_du_mot_de_passe(admin, lea):
    admin.reinitialiser_mot_de_passe("lea", "Neuf12345")
    with pytest.raises(AccesRefuseError):
        lea.catalogue()
    admin.reinitialiser_mot_de_passe("admin", "Neuf12345")
    assert admin.adherents()  # sa propre session reste ouverte


def test_s4_session_conservee_apres_son_propre_changement_de_mot_de_passe(lea):
    lea.changer_mot_de_passe(MDP, "Nouveau456")
    assert lea.mon_compte()["adherent"].numero == "A001"
