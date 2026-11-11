"""Audit securite des fiches, recommandations et couvertures (commits 908786c..c625962).

Convention : un test marque xfail(strict=True) PROUVE une faille ouverte (Fx) ;
il passera (et fera donc echouer la suite) le jour ou la faille sera corrigee,
ce qui rappelle d'enlever le marqueur. Les autres tests verrouillent des points sains.

Tout se fait sur des copies (tmp_path) ; le script de telechargement n'est
JAMAIS execute contre Internet : urllib est simule, ou un serveur local sert.
"""
import importlib.util
import http.server
import json
import sqlite3
import sys
import threading
import urllib.request
from datetime import date, timedelta
from pathlib import Path

import pytest

from mediatheque import recommandations as reco
from mediatheque.adherents import Adherent
from mediatheque.auth import ADHERENT, RESPONSABLE
from mediatheque.documents import Livre
from mediatheque.emprunt import Emprunt
from mediatheque.exceptions import AccesRefuseError
from mediatheque.mediatheque import Mediatheque
from mediatheque.session import ouvrir_session
from mediatheque.web import app as module_app
from mediatheque.web import create_app
from outils_web import MDP, client_connecte, poster, variable_interne, verrou_tenu
from outils_web import (web_admin, web_app, web_db, web_ines,  # noqa: F401 (fixtures)
                        web_lea)

RACINE = Path(__file__).resolve().parents[2]
AUJ = date.today()


def _jours(n):
    return AUJ - timedelta(days=n)


# ====================================================== confidentialite (F1)
def _fonds_sans_fiche(victime_a_lu_d005):
    """Six livres sans fiche, meme epoque, auteurs distincts : AUCUNE ressemblance
    de contenu (score 0,5 < SEUIL). L'espion (A002) a lu D001 et D002 recemment ;
    la victime (A001) a lu D001 et D002 il y a 100 jours, et peut-etre D005
    (hors de la fenetre des « populaires » de 90 jours)."""
    m = Mediatheque()
    for i in range(1, 7):
        m.ajouter_document(Livre(f"D00{i}", f"Titre {i}", 2000, f"Auteur {i}"))
    m.ajouter_adherent(Adherent("A001", "Victime", "Vera", "standard"))
    m.ajouter_adherent(Adherent("A002", "Espion", "Eric", "standard"))
    lus = ["D001", "D002"] + (["D005"] if victime_a_lu_d005 else [])
    for k, d in enumerate(lus):
        m.ajouter_emprunt(Emprunt(d, "A001", _jours(100 + k), _jours(95 + k)))
    for k, d in enumerate(["D001", "D002"]):
        m.ajouter_emprunt(Emprunt(d, "A002", _jours(20 + k), _jours(10 + k)))
    m.creer_compte("espion", MDP, ADHERENT, "A002")
    return m


def _suggestions_espion(victime_a_lu_d005):
    s = ouvrir_session(_fonds_sans_fiche(victime_a_lu_d005), "espion", MDP)
    return [(x["document"].id, x["raison"]) for x in s.pour_moi()]


def test_f1_pour_moi_ne_depend_pas_d_un_seul_autre_lecteur():
    """La seule difference entre les deux mondes est un emprunt de la victime.
    L'espion voit apparaitre D005 « Parce que vous avez lu Titre 1 », alors que
    rien dans le contenu ne relie ces livres : il apprend que quelqu'un qui a lu
    les memes livres que lui (souvent identifiable : nb_prets = 2) a lu D005."""
    sans = _suggestions_espion(False)
    avec = _suggestions_espion(True)
    assert sans == []
    assert avec == sans, avec   # observe : [('D005', 'Parce que vous avez lu « Titre 1 »')]


def test_f1_similaires_ne_depend_pas_d_un_seul_autre_lecteur():
    def voisins(victime):
        m = Mediatheque()
        for i in range(1, 7):
            m.ajouter_document(Livre(f"D00{i}", f"Titre {i}", 2000, f"Auteur {i}"))
        m.ajouter_adherent(Adherent("A001", "Victime", "Vera", "standard"))
        m.ajouter_adherent(Adherent("A002", "Espion", "Eric", "standard"))
        m.ajouter_emprunt(Emprunt("D001", "A001", _jours(160), _jours(155)))  # connu de l'espion
        # l'espion a lu D001 et « sonde » D005 en l'empruntant lui aussi
        m.ajouter_emprunt(Emprunt("D001", "A002", _jours(20), _jours(10)))
        m.ajouter_emprunt(Emprunt("D005", "A002", _jours(5), _jours(2)))
        if victime:
            m.ajouter_emprunt(Emprunt("D005", "A001", _jours(150), _jours(140)))
        m.creer_compte("espion", MDP, ADHERENT, "A002")
        s = ouvrir_session(m, "espion", MDP)
        return [d.id for d, _ in s.similaires("D001")]

    assert voisins(False) == []
    assert voisins(True) == voisins(False)   # observe : ['D005']


