"""Journal des actions du personnel, fiche lecteur et pagination."""
import re

import pytest

from conftest import AUJOURDHUI
from mediatheque.auth import ADHERENT, RESPONSABLE
from mediatheque.exceptions import AccesRefuseError, MediathequeError
from mediatheque.mediatheque import Mediatheque
from mediatheque.session import ouvrir_session
from mediatheque.web import create_app

MDP = "Secret123"


@pytest.fixture
def mj(m):
    m.creer_compte("admin", MDP, RESPONSABLE)
    m.creer_compte("lea", MDP, ADHERENT, "A001")
    return m


# ------------------------------------------------------------- metier
def test_actions_du_personnel_journalisees(mj, tmp_path):
    admin = ouvrir_session(mj, "admin", MDP)
    admin.enregistrer_emprunt("D001", "A002", AUJOURDHUI)
    admin.enregistrer_retour("D001", AUJOURDHUI)
    admin.modifier_lecteur("A001", "Martin", "Lea", "premium")
    admin.reinitialiser_mot_de_passe("lea", "Nouveau456")
    actions = [j.action for j in mj.journal]
    assert actions == ["connexion", "pret", "retour", "modif_lecteur", "reinit_mdp"]
    assert all(j.acteur == "admin" for j in mj.journal)
    assert "standard → premium" in mj.journal[3].detail
    # jamais de mot de passe dans le journal
    assert not any("Nouveau456" in f"{j.cible} {j.detail}" for j in mj.journal)
    # persistance SQLite
    mj.sauvegarder(tmp_path / "m.db")
    assert [j.action for j in Mediatheque.charger(tmp_path / "m.db").journal] == actions


def test_journal_et_fiche_reserves_au_personnel(mj):
    lea = ouvrir_session(mj, "lea", MDP)
    for appel in (lambda: lea.journal(), lambda: lea.fiche_lecteur("A002"),
                  lambda: lea.modifier_lecteur("A001", "M", "L", "premium")):
        with pytest.raises(AccesRefuseError):
            appel()
    assert [j.action for j in mj.journal] == []   # un lecteur n'est pas journalise


def test_modifier_lecteur_valide(mj):
    admin = ouvrir_session(mj, "admin", MDP)
    with pytest.raises(MediathequeError):
        admin.modifier_lecteur("A001", "Martin", "Lea", "vip")
    with pytest.raises(MediathequeError):
        admin.modifier_lecteur("A001", "", "Lea", "standard")
    assert admin.modifier_lecteur("A001", "Martin", "Lea", "standard") == []  # rien change


def test_fiche_lecteur_contenu(mj):
    admin = ouvrir_session(mj, "admin", MDP)
    admin.enregistrer_emprunt("D001", "A001", AUJOURDHUI)
    f = admin.fiche_lecteur("A001", AUJOURDHUI)
    assert f["identifiant"] == "lea"
    assert [e["document"].id for e in f["emprunts"]] == ["D001"]
    assert f["historique"][0]["document"].id == "D001"


def test_journal_pagine_du_plus_recent(mj):
    admin = ouvrir_session(mj, "admin", MDP)
    for _ in range(3):
        admin.enregistrer_emprunt("D002", "A002", AUJOURDHUI)
        admin.enregistrer_retour("D002", AUJOURDHUI)
    page1, total = admin.journal(page=1, par_page=4)
    assert total == 7 and len(page1) == 4 and page1[0].action == "retour"
    assert admin.journal(page=2, par_page=4)[0][-1].action == "connexion"
    assert len(admin.journal(action="pret")[0]) == 3


# ---------------------------------------------------------------- web
@pytest.fixture
def web(mj, tmp_path):
    mj.sauvegarder(tmp_path / "m.db")
    return create_app(tmp_path / "m.db", secret_key="t", testing=True)


def _client(app, ident):
    c = app.test_client()
    page = c.get("/connexion").get_data(as_text=True)
    jeton = re.search(r'name="csrf" value="([^"]+)"', page).group(1)
    c.post("/connexion", data={"identifiant": ident, "mot_de_passe": MDP, "csrf": jeton})
    return c


def _post(c, url, page, **data):
    jeton = re.search(r'name="csrf" value="([^"]+)"', c.get(page).get_data(as_text=True)).group(1)
    return c.post(url, data={**data, "csrf": jeton})


def test_pages_personnel_interdites_au_lecteur(web):
    lea = _client(web, "lea")
    for url in ("/admin/journal", "/admin/lecteurs/A001"):
        assert lea.get(url).status_code == 403
    assert _post(lea, "/admin/lecteurs/A001/modifier", "/catalogue",
                 nom="X", prenom="Y", type="premium").status_code == 403


def test_fiche_lecteur_web_et_changement_de_formule(web):
    admin = _client(web, "admin")
    page = admin.get("/admin/lecteurs/A001").get_data(as_text=True)
    assert "Lea MARTIN" in page and "Modifier la fiche" in page and "lea" in page
    _post(admin, "/admin/lecteurs/A001/modifier", "/admin/lecteurs/A001",
          nom="Martin", prenom="Léa", type="premium")
    page = admin.get("/admin/lecteurs/A001").get_data(as_text=True)
    assert "premium : 6 documents" in page and "Fiche mise à jour" in page
    assert "Fiche lecteur modifiée" in admin.get("/admin/journal").get_data(as_text=True)
    assert admin.get("/admin/lecteurs/A999").status_code == 404
    assert admin.get("/admin/lecteurs/x").status_code == 404


def test_lien_vers_la_fiche_depuis_la_gestion(web):
    admin = _client(web, "admin")
    page = admin.get("/admin/gestion?onglet=adherents").get_data(as_text=True)
    assert 'href="/admin/lecteurs/A001"' in page


def test_pagination_du_catalogue(tmp_path, mj):
    from mediatheque.documents import Livre
    for i in range(10, 40):
        mj.ajouter_document(Livre(f"D0{i}", f"Livre {i}", 2000, "Auteur"))
    mj.sauvegarder(tmp_path / "gros.db")
    app = create_app(tmp_path / "gros.db", secret_key="t", testing=True)
    lea = _client(app, "lea")
    p1 = lea.get("/catalogue").get_data(as_text=True)
    assert "Documents 1 à 24 sur 34" in p1 and 'rel="next"' in p1
    p2 = lea.get("/catalogue?page=2").get_data(as_text=True)
    assert "Documents 25 à 34 sur 34" in p2 and 'rel="prev"' in p2
    assert lea.get("/catalogue?page=999").status_code == 200   # bornee, pas d'erreur
    assert lea.get("/catalogue?page=abc").status_code == 200


def test_connexion_du_personnel_ecrite_aussitot(web):
    _client(web, "admin")
    m = web.extensions["mediatheque"]
    assert [j.action for j in Mediatheque.charger(m._source).journal] == ["connexion"]
