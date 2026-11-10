"""Audit securite P2 : site web - force brute, enumeration, deni de service,
atomicite des actions.

Convention : un test marque xfail(strict=True) PROUVE une faille ouverte (Wx).
"""
import re
import secrets

import pytest

from mediatheque import auth
from mediatheque.auth import ADHERENT, Compte
from mediatheque.mediatheque import Mediatheque
from mediatheque.web import create_app
from outils_web import (MDP, base_de_test, client_connecte, connecter, poster,
                        variable_interne, verrou_tenu)
from outils_web import (web_admin, web_app, web_db, web_ines,  # noqa: F401 (fixtures)
                        web_lea)


def _page_neutre(reponse):
    texte = reponse.get_data(as_text=True)
    texte = re.sub(r'name="csrf" value="[^"]*"', "", texte)
    return re.sub(r'name="identifiant"([^>]*)value="[^"]*"', r'name="identifiant"\1', texte)


# ========================================= force brute et enumeration
def test_meme_reponse_identifiant_inconnu_ou_mauvais_mot_de_passe(web_app):
    inconnu = connecter(web_app.test_client(), "personne", "Mauvais999")
    connu = connecter(web_app.test_client(), "lea", "Mauvais999")
    assert inconnu.status_code == connu.status_code == 200
    assert _page_neutre(inconnu) == _page_neutre(connu)


@pytest.mark.parametrize("ident", ["lea", "personne"])
def test_delai_progressif_applique_a_travers_le_site(web_app, ident):
    """Apres 5 echecs, meme le bon mot de passe est refuse pendant le delai,
    que l'identifiant existe ou non (pas d'enumeration par le blocage)."""
    web_app.extensions["mediatheque"].comptes._horloge = lambda: 1000.0
    for _ in range(5):
        connecter(web_app.test_client(), ident, "Mauvais999")
    r = connecter(web_app.test_client(), ident, MDP)
    assert r.status_code == 200
    assert "trop de tentatives" in r.get_data(as_text=True).lower()


@pytest.mark.parametrize("variante", ["LEA", " lea ", "Lea"])
def test_delai_non_contournable_par_la_casse(web_app, variante):
    web_app.extensions["mediatheque"].comptes._horloge = lambda: 1000.0
    for _ in range(5):
        connecter(web_app.test_client(), "lea", "Mauvais999")
    r = connecter(web_app.test_client(), variante, MDP)
    assert r.status_code == 200


def test_changement_de_mot_de_passe_soumis_au_delai(web_app, web_lea):
    """La route /compte/mot-de-passe ne sert pas d'oracle de force brute."""
    web_app.extensions["mediatheque"].comptes._horloge = lambda: 1000.0
    for _ in range(5):
        poster(web_lea, "/compte/mot-de-passe", page="/compte",
               ancien="Mauvais999", nouveau="Nouveau456", confirmation="Nouveau456")
    poster(web_lea, "/compte/mot-de-passe", page="/compte",
           ancien=MDP, nouveau="Nouveau456", confirmation="Nouveau456")
    assert connecter(web_app.test_client(), "lea", "Nouveau456").status_code == 200


@pytest.fixture
def app_compte_ancien(dossier_data, tmp_path):
    """Base avec un compte dont le hash date d'avant S6 (N=2**14)."""
    chemin = base_de_test(dossier_data, tmp_path)
    m = Mediatheque.charger(chemin)
    sel = secrets.token_bytes(16)
    m.ajouter_compte(Compte("hugo", auth.hacher(MDP, sel, auth._SCRYPT_HISTORIQUE),
                            sel, ADHERENT, "A002"))
    m.sauvegarder()
    return create_app(chemin, secret_key="test", testing=True)


@pytest.mark.xfail(strict=True, reason="faille W7 : un compte a hash ancien (N=2**14) "
                   "repond ~8x plus vite qu'un identifiant inconnu (N=2**17) : enumeration par le temps")
def test_w7_cout_identique_compte_ancien_ou_inconnu(app_compte_ancien, monkeypatch):
    couts = []
    vrai_hacher = auth.hacher

    def espion(mot_de_passe, sel, params=None):
        couts.append((params or auth.parametres_scrypt)["n"])
        return vrai_hacher(mot_de_passe, sel, params)
    monkeypatch.setattr(auth, "hacher", espion)

    connecter(app_compte_ancien.test_client(), "personne", "Mauvais999")
    cout_inconnu, couts[:] = max(couts), []
    connecter(app_compte_ancien.test_client(), "hugo", "Mauvais999")
    assert max(couts) == cout_inconnu


# ===================================================== deni de service
def test_w1_hachage_hors_du_verrou_global(web_app, monkeypatch):
    verrou = variable_interne(web_app, "verrou")
    tenu_pendant_le_hachage = []
    vrai_hacher = auth.hacher

    def espion(*args, **kwargs):
        tenu_pendant_le_hachage.append(verrou_tenu(verrou))
        return vrai_hacher(*args, **kwargs)
    monkeypatch.setattr(auth, "hacher", espion)

    connecter(web_app.test_client(), "personne", "Mauvais999")  # sans compte, avec un CSRF libre
    assert tenu_pendant_le_hachage and not any(tenu_pendant_le_hachage)


