"""Audit securite P2 : site web Flask (CSRF, sessions, autorisations, XSS, en-tetes).

Convention : un test marque xfail(strict=True) PROUVE une faille ouverte (Wx).
Quand la faille sera corrigee, il passera (XPASS strict = echec) : retirer
alors le marqueur. Les autres tests verrouillent les points verifies sains.
"""
import time

import pytest

from outils_web import (MDP, client_connecte, connecter, jeton_csrf, poster,
                      variable_interne)
from outils_web import (web_admin, web_app, web_app_prod, web_db,  # noqa: F401 (fixtures)
                        web_ines, web_lea)
from mediatheque.mediatheque import Mediatheque
from mediatheque.web import app as module_app
from mediatheque.web import create_app


def _regles(app, methode):
    return [r for r in app.url_map.iter_rules()
            if methode in r.methods and r.endpoint != "static"]


def _url(regle):
    return regle.rule.replace("<id_document>", "D001")


def _etat(app):
    m = app.extensions["mediatheque"]
    return (len(m), len(m.adherents), len(m.emprunts), len(m.reservations),
            sorted((c.identifiant, c.hash_mdp) for c in m.comptes))


# ===================================================================== CSRF
def test_tous_les_post_exigent_le_jeton_csrf(web_app, web_admin):
    """Aucun POST (connexion et deconnexion comprises) ne passe sans jeton."""
    avant = _etat(web_app)
    regles = _regles(web_app, "POST")
    assert len(regles) >= 11
    for regle in regles:
        for data in ({}, {"csrf": ""}, {"csrf": "faux"}):
            r = web_admin.post(_url(regle), data={**data, "id_document": "D005",
                                                  "numero": "A003"})
            assert r.status_code == 400, regle.rule
    assert _etat(web_app) == avant
    assert web_admin.get("/admin").status_code == 200  # toujours connecte


def test_jeton_csrf_et_jeton_de_session_regeneres_a_la_connexion(web_app):
    """Pas de fixation : la connexion remplace le jeton de session ET le CSRF."""
    c = web_app.test_client()
    csrf_avant = jeton_csrf(c)
    with c.session_transaction() as s:
        s["jeton"] = "jeton-plante-par-l-attaquant"
    connecter(c, "lea")
    with c.session_transaction() as s:
        assert s["jeton"] != "jeton-plante-par-l-attaquant"
        assert s["csrf"] != csrf_avant
    assert "jeton-plante-par-l-attaquant" not in variable_interne(web_app, "sessions_actives")


def test_ancien_jeton_csrf_refuse_apres_connexion(web_app):
    c = web_app.test_client()
    ancien = jeton_csrf(c)
    connecter(c, "lea")
    r = c.post("/reserver/D001", data={"csrf": ancien})
    assert r.status_code == 400


def test_csrf_compare_en_temps_constant():
    source = (module_app.__file__)
    texte = open(source, encoding="utf-8").read()
    assert "compare_digest(envoye, session[\"csrf\"])" in texte


@pytest.mark.xfail(strict=True, reason="faille W6 : jeton CSRF non ASCII -> TypeError "
                   "dans secrets.compare_digest -> erreur 500 au lieu de 400")
def test_w6_jeton_csrf_non_ascii_donne_400(web_app_prod):
    c = web_app_prod.test_client()
    jeton_csrf(c)
    r = c.post("/connexion", data={"identifiant": "lea", "mot_de_passe": MDP,
                                   "csrf": "é" * 43})
    assert r.status_code == 400


def test_post_intersite_sans_jeton_meme_avec_referer_externe(web_lea):
    """Le `redirect(request.referrer)` n'est pas exploitable depuis un site
    tiers : la requete est rejetee par le CSRF avant d'atteindre la vue."""
    r = web_lea.post("/reserver/D001", headers={"Referer": "https://evil.example/"})
    assert r.status_code == 400
    assert "evil.example" not in (r.location or "")


# ================================================================= sessions
def test_cookie_rejoue_apres_deconnexion_refuse(web_app, web_lea):
    cookie = web_lea.get_cookie("session").value
    poster(web_lea, "/deconnexion")
    pirate = web_app.test_client()
    pirate.set_cookie("session", cookie)
    r = pirate.get("/catalogue")
    assert r.status_code == 302 and r.location.endswith("/connexion")