def test_fiche_d_un_lecteur_ne_contient_ni_nom_ni_numero(web_app, web_ines):
    """D001 est chez lea (A001) : ines voit « Sorti, retour prevu », jamais qui."""
    page = web_ines.get("/document/D001").get_data(as_text=True)
    assert "Sorti" in page and "retour prévu" in page
    for indice in ("A001", "Martin", "Historique des prêts"):
        assert indice not in page
    m = web_app.extensions["mediatheque"]
    s = ouvrir_session(m, "ines", MDP)
    assert s.fiche("D001")["historique"] is None


def test_historique_des_prets_visible_du_responsable_seulement(web_admin, web_lea):
    assert "Historique des prêts" in web_admin.get("/document/D002").get_data(as_text=True)
    assert "Historique des prêts" not in web_lea.get("/document/D002").get_data(as_text=True)


def test_pour_moi_d_un_autre_numero_refuse(web_app):
    m = web_app.extensions["mediatheque"]
    with pytest.raises(AccesRefuseError):
        ouvrir_session(m, "lea", MDP).pour_moi("A003")
    assert isinstance(ouvrir_session(m, "admin", MDP).pour_moi("A003"), list)


def test_raison_ne_cite_que_les_lectures_du_demandeur():
    m = _fonds_sans_fiche(True)
    s = ouvrir_session(m, "espion", MDP)
    lus = {m[e.id_document].titre for e in m.emprunts if e.numero_adherent == "A002"}
    for x in s.pour_moi():
        if x["raison"].startswith("Parce que"):
            assert any(f"« {t} »" in x["raison"] for t in lus)


# ============================================================ XSS (sain)
CHARGE = '"><img src=x onerror=alert(1)></textarea><script>alert(2)</script>'


@pytest.fixture
def doc_piege(web_admin):
    r = poster(web_admin, "/admin/documents", page="/admin/gestion",
               type="livre", id="D099", titre="Piège" + CHARGE[:40], annee="2020",
               extra="Auteur" + CHARGE[:40], genre="G" + CHARGE[:50],
               themes="javascript:alert(1)," + CHARGE[:39], resume="R" + CHARGE)
    assert r.status_code == 302
    return "D099"


@pytest.mark.parametrize("url", ["/document/D099", "/catalogue", "/catalogue?q=g",
                                 "/admin/gestion"])
def test_champs_de_fiche_echappes(web_admin, doc_piege, url):
    page = web_admin.get(url).get_data(as_text=True)
    assert "<img src=x" not in page and "<script>alert" not in page
    assert "onerror=alert" not in page.replace("onerror=alert(1)&gt;", "")


def test_champs_de_fiche_echappes_cote_lecteur(web_app, doc_piege):
    c = client_connecte(web_app, "ines")
    for url in ("/document/D099", "/catalogue", "/compte"):
        page = c.get(url).get_data(as_text=True)
        assert "<img src=x" not in page and "<script>" not in page


def test_liens_de_theme_restent_internes(web_admin, doc_piege):
    page = web_admin.get("/document/D099").get_data(as_text=True)
    assert 'href="javascript' not in page
    assert "/catalogue?q=javascript" in page


def test_xss_depuis_un_csv_importe(dossier_data, tmp_path):
    (dossier_data / "documents.csv").write_text(
        "id,type,titre,annee,extra,genre,themes,resume,editeur,pages,isbn,public\n"
        f'D009,livre,T,2000,A,"{CHARGE[:50].replace(chr(34), chr(34) * 2)}",x|y,'
        f'"{CHARGE.replace(chr(34), chr(34) * 2)}",E,10,,adulte\n', encoding="utf-8")
    (dossier_data / "emprunts.csv").write_text(
        "id_document,numero_adherent,date_emprunt,date_retour\n", encoding="utf-8")
    m = Mediatheque.charger(dossier_data)
    m.creer_compte("ines", MDP, ADHERENT, "A003")
    m.sauvegarder(tmp_path / "x.db")
    c = client_connecte(create_app(tmp_path / "x.db", secret_key="t", testing=True), "ines")
    for url in ("/document/D009", "/catalogue"):
        page = c.get(url).get_data(as_text=True)
        assert "<img src=x" not in page and "<script>" not in page


