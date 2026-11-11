import re

import pytest

from mediatheque.auth import ADHERENT, RESPONSABLE
from mediatheque.mediatheque import Mediatheque
from mediatheque.web import create_app

MDP = "Secret123"


@pytest.fixture
def db(dossier_data, tmp_path):
    m = Mediatheque.charger(dossier_data)
    m.creer_compte("admin", MDP, RESPONSABLE)
    m.creer_compte("lea", MDP, ADHERENT, "A001")
    m.creer_compte("ines", MDP, ADHERENT, "A003")
    chemin = tmp_path / "m.db"
    m.sauvegarder(chemin)
    return chemin


@pytest.fixture
def app(db):
    return create_app(db, secret_key="test", testing=True)


def csrf(client, url="/connexion"):
    page = client.get(url).get_data(as_text=True)
    return re.search(r'name="csrf" value="([^"]+)"', page).group(1)


def connecter(client, ident, mdp=MDP):
    return client.post("/connexion", data={"identifiant": ident, "mot_de_passe": mdp,
                                           "csrf": csrf(client)})


@pytest.fixture
def lea(app):
    c = app.test_client()
    connecter(c, "lea")
    return c


@pytest.fixture
def admin(app):
    c = app.test_client()
    connecter(c, "admin")
    return c


def post(client, url, page="/catalogue", **data):
    return client.post(url, data={**data, "csrf": csrf(client, page)})


# ------------------------------------------------------------- connexion
def test_redirection_sans_connexion(app):
    c = app.test_client()
    for url in ("/", "/catalogue", "/compte", "/admin", "/admin/gestion"):
        r = c.get(url)
        assert r.status_code == 302 and r.location.endswith("/connexion")


def test_connexion_et_redirection_par_role(app):
    c = app.test_client()
    assert connecter(c, "lea").location.endswith("/")
    assert c.get("/").location.endswith("/catalogue")
    c2 = app.test_client()
    connecter(c2, "admin")
    assert c2.get("/").location.endswith("/admin")


def test_mauvais_mot_de_passe(app):
    r = connecter(app.test_client(), "lea", "Mauvais999")
    assert r.status_code == 200
    assert "incorrect" in r.get_data(as_text=True)


def test_csrf_obligatoire(app):
    c = app.test_client()
    r = c.post("/connexion", data={"identifiant": "lea", "mot_de_passe": MDP})
    assert r.status_code == 400


def test_deconnexion_invalide_la_session(lea):
    post(lea, "/deconnexion")
    assert lea.get("/catalogue").status_code == 302


def test_entetes_de_securite(app):
    r = app.test_client().get("/connexion")
    assert "script-src 'none'" in r.headers["Content-Security-Policy"]
    assert r.headers["X-Frame-Options"] == "DENY"
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    cookie = r.headers.get("Set-Cookie", "")
    assert "HttpOnly" in cookie and "SameSite=Lax" in cookie


# -------------------------------------------------------------- adhérent
def test_catalogue_et_filtres(lea):
    page = lea.get("/catalogue").get_data(as_text=True)
    assert "Fluent Python" in page and "Inception" in page
    page = lea.get("/catalogue?type=dvd").get_data(as_text=True)
    assert "Inception" in page and "Fluent Python" not in page
    page = lea.get("/catalogue?q=martin").get_data(as_text=True)
    assert "Clean Code" in page and "Inception" not in page


def test_reserver_puis_annuler(app):
    c = app.test_client()
    connecter(c, "ines")
    r = post(c, "/reserver/D001")
    assert r.status_code == 302
    assert "Vous êtes le 1er à l'attendre" in c.get("/compte").get_data(as_text=True)
    post(c, "/annuler/D001", page="/compte")
    assert "Aucune réservation active" in c.get("/compte").get_data(as_text=True)
    # persistance : la base a ete sauvegardee
    m = app.extensions["mediatheque"]
    assert Mediatheque.charger(m._source).reservations[0].statut == "annulee"


def test_reserver_document_disponible_affiche_erreur(app):
    c = app.test_client()
    connecter(c, "ines")
    post(c, "/reserver/D005")
    page = c.get("/catalogue").get_data(as_text=True)
    assert 'class="message erreur"' in page and "directement" in page


def test_mon_compte(lea):
    page = lea.get("/compte").get_data(as_text=True)
    assert "Bonjour Lea" in page and "Fluent Python" in page and "de retard" in page


def test_adherent_interdit_en_admin(lea):
    assert lea.get("/admin").status_code == 403
    assert lea.get("/admin/gestion").status_code == 403
    assert lea.get("/admin/retards.csv").status_code == 403
    assert post(lea, "/admin/emprunt", id_document="D005", numero="A001").status_code == 403


def test_changer_mot_de_passe(app, lea):
    post(lea, "/compte/mot-de-passe", page="/compte",
         ancien=MDP, nouveau="Nouveau456", confirmation="Nouveau456")
    page = lea.get("/compte")
    assert page.status_code == 200  # toujours connectee
    texte = page.get_data(as_text=True)
    assert "Mot de passe modifié" in texte and 'class="message erreur"' not in texte
    post(lea, "/reserver/D003")  # la session reste pleinement utilisable
    assert "Réservation enregistrée" in lea.get("/catalogue").get_data(as_text=True)
    assert connecter(app.test_client(), "lea", "Nouveau456").status_code == 302


def test_session_revoquee_par_le_responsable(app, admin, lea):
    post(admin, "/admin/comptes/mot-de-passe", page="/admin/gestion?onglet=adherents",
         identifiant="lea", mot_de_passe="Reinit1234")
    r = lea.get("/catalogue")
    assert r.status_code == 302 and r.location.endswith("/connexion")