def test_changement_de_mot_de_passe_revoque_les_autres_sessions(web_app, web_lea):
    autre_navigateur = client_connecte(web_app, "lea")
    poster(web_lea, "/compte/mot-de-passe", page="/compte",
           ancien=MDP, nouveau="Nouveau456", confirmation="Nouveau456")
    assert web_lea.get("/compte").status_code == 200
    r = autre_navigateur.get("/compte")
    assert r.status_code == 302 and r.location.endswith("/connexion")


def test_reinitialisation_par_le_responsable_revoque_la_session(web_app, web_admin, web_lea):
    poster(web_admin, "/admin/comptes/mot-de-passe", page="/admin/gestion?onglet=adherents",
           identifiant="lea", mot_de_passe="Reinit1234")
    assert web_lea.get("/catalogue").status_code == 302
    assert web_lea.post("/reserver/D001", data={"csrf": "x"}).status_code == 400


def test_cookie_falsifie_refuse(web_app):
    """Le cookie est signe : un jeton invente ne donne aucun acces."""
    c = web_app.test_client()
    c.set_cookie("session", "eyJqZXRvbiI6ImFkbWluIn0.AAAAAA.BBBBBBBB")
    assert c.get("/admin").status_code == 302


def test_cookie_httponly_samesite_et_secure_si_https(web_db, monkeypatch):
    monkeypatch.setenv("MEDIATHEQUE_HTTPS", "1")
    app = create_app(web_db, secret_key="test", testing=True)
    cookie = app.test_client().get("/connexion", base_url="https://localhost").headers["Set-Cookie"]
    assert "HttpOnly" in cookie and "SameSite=Lax" in cookie and "Secure" in cookie


def test_w2_session_expire_apres_une_longue_inactivite(web_lea, monkeypatch):
    assert web_lea.get("/catalogue").status_code == 200
    plus_tard = time.time() + 7 * 24 * 3600
    base_mono = time.monotonic() + 7 * 24 * 3600
    monkeypatch.setattr(time, "time", lambda: plus_tard)
    monkeypatch.setattr(time, "monotonic", lambda: base_mono)
    r = web_lea.get("/catalogue")
    assert r.status_code == 302 and r.location.endswith("/connexion")


class _Horloge:
    def __init__(self):
        self.t = time.monotonic()

    def __call__(self):
        return self.t


def test_w2_inactivite_message_neutre_et_registre_vide(web_db, monkeypatch):
    horloge = _Horloge()
    monkeypatch.setattr(time, "monotonic", horloge)
    app = create_app(web_db, secret_key="test", testing=True, inactivite_s=60, duree_max_s=600)
    c = client_connecte(app, "lea")
    horloge.t += 50
    assert c.get("/catalogue").status_code == 200   # l'activite repousse l'echeance
    horloge.t += 50
    assert c.get("/catalogue").status_code == 200
    horloge.t += 61
    r = c.get("/catalogue")
    assert r.status_code == 302 and r.location.endswith("/connexion")
    assert "Session expirée, reconnectez-vous" in c.get("/connexion").get_data(as_text=True)
    assert variable_interne(app, "sessions_actives") == {}
    assert c.get("/catalogue").status_code == 302


def test_w2_duree_maximale_meme_avec_activite(web_db, monkeypatch):
    horloge = _Horloge()
    monkeypatch.setattr(time, "monotonic", horloge)
    app = create_app(web_db, secret_key="test", testing=True, inactivite_s=60, duree_max_s=150)
    c = client_connecte(app, "lea")
    for _ in range(3):
        horloge.t += 45
        assert c.get("/catalogue").status_code == 200
    horloge.t += 45   # 180 s depuis la connexion, jamais 60 s d'inactivite
    assert c.get("/catalogue").status_code == 302


def test_w2_valeurs_par_defaut():
    assert module_app.INACTIVITE_S == 30 * 60 and module_app.DUREE_MAX_S == 12 * 3600


def test_w3_session_revoquee_purgee_du_registre(web_app, web_admin, web_lea):
    sessions = variable_interne(web_app, "sessions_actives")
    poster(web_admin, "/admin/comptes/mot-de-passe", page="/admin/gestion?onglet=adherents",
           identifiant="lea", mot_de_passe="Reinit1234")
    client_connecte(web_app, "ines")  # activite ordinaire du site
    assert not [s for s in sessions.values() if s.compte.identifiant == "lea"]


def test_w3_cinq_sessions_au_plus_par_compte(web_app):
    sessions = variable_interne(web_app, "sessions_actives")
    clients = [client_connecte(web_app, "lea") for _ in range(7)]
    assert len([s for s in sessions.values() if s.compte.identifiant == "lea"]) == 5
    # les deux plus anciennes ont ete fermees, les cinq plus recentes restent valides
    assert [c.get("/catalogue").status_code for c in clients] == [302] * 2 + [200] * 5