def test_fiches_demo_sans_balise():
    sys.path.insert(0, str(RACINE / "scripts"))
    try:
        from fiches_demo import FICHES
    finally:
        sys.path.remove(str(RACINE / "scripts"))
    texte = json.dumps(FICHES, ensure_ascii=False)
    assert "<" not in texte and "javascript:" not in texte.lower()


# =============================================== chemins et couvertures (sain)
@pytest.mark.parametrize("ident", ["../../app", "D1/../../x", "D001\x00", "D1.jpg/..",
                                   "..\\D001", "D0000001"])
def test_couverture_refuse_les_identifiants_hostiles(ident):
    class Faux:
        id = ident
    assert module_app.couverture(Faux()) is None


@pytest.mark.parametrize("url", ["/document/..%2F..%2Fapp", "/document/D001%00",
                                 "/document/D1234567", "/document/d001",
                                 "/static/couvertures/..%2F..%2Fapp.py",
                                 "/static/couvertures/../../app.py"])
def test_routes_sans_traversee(web_lea, url):
    assert web_lea.get(url).status_code == 404


def test_polyglotte_jpeg_html_servi_comme_image(web_app, web_lea, tmp_path, monkeypatch):
    """Un « JPEG » qui contient du HTML est servi en image/jpeg avec nosniff et
    la CSP script-src 'none' : le navigateur ne l'interprete pas comme une page."""
    statique = tmp_path / "static"
    (statique / "couvertures").mkdir(parents=True)
    (statique / "couvertures" / "D001.jpg").write_bytes(
        b"\xff\xd8\xff\xe0" + b"<html><script>alert(1)</script></html>" * 100)
    monkeypatch.setattr(module_app, "DOSSIER_COUVERTURES", statique / "couvertures")
    web_app.static_folder = str(statique)
    assert "/static/couvertures/D001.jpg" in web_lea.get("/document/D001").get_data(as_text=True)
    r = web_lea.get("/static/couvertures/D001.jpg")
    assert r.status_code == 200
    assert r.mimetype == "image/jpeg"
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert "script-src 'none'" in r.headers["Content-Security-Policy"]


# ============================================== script de telechargement
def _script():
    spec = importlib.util.spec_from_file_location(
        "telecharger_couvertures_audit", RACINE / "scripts" / "telecharger_couvertures.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _Reponse:
    def __init__(self, donnees, type_mime):
        self._donnees, self.headers = donnees, _Entetes(type_mime)

    def read(self, n=-1):
        return self._donnees if n < 0 else self._donnees[:n]

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class _Entetes:
    def __init__(self, type_mime):
        self._t = type_mime

    def get_content_type(self):
        return self._t


JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 5000


def _simuler(monkeypatch, donnees=JPEG, type_mime="image/jpeg"):
    vues = []

    def urlopen(requete, timeout=None):
        url = requete.full_url
        vues.append(url)
        if "search.json" in url:
            return _Reponse(json.dumps({"docs": [{"cover_i": 42}]}).encode(), "application/json")
        return _Reponse(donnees, type_mime)

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    return vues


@pytest.mark.parametrize("donnees,type_mime,motif", [
    (b"<html>" + b"x" * 5000, "image/jpeg", "pas un JPEG"),
    (JPEG, "text/html", "pas un JPEG"),
    (b"\xff\xd8\xff" + b"x" * 100, "image/jpeg", "trop petite"),
    (b"\xff\xd8\xff" + b"x" * (3 * 1024 * 1024), "image/jpeg", "volumineuse"),
])
def test_script_refuse_faux_jpeg_et_reponses_enormes(monkeypatch, tmp_path, donnees,
                                                     type_mime, motif):
    s = _script()
    _simuler(monkeypatch, donnees, type_mime)
    with pytest.raises(ValueError, match=motif):
        s.telecharger(42, tmp_path / "D001.jpg")
    assert list(tmp_path.iterdir()) == []


def test_script_isbn_et_titre_encodes_dans_l_url(monkeypatch):
    s = _script()
    vues = _simuler(monkeypatch)
    livre = Livre("D001", "a&b=c/../#x", 2000, "x?y").completer_fiche()
    assert s.chercher_couverture(livre) == 42
    assert vues[0].startswith("https://openlibrary.org/search.json?")
    assert "&b=" not in vues[0] and "#" not in vues[0]


def _data_avec_identifiant(dossier, ident):
    dossier.mkdir()
    (dossier / "documents.csv").write_text(
        f"id,type,titre,annee,extra\n{ident},livre,T,2000,A\n", encoding="utf-8")
    (dossier / "adherents.csv").write_text("numero,nom,prenom,type\n", encoding="utf-8")
    (dossier / "emprunts.csv").write_text(
        "id_document,numero_adherent,date_emprunt,date_retour\n", encoding="utf-8")


@pytest.mark.xfail(strict=True, reason="faille F3 : le script ecrit hors de static/couvertures "
                   "si un identifiant du fonds contient ../ (aucun controle a l'import)")
def test_f3_script_n_ecrit_pas_hors_du_dossier(monkeypatch, tmp_path):
    s = _script()
    _simuler(monkeypatch)
    dossier = tmp_path / "static" / "couvertures"
    monkeypatch.setattr(s, "DOSSIER", dossier)
    monkeypatch.setattr(s.time, "sleep", lambda _: None)
    _data_avec_identifiant(tmp_path / "data", "../../evil")
    monkeypatch.setattr(sys, "argv", ["x", "--depuis", str(tmp_path / "data")])
    s.main()
    assert not (tmp_path / "evil.jpg").exists()   # observe : ecrit dans tmp_path/


class _Redirige(http.server.BaseHTTPRequestHandler):
    cible = ""

    def do_GET(self):
        self.send_response(302)
        self.send_header("Location", self.cible)
        self.end_headers()

    def log_message(self, *_):
        pass


class _Interne(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        corps = b"\xff\xd8\xff" + b"donnees internes " * 200
        self.send_response(200)
        self.send_header("Content-Type", "image/jpeg")
        self.send_header("Content-Length", str(len(corps)))
        self.end_headers()
        self.wfile.write(corps)

    def log_message(self, *_):
        pass


@pytest.fixture
def serveurs_locaux():
    interne = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Interne)
    redirige = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Redirige)
    _Redirige.cible = f"http://127.0.0.1:{interne.server_port}/admin"
    for srv in (interne, redirige):
        threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{redirige.server_port}/b/id/1-L.jpg"
    for srv in (interne, redirige):
        srv.shutdown()
        srv.server_close()