def test_xss_echappe(admin, app):
    post(admin, "/admin/documents", page="/admin/gestion", type="livre", id="D099",
         titre="<script>alert(1)</script>", annee="2020", extra="x")
    page = admin.get("/admin/gestion").get_data(as_text=True)
    assert "<script>alert(1)</script>" not in page
    assert "&lt;script&gt;" in page


# ----------------------------------------------------------- responsable
def test_tableau_de_bord(admin):
    page = admin.get("/admin").get_data(as_text=True)
    assert "Tableau de bord" in page and "Retards" in page and "Fluent Python" in page


def test_guichet_emprunt_et_retour(admin, app):
    post(admin, "/admin/emprunt", page="/admin", id_document="D005", numero="A003")
    m = app.extensions["mediatheque"]
    assert not m.disponible("D005")
    post(admin, "/admin/retour", page="/admin", id_document="D005")
    assert m.disponible("D005")


def test_export_csv_neutralise_les_formules(admin):
    r = admin.get("/admin/retards.csv")
    assert r.status_code == 200 and r.mimetype == "text/csv"
    assert "D001" in r.get_data(as_text=True)


def test_ajout_adherent_avec_compte(admin, app):
    post(admin, "/admin/adherents", page="/admin/gestion?onglet=adherents",
         numero="A004", prenom="Noe", nom="Blanc", type="premium",
         identifiant="noe.blanc", mot_de_passe="Provisoire1")
    assert connecter(app.test_client(), "noe.blanc", "Provisoire1").status_code == 302


def test_suppression_document_avec_historique_refusee(admin, app):
    post(admin, "/admin/documents/D001/supprimer", page="/admin/gestion")
    assert "D001" in app.extensions["mediatheque"]


# ------------------------------------------------------- fiche et reco
def test_fiche_document(lea, admin):
    page = lea.get("/document/D001").get_data(as_text=True)
    assert "Fluent Python" in page and "Luciano Ramalho" in page
    assert "Historique des prêts" not in page            # reserve au personnel
    assert "Historique des prêts" in admin.get("/document/D001").get_data(as_text=True)


@pytest.mark.parametrize("url", ["/document/D999", "/document/abc", "/document/D1%27%3B"])
def test_fiche_introuvable(lea, url):
    assert lea.get(url).status_code == 404


def test_fiche_exige_une_connexion(app):
    r = app.test_client().get("/document/D001")
    assert r.status_code == 302 and r.location.endswith("/connexion")


def test_catalogue_relie_les_fiches(lea):
    assert 'href="/document/D002"' in lea.get("/catalogue").get_data(as_text=True)


def test_catalogue_genre_inconnu_ignore(lea):
    assert lea.get("/catalogue?genre=%3Cscript%3E").status_code == 200


def test_compte_affiche_les_suggestions(lea):
    page = lea.get("/compte").get_data(as_text=True)
    assert "Pour vous" in page


# ------------------------------------------------ retours du panel UX
def test_guichet_saisie_libre_et_message_complet(admin, app):
    post(admin, "/admin/emprunt", page="/admin", id_document="d005 — Design Patterns",
         numero="A003 Petit")
    page = admin.get("/admin").get_data(as_text=True)
    assert "Prêt enregistré : « Design Patterns » pour Ines PETIT (A003)" in page


def test_retour_dit_pour_qui_mettre_de_cote(app, admin):
    c = app.test_client()
    connecter(c, "ines")
    post(c, "/reserver/D001")                       # D001 est chez lea
    post(admin, "/admin/retour", page="/admin?onglet=retour", id_document="D001")
    page = admin.get("/admin").get_data(as_text=True)
    assert "mettez-le de côté pour Ines PETIT (A003)" in page


def test_bouton_reserver_remplace_quand_limite_atteinte(app):
    m = app.extensions["mediatheque"]
    for i, id_doc in enumerate(("D002", "D003", "D004")):
        if m.disponible(id_doc):
            m.emprunter(id_doc, "A002")
        m.reserver(id_doc, "A003")
    c = app.test_client()
    connecter(c, "ines")
    assert "3 réservations en cours" in c.get("/catalogue").get_data(as_text=True)


def test_recherche_sans_accents_depuis_le_site(lea):
    assert "Clean Code" in lea.get("/catalogue?q=MARTIN").get_data(as_text=True)


def test_lien_d_evitement(lea):
    page = lea.get("/catalogue").get_data(as_text=True)
    assert 'href="#contenu"' in page and 'id="contenu"' in page


# ------------------------------------------------ second panel (N1 a N4)
def test_guichet_par_nom_et_par_titre(admin, app):
    post(admin, "/admin/emprunt", page="/admin", id_document="design patterns", numero="petit")
    page = admin.get("/admin").get_data(as_text=True)
    assert "« Design Patterns » pour Ines PETIT (A003)" in page
    assert "décembre" in page or "novembre" in page            # date ecrite en toutes lettres
    assert ".." not in page.split("Prêt enregistré")[1][:200]   # N1 : pas de double point


def test_guichet_saisie_ambigue_ou_inconnue(admin):
    post(admin, "/admin/emprunt", page="/admin", id_document="D005", numero="zzz")
    assert "Aucun lecteur ne correspond" in admin.get("/admin").get_data(as_text=True)


def test_compteur_annonce_les_filtres_et_propose_tout_le_fonds(lea):
    page = lea.get("/catalogue?q=zzzz&type=dvd").get_data(as_text=True)
    assert "films" in page and "retirer les filtres" in page
    assert "dans tout le fonds" in page