def test_w3_session_expiree_purgee_a_la_connexion_suivante(web_db, monkeypatch):
    horloge = _Horloge()
    monkeypatch.setattr(time, "monotonic", horloge)
    app = create_app(web_db, secret_key="test", testing=True, inactivite_s=60)
    sessions = variable_interne(app, "sessions_actives")
    client_connecte(app, "lea")      # navigateur abandonne : le cookie ne revient jamais
    horloge.t += 61
    client_connecte(app, "ines")
    assert [s.compte.identifiant for s in sessions.values()] == ["ines"]


def test_w3_constat_croissance_du_registre(web_app):
    """Constat chiffre (passe aujourd'hui) : chaque connexion sans deconnexion
    ajoute une entree. Le test ne fige que le minimum : au moins une entree
    par session encore valide."""
    sessions = variable_interne(web_app, "sessions_actives")
    clients = [client_connecte(web_app, "lea") for _ in range(5)]
    assert len(sessions) >= 5
    assert all(c.get("/catalogue").status_code == 200 for c in clients)


# ============================================================ autorisations
def test_toutes_les_pages_exigent_la_connexion(web_app):
    c = web_app.test_client()
    publiques = {"/connexion"}
    for regle in _regles(web_app, "GET"):
        if regle.rule in publiques:
            continue
        r = c.get(_url(regle))
        assert r.status_code == 302 and r.location.endswith("/connexion"), regle.rule


def test_routes_admin_interdites_a_l_adherent(web_app, web_lea):
    avant = _etat(web_app)
    admin = [r for r in web_app.url_map.iter_rules() if r.rule.startswith("/admin")]
    assert len(admin) >= 9
    jeton = jeton_csrf(web_lea, "/catalogue")
    for regle in admin:
        if "GET" in regle.methods:
            assert web_lea.get(_url(regle)).status_code == 403, regle.rule
        if "POST" in regle.methods:
            r = web_lea.post(_url(regle), data={
                "csrf": jeton, "id_document": "D005", "numero": "A001", "type": "livre",
                "id": "D099", "titre": "x", "annee": "2020", "extra": "x", "nom": "x",
                "prenom": "x", "identifiant": "lea", "mot_de_passe": "Pirate1234"})
            assert r.status_code == 403, regle.rule
    assert _etat(web_app) == avant


def test_idor_annuler_la_reservation_d_un_autre(web_app, web_ines, web_lea):
    poster(web_ines, "/reserver/D001")  # D001 est emprunte par Lea
    poster(web_lea, "/reserver/D003")
    m = web_app.extensions["mediatheque"]
    assert [r.numero_adherent for r in m.file_attente("D001")] == ["A003"]
    # Lea tente d'annuler la reservation d'Ines par l'URL
    poster(web_lea, "/annuler/D001", page="/compte")
    assert [r.statut for r in m.file_attente("D001")] == ["en_attente"]
    assert "aucune reservation active" in web_lea.get("/compte").get_data(as_text=True)


def test_adherent_ne_peut_cibler_un_autre_numero_par_formulaire(web_app, web_lea):
    """Les vues adherent n'acceptent aucun parametre `numero` : un champ ajoute
    a la main est ignore et la reservation reste au nom de l'adherent connecte."""
    jeton = jeton_csrf(web_lea)
    web_lea.post("/reserver/D003", data={"csrf": jeton, "numero": "A003"})
    m = web_app.extensions["mediatheque"]
    assert [r.numero_adherent for r in m.reservations] == ["A001"]


# ===================================================================== XSS
CHARGE = '"><script>alert(1)</script><x a=\''


def test_xss_recherche_reflechie_echappee(web_lea):
    page = web_lea.get("/catalogue", query_string={"q": CHARGE}).get_data(as_text=True)
    assert "<script>alert(1)" not in page
    assert "&#34;&gt;&lt;script&gt;" in page


def test_xss_identifiant_reflechi_echappe(web_app):
    c = web_app.test_client()
    page = c.post("/connexion", data={"identifiant": CHARGE, "mot_de_passe": "x",
                                      "csrf": jeton_csrf(c)}).get_data(as_text=True)
    assert "<script>alert(1)" not in page and 'value="&#34;&gt;' in page