@pytest.mark.xfail(strict=True, reason="faille F4 : le script suit toute redirection "
                   "(autre hote, http en clair) sans liste d'hotes autorises")
def test_f4_script_ne_suit_pas_une_redirection_vers_un_autre_hote(serveurs_locaux):
    s = _script()
    try:
        donnees, _ = s.lire(serveurs_locaux)
    except Exception:
        return  # comportement attendu : redirection refusee
    assert b"donnees internes" not in donnees   # observe : contenu de l'autre hote lu


# =================================================== migration SQLite (sain)
def _base_ancienne(chemin):
    con = sqlite3.connect(chemin)
    con.executescript("""
        CREATE TABLE documents (id TEXT PRIMARY KEY, type TEXT NOT NULL, titre TEXT NOT NULL,
                                annee INTEGER NOT NULL, extra TEXT NOT NULL);
        INSERT INTO documents VALUES ('D001', 'livre', 'T', 2000, 'A');""")
    con.commit()
    con.close()


def test_migration_d_une_base_ancienne(tmp_path):
    _base_ancienne(tmp_path / "v1.db")
    m = Mediatheque.charger(tmp_path / "v1.db")
    assert m["D001"].fiche["genre"] == "" and m["D001"].themes == ()
    con = sqlite3.connect(tmp_path / "v1.db")
    colonnes = {l[1] for l in con.execute("PRAGMA table_info(documents)")}
    con.close()
    assert {"genre", "themes", "resume", "editeur", "pages", "isbn", "public"} <= colonnes


def test_migration_sans_entree_utilisateur():
    from mediatheque import stockage_sqlite
    import inspect
    source = inspect.getsource(stockage_sqlite._migrer)
    assert "_COLONNES_FICHE.items()" in source
    for nom in stockage_sqlite._COLONNES_FICHE:
        assert nom.isidentifier()


def test_base_corrompue_refusee_sans_etre_modifiee(tmp_path):
    chemin = tmp_path / "x.db"
    chemin.write_bytes(b"pas une base sqlite" * 100)
    avant = chemin.read_bytes()
    with pytest.raises(sqlite3.DatabaseError):
        Mediatheque.charger(chemin)
    assert chemin.read_bytes() == avant


