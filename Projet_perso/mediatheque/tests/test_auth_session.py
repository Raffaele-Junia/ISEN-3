import inspect

import pytest

from conftest import AUJOURDHUI
from mediatheque.auth import (ADHERENT, MAX_ECHECS, RESPONSABLE, GestionComptes)
from mediatheque.exceptions import (AccesRefuseError, AuthentificationError,
                                    CompteBloqueError, MediathequeError)
from mediatheque.mediatheque import Mediatheque
from mediatheque.session import Session, ouvrir_session

MDP = "Secret123"


@pytest.fixture
def mc(m):
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


# ------------------------------------------------------------------ comptes
def test_mot_de_passe_jamais_en_clair(mc):
    compte = next(iter(mc.comptes))
    assert MDP.encode() not in compte.hash_mdp
    assert len(compte.sel) == 16
    assert MDP not in repr(compte)


def test_sels_differents_pour_meme_mot_de_passe(mc):
    hashes = {c.hash_mdp for c in mc.comptes}
    assert len(hashes) == 3


@pytest.mark.parametrize("mdp", ["court1", "sanschiffre", "12345678"])
def test_mot_de_passe_faible_refuse(m, mdp):
    with pytest.raises(MediathequeError):
        m.creer_compte("test", mdp, RESPONSABLE)


@pytest.mark.parametrize("ident", ["ab", "avec espace", "x" * 33, "é"])
def test_identifiant_invalide(m, ident):
    with pytest.raises(MediathequeError):
        m.creer_compte(ident, MDP, RESPONSABLE)


def test_compte_adherent_doit_exister_et_etre_unique(mc):
    with pytest.raises(MediathequeError):
        mc.creer_compte("x123", MDP, ADHERENT, "A999")
    with pytest.raises(MediathequeError):
        mc.creer_compte("lea2", MDP, ADHERENT, "A001")


def test_connexion_message_identique(mc):
    with pytest.raises(AuthentificationError) as e1:
        ouvrir_session(mc, "lea", "Mauvais123")
    with pytest.raises(AuthentificationError) as e2:
        ouvrir_session(mc, "inconnu", "Mauvais123")
    assert str(e1.value) == str(e2.value)


def test_identifiant_insensible_casse(mc):
    assert ouvrir_session(mc, "  LEA ", MDP).compte.identifiant == "lea"


def test_blocage_apres_echecs():
    t = [0.0]
    g = GestionComptes(horloge=lambda: t[0])
    g.creer("lea", MDP, RESPONSABLE)
    for _ in range(MAX_ECHECS):
        with pytest.raises(AuthentificationError):
            g.authentifier("lea", "Mauvais123")
    with pytest.raises(CompteBloqueError):
        g.authentifier("lea", MDP)  # meme le bon mot de passe est refuse
    t[0] += 301
    assert g.authentifier("lea", MDP).identifiant == "lea"


def test_changer_mot_de_passe(mc, lea):
    lea.changer_mot_de_passe(MDP, "Nouveau456")
    with pytest.raises(AuthentificationError):
        ouvrir_session(mc, "lea", MDP)
    ouvrir_session(mc, "lea", "Nouveau456")


def test_comptes_persistes_en_sqlite(mc, tmp_path):
    mc.sauvegarder(tmp_path / "m.db")
    m2 = Mediatheque.charger(tmp_path / "m.db")
    assert ouvrir_session(m2, "admin", MDP).est_responsable


def test_comptes_refuses_en_csv(mc, tmp_path):
    with pytest.raises(MediathequeError):
        mc.sauvegarder(tmp_path / "dossier")


# ------------------------------------------------------------------- roles
METHODES_RESPONSABLE = [
    ("ajouter_document", ("livre", "D050", "T", "2020", "A")),
    ("supprimer_document", ("D004",)),
    ("adherents", ()),
    ("ajouter_adherent", ("A050", "N", "P", "standard")),
    ("creer_compte", ("pirate", MDP, RESPONSABLE)),
    ("reinitialiser_mot_de_passe", ("admin", "Pirate123")),
    ("enregistrer_emprunt", ("D002", "A001")),
    ("enregistrer_retour", ("D001",)),
    ("retards", ()),
    ("statistiques", ()),
    ("sauvegarder", ()),
]


@pytest.mark.parametrize("nom,args", METHODES_RESPONSABLE)
def test_adherent_ne_peut_pas_faire_les_actions_admin(lea, nom, args):
    with pytest.raises(AccesRefuseError):
        getattr(lea, nom)(*args)


def test_toutes_les_methodes_publiques_sont_protegees():
    """Garde-fou : toute nouvelle methode de Session doit etre decoree."""
    for nom, fn in inspect.getmembers(Session, inspect.isfunction):
        if nom.startswith("_") or nom == "fermer":
            continue
        assert hasattr(fn, "__wrapped__"), f"Session.{nom} n'a pas de controle d'acces"


def test_adherent_ne_peut_pas_agir_pour_un_autre(lea, admin):
    admin.enregistrer_emprunt("D001", "A002", AUJOURDHUI)
    with pytest.raises(AccesRefuseError):
        lea.reserver("D001", numero="A002")
    with pytest.raises(AccesRefuseError):
        lea.mon_compte(numero="A002")
    lea.reserver("D001", jour=AUJOURDHUI)
    assert lea.mon_compte(aujourdhui=AUJOURDHUI)["reservations"][0]["rang"] == 1


def test_session_fermee(lea):
    lea.fermer()
    with pytest.raises(AccesRefuseError):
        lea.catalogue()


# --------------------------------------------------------------- parcours
def test_parcours_complet(mc, admin, lea):
    admin.enregistrer_emprunt("D001", "A002", AUJOURDHUI)
    statuts = dict((d.id, s) for d, s in lea.catalogue())
    assert statuts["D001"] == "emprunte" and statuts["D002"] == "disponible"
    assert [d.id for d, _ in lea.catalogue("python")] == ["D001"]
    assert [d.id for d, _ in lea.catalogue(type_doc="dvd")] == ["D002"]

    lea.reserver("D001", jour=AUJOURDHUI)
    admin.enregistrer_retour("D001", AUJOURDHUI)
    assert dict((d.id, s) for d, s in lea.catalogue())["D001"] == "disponible"
    hugo = ouvrir_session(mc, "hugo", MDP)
    assert dict((d.id, s) for d, s in hugo.catalogue())["D001"] == "reserve"

    admin.enregistrer_emprunt("D001", "A001", AUJOURDHUI)
    compte = lea.mon_compte(aujourdhui=AUJOURDHUI)
    assert [e["document"].id for e in compte["emprunts"]] == ["D001"]
    assert compte["quota_restant"] == 2 and compte["reservations"] == []


def test_admin_ajoute_document_et_adherent(admin):
    doc = admin.ajouter_document("dvd", "D050", "Alien", "1979", "117")
    assert doc.duree_min == 117
    admin.ajouter_adherent("A050", "Nom", "Prenom", "premium")
    admin.creer_compte("nouveau", MDP, ADHERENT, "A050")
    admin.supprimer_document("D050")


def test_suppression_document_avec_historique_refusee(admin):
    admin.enregistrer_emprunt("D001", "A001", AUJOURDHUI)
    with pytest.raises(MediathequeError):
        admin.supprimer_document("D001")