def test_xss_message_flash_avec_id_de_l_url(web_lea):
    poster(web_lea, "/reserver/" + "%3Cscript%3Ealert(1)%3C!--")
    page = web_lea.get("/catalogue").get_data(as_text=True)
    assert "document inconnu" in page
    assert "<script>alert(1)" not in page and "&lt;script&gt;" in page


def test_xss_titre_dans_attribut_aria_label(web_app, web_admin):
    titre = 'x" onmouseover="alert(1)'
    poster(web_admin, "/admin/documents", page="/admin/gestion", type="livre", id="D099",
           titre=titre, annee="2020", extra="x")
    poster(web_admin, "/admin/emprunt", page="/admin", id_document="D099", numero="A002")
    page_admin = web_admin.get("/admin/gestion").get_data(as_text=True)
    lea = client_connecte(web_app, "ines")
    page = lea.get("/catalogue").get_data(as_text=True)
    for p in (page, page_admin):
        assert 'onmouseover="alert(1)' not in p
        assert "x&#34; onmouseover=&#34;alert(1)" in p
    assert 'aria-label="Réserver x&#34; onmouseover' in page


def test_csp_et_entetes_sur_toutes_les_reponses(web_app, web_lea):
    for r in (web_app.test_client().get("/connexion"), web_lea.get("/inexistant"),
              web_lea.get("/admin"), web_lea.post("/reserver/D001")):
        csp = r.headers["Content-Security-Policy"]
        assert "script-src 'none'" in csp and "frame-ancestors 'none'" in csp
        assert "base-uri 'none'" in csp and "form-action 'self'" in csp
        assert r.headers["X-Frame-Options"] == "DENY"
        assert r.headers["Cache-Control"] == "no-store"


def test_aucun_script_ni_style_en_ligne_dans_les_pages(web_app, web_admin, web_lea):
    pages = [web_app.test_client().get("/connexion"), web_lea.get("/catalogue"),
             web_lea.get("/compte"), web_admin.get("/admin"),
             web_admin.get("/admin/gestion"), web_admin.get("/admin/gestion?onglet=adherents")]
    for r in pages:
        html = r.get_data(as_text=True).lower()
        assert "<script" not in html and "<style" not in html and " on" + "click=" not in html


# ============================================== export CSV et en-tetes
def test_export_csv_entete_fixe(web_admin):
    r = web_admin.get("/admin/retards.csv")
    assert r.headers["Content-Disposition"] == "attachment; filename=retards.csv"
    assert r.headers["X-Content-Type-Options"] == "nosniff"


@pytest.mark.parametrize("charge", ["=1+1", "+1", "-1", "@SOMME(A1)", "\t=1", "\r=1"])
def test_export_csv_cellule_neutralisee(charge):
    assert module_app._cellule(charge).startswith("'")


def test_redirection_ignore_les_entetes_injectes(web_lea):
    r = web_lea.get("/catalogue", query_string={"q": "a\r\nSet-Cookie: x=1"})
    assert r.status_code == 200 and "x=1" not in r.headers.get("Set-Cookie", "")


# ======================================================= erreurs, debug
def test_erreur_500_sans_trace(web_app_prod, monkeypatch):
    from mediatheque.session import Session

    def panne(self, *a, **k):
        raise RuntimeError("detail-interne-secret")
    monkeypatch.setattr(Session, "catalogue", panne)
    c = client_connecte(web_app_prod, "lea")
    r = c.get("/catalogue")
    assert r.status_code == 500
    texte = r.get_data(as_text=True)
    assert "detail-interne-secret" not in texte and "Traceback" not in texte


def test_lancement_sans_debug_sur_127_0_0_1(web_db, monkeypatch):
    appels = {}
    from flask import Flask
    monkeypatch.setattr(Flask, "run", lambda self, **kw: appels.update(kw))
    monkeypatch.setattr("sys.argv", ["app", "--db", str(web_db)])
    module_app.main()
    assert appels["host"] == "127.0.0.1" and appels["debug"] is False


def test_taille_de_requete_bornee(web_app):
    c = web_app.test_client()
    r = c.post("/connexion", data={"identifiant": "x" * 100_000, "csrf": jeton_csrf(c)})
    assert r.status_code == 413
    assert web_app.config["MAX_CONTENT_LENGTH"] == 64 * 1024


def test_persistance_apres_action_reussie(web_app, web_ines):
    poster(web_ines, "/reserver/D001")
    m = web_app.extensions["mediatheque"]
    assert len(Mediatheque.charger(m._source).reservations) == 1