def test_w1_changement_de_mot_de_passe_hache_hors_du_verrou(web_app, web_lea, monkeypatch):
    verrou = variable_interne(web_app, "verrou")
    tenu_pendant_le_hachage = []
    vrai_hacher = auth.hacher

    def espion(*args, **kwargs):
        tenu_pendant_le_hachage.append(verrou_tenu(verrou))
        return vrai_hacher(*args, **kwargs)
    monkeypatch.setattr(auth, "hacher", espion)

    poster(web_lea, "/compte/mot-de-passe", page="/compte",
           ancien=MDP, nouveau="Nouveau456", confirmation="Nouveau456")
    assert len(tenu_pendant_le_hachage) == 2 and not any(tenu_pendant_le_hachage)
    assert "Mot de passe modifié" in web_lea.get("/compte").get_data(as_text=True)


def test_w1_site_sature_donne_503(web_db):
    app = create_app(web_db, secret_key="test", testing=True, attente_hachage_s=0.01)
    emplacement = variable_interne(app, "emplacement_hachage").__wrapped__
    hachage = emplacement.__closure__[emplacement.__code__.co_freevars.index("hachage")].cell_contents
    pris = [hachage.acquire(blocking=False) for _ in range(2)]  # deux connexions en cours
    try:
        assert all(pris)
        r = connecter(app.test_client(), "lea")
        assert r.status_code == 503 and "Retry-After" in r.headers
        assert "Réessayez dans quelques secondes" in r.get_data(as_text=True)
    finally:
        for _ in pris:
            hachage.release()
    assert connecter(app.test_client(), "lea").status_code == 302


def test_w1_limite_de_tentatives_par_adresse_ip(web_db):
    app = create_app(web_db, secret_key="test", testing=True, tentatives_par_ip=3)
    c = app.test_client()
    for _ in range(3):
        assert connecter(c, "personne", "Mauvais999").status_code == 200
    r = connecter(c, "lea")
    assert r.status_code == 429 and "Trop de tentatives" in r.get_data(as_text=True)
    autre = {"REMOTE_ADDR": "10.0.0.2"}  # une autre adresse n'est pas bloquee
    page = c.get("/connexion", environ_base=autre).get_data(as_text=True)
    jeton = re.search(r'name="csrf" value="([^"]+)"', page).group(1)
    r = c.post("/connexion", environ_base=autre,
               data={"identifiant": "lea", "mot_de_passe": MDP, "csrf": jeton})
    assert r.status_code == 302


def test_w1_connexions_reussies_non_comptees(web_db):
    app = create_app(web_db, secret_key="test", testing=True, tentatives_par_ip=2)
    for _ in range(4):  # une borne partagee : plusieurs lecteurs, une seule adresse
        assert connecter(app.test_client(), "lea").status_code == 302




def test_longueurs_tronquees_a_la_connexion(web_app, monkeypatch):
    recus = []
    vrai = auth.GestionComptes.authentifier

    def espion(self, identifiant, mot_de_passe):
        recus.append((len(identifiant), len(mot_de_passe)))
        return vrai(self, identifiant, mot_de_passe)
    monkeypatch.setattr(auth.GestionComptes, "authentifier", espion)
    connecter(web_app.test_client(), "x" * 10_000, "y" * 50_000)
    assert recus == [(64, 256)]


# ========================================================= atomicite
@pytest.mark.xfail(strict=True, reason="faille W4 : le decorateur `action` ne defait pas les "
                   "modifications en memoire quand l'action echoue : adherent cree sans compte, "
                   "puis persiste par l'action suivante alors que le responsable a vu une erreur")
def test_w4_echec_partiel_annule(web_app, web_admin, web_ines):
    m = web_app.extensions["mediatheque"]
    poster(web_admin, "/admin/adherents", page="/admin/gestion?onglet=adherents",
           numero="A004", prenom="Noe", nom="Blanc", type="standard",
           identifiant="noe.blanc", mot_de_passe="faible")  # refuse par la politique
    page = web_admin.get("/admin/gestion?onglet=adherents").get_data(as_text=True)
    assert "mot de passe trop faible" in page
    poster(web_ines, "/reserver/D001")  # action ordinaire d'un autre utilisateur
    assert "A004" not in [a.numero for a in Mediatheque.charger(m._source).adherents]
    assert "A004" not in [a.numero for a in m.adherents]




@pytest.mark.xfail(strict=True, reason="faille W5 : les pages GET (/compte, /catalogue, "
                   "/admin) modifient l'etat (actualiser_reservations) sans prendre le verrou")
def test_w5_get_qui_modifie_l_etat_prend_le_verrou(web_app, web_lea, monkeypatch):
    m = web_app.extensions["mediatheque"]
    verrou = variable_interne(web_app, "verrou")
    tenu = []
    vrai = m.actualiser_reservations

    def espion(jour):
        tenu.append(verrou_tenu(verrou))
        return vrai(jour)
    monkeypatch.setattr(m, "actualiser_reservations", espion)
    assert web_lea.get("/compte").status_code == 200
    assert tenu and all(tenu)


def test_action_verrouillee_et_sauvegardee(web_app, web_ines, monkeypatch):
    """Point sain : les POST metier s'executent sous le verrou."""
    m = web_app.extensions["mediatheque"]
    verrou = variable_interne(web_app, "verrou")
    tenu = []
    vrai = m.sauvegarder

    def espion(*a, **k):
        tenu.append(verrou_tenu(verrou))
        return vrai(*a, **k)
    monkeypatch.setattr(m, "sauvegarder", espion)
    poster(web_ines, "/reserver/D001")
    assert tenu == [True]


def test_sessions_independantes_entre_comptes(web_app):
    lea = client_connecte(web_app, "lea")
    ines = client_connecte(web_app, "ines")
    assert "Bonjour Lea" in lea.get("/compte").get_data(as_text=True)
    assert "Bonjour Ines" in ines.get("/compte").get_data(as_text=True)