def test_base_falsifiee_fiche_trop_longue_refusee(tmp_path):
    _base_ancienne(tmp_path / "v1.db")
    Mediatheque.charger(tmp_path / "v1.db")  # migre
    con = sqlite3.connect(tmp_path / "v1.db")
    con.execute("UPDATE documents SET resume = ?", ("x" * 50_000,))
    con.commit()
    con.close()
    with pytest.raises(ValueError, match="trop long"):
        Mediatheque.charger(tmp_path / "v1.db")


# ================================================= validation de la fiche
def test_ajouter_document_refuse_une_cle_inattendue(web_app):
    m = web_app.extensions["mediatheque"]
    s = ouvrir_session(m, "admin", MDP)
    with pytest.raises(ValueError, match="inconnu"):
        s.ajouter_document("livre", "D050", "T", "2000", "A", _source="x")
    assert "D050" not in m


def test_formulaire_ignore_les_champs_en_trop_et_borne_les_themes(web_app, web_admin):
    themes = ",".join(f"theme{i}" + "x" * 100 for i in range(500))
    r = poster(web_admin, "/admin/documents", page="/admin/gestion", type="livre", id="D051",
               titre="T", annee="2000", extra="A", themes=themes[:60_000],
               pages="-5", isbn="pas un isbn", public="<b>", _source="x", CLE="dvd")
    assert r.status_code == 302
    d = web_app.extensions["mediatheque"]["D051"]
    assert len(d.themes) == 8 and all(len(t) <= 40 for t in d.themes)
    assert (d.pages, d.isbn, d.public, d.CLE) == (0, "", "", "livre")


def test_resume_trop_long_refuse_sans_ajout(web_app, web_admin):
    poster(web_admin, "/admin/documents", page="/admin/gestion", type="livre", id="D052",
           titre="T", annee="2000", extra="A", resume="x" * 1201)
    assert "D052" not in web_app.extensions["mediatheque"]


def test_f5_themes_identiques_apres_rechargement(web_app, web_admin):
    poster(web_admin, "/admin/documents", page="/admin/gestion", type="livre", id="D053",
           titre="T", annee="2000", extra="A", themes="science|fiction, polar")
    m = web_app.extensions["mediatheque"]
    # corrige (F5) : un theme contenant le separateur est refuse, rien n'est cree
    assert "D053" not in m
    assert "D053" not in Mediatheque.charger(m._source)
    poster(web_admin, "/admin/documents", page="/admin/gestion", type="livre", id="D054",
           titre="T", annee="2000", extra="A", themes="science  fiction,\n polar")
    avant = m["D054"].themes                      # blancs et retours normalises
    assert avant == ("science fiction", "polar")
    assert Mediatheque.charger(m._source)["D054"].themes == avant


# ======================================================== deni de service (F2)
@pytest.fixture
def grosse_base(tmp_path):
    """1 000 documents avec fiche, 100 lecteurs de 40 prets chacun (jeu reduit
    pour la vitesse des tests ; mesures sur 2 000 x 300 dans le rapport)."""
    import random
    rng = random.Random(1)
    m = Mediatheque()
    genres, themes = [f"g{i}" for i in range(20)], [f"t{i}" for i in range(60)]
    for i in range(1000):
        m.ajouter_document(Livre(f"D{i:04d}", f"T{i}", rng.randint(1950, 2024),
                                 f"Auteur {i % 300}").completer_fiche(
            genre=rng.choice(genres), themes=rng.sample(themes, 4)))
    for j in range(100):
        m.ajouter_adherent(Adherent(f"A{j:03d}", "N", "P", "premium"))
        for k, i in enumerate(rng.sample(range(1000), 40)):
            m.ajouter_emprunt(Emprunt(f"D{i:04d}", f"A{j:03d}", _jours(200 - k), _jours(199 - k)))
    m.creer_compte("gros", MDP, ADHERENT, "A001")
    m.sauvegarder(tmp_path / "gros.db")
    return create_app(tmp_path / "gros.db", secret_key="t", testing=True)


def test_f2_cout_de_la_page_compte_borne(grosse_base, monkeypatch):
    c = client_connecte(grosse_base, "gros")
    verrou = variable_interne(grosse_base, "verrou")
    appels, sous_verrou = [0], []
    vraie = reco.ressemblance

    def comptee(a, b, co=None):
        if not appels[0]:
            sous_verrou.append(verrou_tenu(verrou))
        appels[0] += 1
        return vraie(a, b, co)

    monkeypatch.setattr(reco, "ressemblance", comptee)
    assert c.get("/compte").status_code == 200
    assert sous_verrou == [True]
    # borne raisonnable : quelques passes sur le fonds (1 000 documents)
    assert appels[0] <= 4 * 1000, appels[0]   # observe : 40 x 1 000 = 40 000
