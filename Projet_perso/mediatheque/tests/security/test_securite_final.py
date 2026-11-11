"""Audit de securite final (2026-11-11) : journal des actions, fiche lecteur,
saisie libre du guichet, pagination, puis passage transversal.

Chaque faille Zx est prouvee par un test `xfail(strict=True)` qui echoue tant
qu'elle existe. Les autres tests verifient des points sains. Toujours sur une
copie de data/ dans tmp_path (fixtures de `outils_web`), jamais sur data/.
"""
import dataclasses
import random
import re
import sqlite3
from datetime import date, timedelta
from urllib.parse import urlsplit

import pytest

from mediatheque import session as module_session
from mediatheque.adherents import Adherent
from mediatheque.auth import ADHERENT
from mediatheque.documents import Livre
from mediatheque.emprunt import Emprunt
from mediatheque.exceptions import AuthentificationError, MediathequeError
from mediatheque.journal import EntreeJournal
from mediatheque.mediatheque import Mediatheque
from mediatheque.session import Session, ouvrir_session
from mediatheque.web import create_app
from outils_web import (MDP, client_connecte, connecter, poster, variable_interne,
                        verrou_tenu)
from outils_web import (web_admin, web_app, web_db, web_lea,  # noqa: F401 (fixtures)
                        web_app_prod)

ROUTES_FICHE = ["/admin/lecteurs/A001/modifier", "/admin/lecteurs/A001/annuler/D003",
                "/admin/lecteurs/A001/retour/D001"]


def _lignes(db, table):
    with sqlite3.connect(db) as con:
        return con.execute(f"SELECT * FROM {table} ORDER BY rowid").fetchall()  # noqa: S608 (constante)


def _etat_base(db):
    return {t: _lignes(db, t) for t in ("adherents", "emprunts", "reservations", "journal",
                                         "comptes")}


def _jours(n):
    return date.today() - timedelta(days=n)


# ================================================================ Z1 (Haute)
@pytest.fixture
def hugo_cinq_prets(web_db):
    """Hugo (A002, premium) a 5 documents chez lui : D003 et D006 a D009."""
    m = Mediatheque.charger(web_db)
    for i in range(6, 10):
        m.ajouter_document(Livre(f"D{i:03d}", f"Titre {i}", 2000, "Auteur"))
        m.emprunter(f"D{i:03d}", "A002")
    m.sauvegarder()
    return web_db


def _retrograder_hugo(app):
    admin = client_connecte(app, "admin")
    r = poster(admin, "/admin/lecteurs/A002/modifier", page="/connexion",
               nom="Durand", prenom="Hugo", type="standard")
    assert r.status_code == 302


def test_z1_retrogradation_garde_la_base_lisible(hugo_cinq_prets):
    app = create_app(hugo_cinq_prets, secret_key="t", testing=True)
    _retrograder_hugo(app)
    Mediatheque.charger(hugo_cinq_prets)  # redemarrage du site : ne doit pas lever


def test_z1_erreur_suivante_reste_un_message(hugo_cinq_prets):
    app = create_app(hugo_cinq_prets, secret_key="t", testing=False)
    _retrograder_hugo(app)
    lea = client_connecte(app, "lea")
    # D002 est en rayon : reservation refusee, d'ou m.recharger() dans `action`
    assert poster(lea, "/reserver/D002", page="/connexion").status_code == 302


# =============================================================== Z2 (Moyenne)
@pytest.fixture
def base_moyenne(tmp_path):
    """300 documents, 30 lecteurs de 40 prets rendus (1 200 prets)."""
    rng = random.Random(2)
    m = Mediatheque()
    for i in range(300):
        m.ajouter_document(Livre(f"D{i:04d}", f"Titre {i}", 2000, "Auteur"))
    for j in range(30):
        m.ajouter_adherent(Adherent(f"A{j:03d}", "N", "P", "premium"))
        for k, i in enumerate(rng.sample(range(300), 40)):
            m.ajouter_emprunt(Emprunt(f"D{i:04d}", f"A{j:03d}", _jours(400 - 2 * k),
                                      _jours(399 - 2 * k)))
    m.creer_compte("lea", MDP, ADHERENT, "A001")
    m.sauvegarder(tmp_path / "moy.db")
    return create_app(tmp_path / "moy.db", secret_key="t", testing=True)


def test_z2_cout_du_catalogue_lineaire(base_moyenne, monkeypatch):
    lea = client_connecte(base_moyenne, "lea")
    m = base_moyenne.extensions["mediatheque"]
    compteur = [0]

    class ListeComptee(list):
        def __iter__(self):
            for e in list.__iter__(self):
                compteur[0] += 1
                yield e

    monkeypatch.setattr(m, "_emprunts", ListeComptee(m._emprunts))
    assert lea.get("/catalogue").status_code == 200
    # borne lineaire : quelques passes sur les documents et sur les prets
    assert compteur[0] <= 20 * (300 + 1200), compteur[0]  # observe : ~1 400 000


def test_z2_index_identiques_a_une_recherche_lineaire(tmp_path):
    """Les index des prets en cours et des mises de cote donnent exactement ce
    que donnait le parcours des listes, apres une suite d'operations au hasard,
    une sauvegarde et un rechargement."""
    from mediatheque.reservation import DISPONIBLE
    rng = random.Random(7)
    m = Mediatheque()
    for i in range(12):
        m.ajouter_document(Livre(f"D{i:03d}", f"T{i}", 2000, "A"))
    for j in range(6):
        m.ajouter_adherent(Adherent(f"A{j:03d}", "N", "P", "premium"))
    m.sauvegarder(tmp_path / "idx.db")
    m = Mediatheque.charger(tmp_path / "idx.db")

    def verifier():
        for d in m:
            lin_e = next((e for e in m._emprunts if e.id_document == d.id and e.en_cours), None)
            lin_r = next((r for r in m._reservations
                          if r.id_document == d.id and r.statut == DISPONIBLE), None)
            assert m._emprunt_en_cours(d.id) is lin_e
            assert m._mise_de_cote(d.id) is lin_r

    jour = date(2026, 1, 1)
    for _ in range(600):
        jour += timedelta(days=rng.choice((0, 0, 1, 2, 5)))
        doc, num = f"D{rng.randrange(12):03d}", f"A{rng.randrange(6):03d}"
        op = rng.choice(("emprunter", "retourner", "reserver", "annuler", "actualiser",
                         "recharger"))
        try:
            if op == "emprunter":
                m.emprunter(doc, num, jour)
            elif op == "retourner":
                m.retourner(doc, jour)
            elif op == "reserver":
                m.reserver(doc, num, jour)
            elif op == "annuler":
                m.annuler_reservation(doc, num, jour)
            elif op == "actualiser":
                m.actualiser_reservations(jour)
            else:
                m.sauvegarder()
                m.recharger()
        except MediathequeError:
            pass
        verifier()


# =============================================================== Z3 (Moyenne)
@pytest.fixture
def base_avec_journal(web_db):
    m = Mediatheque.charger(web_db)
    for i in range(500):
        m.journaliser("admin", "pret", "D001", f"entree {i}")
    m.sauvegarder()
    return web_db


def test_z3_une_reservation_ne_reecrit_pas_le_journal(base_avec_journal):
    app = create_app(base_avec_journal, secret_key="t", testing=True)
    avant = _lignes(base_avec_journal, "journal")
    lea = client_connecte(app, "lea")
    assert poster(lea, "/reserver/D003", page="/connexion").status_code == 302
    assert _lignes(base_avec_journal, "reservations")  # la reservation est bien enregistree
    assert _lignes(base_avec_journal, "journal") == avant  # ids et contenu inchanges


@pytest.mark.parametrize("requete", ["UPDATE journal SET detail = 'falsifie'",
                                     "DELETE FROM journal"])
def test_z3_journal_en_ajout_seul_dans_la_base(base_avec_journal, requete):
    with sqlite3.connect(base_avec_journal) as con, pytest.raises(sqlite3.DatabaseError):
        con.execute(requete)


def test_z3_declencheurs_ajoutes_aux_bases_existantes(tmp_path):
    """Une base creee avant le correctif (sans declencheurs) les recoit a l'ouverture."""
    db = tmp_path / "ancienne.db"
    with sqlite3.connect(db) as con:
        con.execute("CREATE TABLE journal (id INTEGER PRIMARY KEY AUTOINCREMENT, horodatage "
                    "TEXT NOT NULL, acteur TEXT NOT NULL, action TEXT NOT NULL, cible TEXT "
                    "NOT NULL DEFAULT '', detail TEXT NOT NULL DEFAULT '')")
        con.execute("INSERT INTO journal (horodatage, acteur, action) "
                    "VALUES ('2026-01-01T10:00:00', 'admin', 'connexion')")
    Mediatheque.charger(db)
    with sqlite3.connect(db) as con, pytest.raises(sqlite3.DatabaseError):
        con.execute("DELETE FROM journal")


def test_z3_sauvegardes_successives_ajoutent_seulement(base_avec_journal):
    m = Mediatheque.charger(base_avec_journal)
    avant = _lignes(base_avec_journal, "journal")
    m.journaliser("admin", "pret", "D002", "nouvelle")
    m.sauvegarder()
    m.sauvegarder()  # rien de nouveau : rien n'est ajoute
    apres = _lignes(base_avec_journal, "journal")
    assert apres[:len(avant)] == avant and len(apres) == len(avant) + 1
    assert apres[-1][-1] == "nouvelle"


def test_z3_recharger_sans_relire_un_journal_inchange(base_avec_journal, monkeypatch):
    from mediatheque import stockage_sqlite
    m = Mediatheque.charger(base_avec_journal)
    lectures = [0]
    vraie = stockage_sqlite._lire_journal

    def comptee(con):
        lectures[0] += 1
        return vraie(con)

    monkeypatch.setattr(stockage_sqlite, "_lire_journal", comptee)
    m.journaliser("admin", "pret", "D002", "ecrite")
    m.sauvegarder()
    m.journaliser("admin", "pret", "D002", "perdue")  # jamais sauvegardee
    m.recharger()
    assert lectures[0] == 0
    assert [j.detail for j in m.journal][-1] == "ecrite"
    assert m.journal == Mediatheque.charger(base_avec_journal).journal
    # la base change ailleurs (nouvelle entree) : le journal est bien relu
    autre = Mediatheque.charger(base_avec_journal)
    autre.journaliser("admin", "connexion")
    autre.sauvegarder()
    m.recharger()
    assert lectures[0] >= 1 and m.journal[-1].action == "connexion"


def test_z3_purge_reservee_au_responsable_et_journalisee(base_avec_journal):
    from datetime import datetime
    from mediatheque.exceptions import AccesRefuseError
    from mediatheque.journal import CONSERVATION_JOURNAL_JOURS
    from mediatheque.purge_journal import purger
    assert CONSERVATION_JOURNAL_JOURS == 365
    m = Mediatheque.charger(base_avec_journal)
    vieux = datetime.now().replace(microsecond=0) - timedelta(days=400)
    for i in range(3):
        m.journaliser("admin", "pret", "D001", f"ancienne {i}", quand=vieux)
    m.sauvegarder()
    total = len(m.journal)
    # un adherent, ou un compte qui n'est pas celui du registre : refuse
    lea = m.comptes.authentifier("lea", MDP)
    with pytest.raises(AccesRefuseError):
        m.purger_journal(lea)
    with pytest.raises(AccesRefuseError):
        m.purger_journal(dataclasses.replace(m.comptes.get("admin")))
    with pytest.raises(AccesRefuseError):
        purger(base_avec_journal, "lea", MDP)  # par la commande : adherent refuse
    with pytest.raises(AuthentificationError):
        purger(base_avec_journal, "admin", "MauvaisMdp1")
    assert len(_lignes(base_avec_journal, "journal")) == total
    # le responsable purge : 3 anciennes supprimees, la purge est journalisee
    assert purger(base_avec_journal, "admin", MDP) == 3
    lignes = _lignes(base_avec_journal, "journal")
    assert len(lignes) == total - 3 + 1
    assert not any("ancienne" in l[-1] for l in lignes)
    assert lignes[-1][2:4] == ("admin", "purge_journal")
    # les declencheurs sont toujours en place apres la purge
    with sqlite3.connect(base_avec_journal) as con, pytest.raises(sqlite3.DatabaseError):
        con.execute("DELETE FROM journal")


def test_z3_purge_jamais_automatique(base_avec_journal):
    from datetime import datetime
    m = Mediatheque.charger(base_avec_journal)
    vieux = datetime.now().replace(microsecond=0) - timedelta(days=4000)
    m.journaliser("admin", "pret", "D001", "tres ancienne", quand=vieux)
    m.sauvegarder()
    app = create_app(base_avec_journal, secret_key="t", testing=True)
    client_connecte(app, "admin")
    poster(client_connecte(app, "lea"), "/reserver/D003", page="/connexion")
    assert any("tres ancienne" in l[-1] for l in _lignes(base_avec_journal, "journal"))


# ================================================================ Z4 (Basse)
@pytest.mark.xfail(strict=True, reason="faille Z4 : /admin/lecteurs/<numero>/retour/<id> "
                   "ignore <numero> et clot le pret d'un autre lecteur")
def test_z4_retour_depuis_la_fiche_verifie_le_lecteur(web_app, web_admin, web_db):
    # D003 est chez Hugo (A002), pas chez Lea (A001) : page perimee ou formulaire modifie
    poster(web_admin, "/admin/lecteurs/A001/retour/D003", page="/connexion")
    m = Mediatheque.charger(web_db)
    assert m._emprunt_en_cours("D003") is not None
    assert m._emprunt_en_cours("D003").numero_adherent == "A002"


# ================================================================ Z5 (Basse)
@pytest.mark.xfail(strict=True, reason="faille Z5 : Session.adherents() renvoie les Adherent "
                   "du modele : modification sans journal, persistee a la sauvegarde")
def test_z5_adherents_renvoie_des_copies(web_db):
    m = Mediatheque.charger(web_db)
    s = ouvrir_session(m, "admin", MDP)
    a = next(x for x in s.adherents() if x.numero == "A001")
    a.type = "premium"
    assert m.adherent("A001").type == "standard"


@pytest.mark.xfail(strict=True, reason="faille Z5 : Session.reserver() renvoie la Reservation "
                   "du modele : un adherent la reaffecte a un autre numero")
def test_z5_reservation_renvoyee_a_l_adherent_est_une_copie(web_db):
    m = Mediatheque.charger(web_db)
    lea = ouvrir_session(m, "lea", MDP)
    r = lea.reserver("D003")
    r.numero_adherent = "A003"
    assert m.reservations_de("A003") == []


# ================================================================ Z6 (Basse)
@pytest.mark.xfail(strict=True, reason="faille Z6 : la connexion du personnel est journalisee "
                   "hors du verrou global (course avec recharger/sauvegarder)")
def test_z6_connexion_du_personnel_journalisee_sous_verrou(web_app, monkeypatch):
    m = web_app.extensions["mediatheque"]
    verrou = variable_interne(web_app, "verrou")
    vraie, tenu = m.journaliser, []

    def journaliser(*args, **kwargs):
        tenu.append(verrou_tenu(verrou))
        return vraie(*args, **kwargs)

    monkeypatch.setattr(m, "journaliser", journaliser)
    assert connecter(web_app.test_client(), "admin").status_code == 302
    assert tenu == [True]


# ================================================================ Z7 (Basse)
@pytest.mark.xfail(strict=True, reason="faille Z7 : le n° d'inventaire accepte les chiffres "
                   "Unicode et n'a pas de longueur maximale")
@pytest.mark.parametrize("ident", ["D١٢٣", "D" + "1" * 50])
def test_z7_numero_d_inventaire_ascii_et_borne(web_db, ident):
    m = Mediatheque.charger(web_db)
    s = ouvrir_session(m, "admin", MDP)
    with pytest.raises(MediathequeError):
        s.ajouter_document("livre", ident, "Titre", "2000", "Auteur")
    assert ident not in m


@pytest.mark.xfail(strict=True, reason="faille Z7 : le n° de carte accepte les chiffres Unicode")
def test_z7_numero_de_carte_ascii():
    with pytest.raises(ValueError):
        Adherent("A١٢٣", "Nom", "Prenom", "standard")


# ======================================================= journal : points sains
def test_journal_ne_contient_aucun_mot_de_passe(web_app, web_admin, web_db):
    secrets_saisis = ["MotSecret987", "AutreSecret654"]
    r = poster(web_admin, "/admin/adherents", page="/connexion", numero="A004", nom="Neuf",
               prenom="Lecteur", type="standard", identifiant="lecteur.neuf",
               mot_de_passe=secrets_saisis[0])
    assert r.status_code == 302
    r = poster(web_admin, "/admin/comptes/mot-de-passe", page="/connexion",
               identifiant="lea", mot_de_passe=secrets_saisis[1], retour="A001")
    assert r.status_code == 302
    connecter(web_app.test_client(), "admin")
    m = web_app.extensions["mediatheque"]
    actions = {j.action for j in m.journal}
    assert {"connexion", "ajout_lecteur", "creation_compte", "reinit_mdp"} <= actions
    en_memoire = " ".join(f"{j.acteur} {j.cible} {j.detail}" for j in m.journal)
    en_base = " ".join(map(str, _lignes(web_db, "journal")))
    for mdp in [*secrets_saisis, MDP]:
        assert mdp not in en_memoire and mdp not in en_base


def test_journal_reserve_au_personnel(web_app, web_lea):
    assert web_lea.get("/admin/journal").status_code == 403
    r = web_app.test_client().get("/admin/journal")
    assert r.status_code == 302 and "/connexion" in r.headers["Location"]


def test_journal_echappe_et_liens_internes(web_admin):
    poster(web_admin, "/admin/documents", page="/connexion", type="livre", id="D006",
           titre="<script>alert(1)</script>", annee="2000", extra="Auteur")
    poster(web_admin, "/admin/adherents", page="/connexion", numero="A004",
           nom='"><img src=x onerror=alert(1)>', prenom="Eve", type="standard")
    page = web_admin.get("/admin/journal").get_data(as_text=True)
    assert "<script>alert" not in page and "<img src=x" not in page
    assert "&lt;script&gt;" in page
    table = page[page.index("<tbody>"):page.index("</tbody>")]
    assert 'href="/admin/lecteurs/A004"' in table
    for href in re.findall(r'href="([^"]*)"', table):
        assert href.startswith("/") and not href.startswith("//"), href


def test_journal_en_ajout_seul_par_l_api(web_app, web_admin):
    m = web_app.extensions["mediatheque"]
    assert isinstance(m.journal, tuple)
    entree = m.journal[0]
    with pytest.raises(dataclasses.FrozenInstanceError):
        entree.detail = "falsifie"
    with pytest.raises(ValueError):
        EntreeJournal(entree.horodatage, "admin", "suppression_journal")
    publiques = {n for n in dir(Session) if not n.startswith("_")}
    assert {n for n in publiques if "journal" in n} == {"journal"}
    for regle in web_app.url_map.iter_rules():
        if "journal" in regle.rule:
            assert "POST" not in regle.methods


@pytest.mark.parametrize("formule", ["gold", "", "Premium", "responsable", "premium "])
def test_formule_inconnue_refusee_sans_trace(web_app, web_admin, web_db, formule):
    avant = _etat_base(web_db)
    r = poster(web_admin, "/admin/lecteurs/A001/modifier", page="/connexion",
               nom="Martin", prenom="Lea", type=formule)
    assert r.status_code == 302
    assert _etat_base(web_db) == avant
    assert web_app.extensions["mediatheque"].adherent("A001").type == "standard"


# ================================================== fiche lecteur : points sains
def test_fiche_lecteur_reservee_au_personnel(web_app, web_lea, web_db):
    avant = _etat_base(web_db)
    assert web_lea.get("/admin/lecteurs/A001").status_code == 403
    for url in ROUTES_FICHE:
        r = poster(web_lea, url, page="/connexion", nom="X", prenom="Y", type="premium")
        assert r.status_code == 403, url
    assert _etat_base(web_db) == avant
    r = web_app.test_client().get("/admin/lecteurs/A001")
    assert r.status_code == 302 and "/connexion" in r.headers["Location"]


def test_fiche_lecteur_post_exigent_le_jeton_csrf(web_admin, web_db):
    avant = _etat_base(web_db)
    for url in ROUTES_FICHE:
        for data in ({}, {"csrf": ""}, {"csrf": "faux"}):
            r = web_admin.post(url, data={**data, "nom": "X", "prenom": "Y", "type": "premium"})
            assert r.status_code == 400, url
    assert _etat_base(web_db) == avant


@pytest.mark.parametrize("numero", ["A1", "A0001", "a001", "A001x", "A999", "..%2F..",
                                    "A١٢٣"])
def test_fiche_lecteur_numero_invalide(web_admin, numero):
    assert web_admin.get(f"/admin/lecteurs/{numero}").status_code == 404


@pytest.mark.parametrize("retour", ["https://evil.example", "//evil.example",
                                    "A001/../../x", "A001\r\nLocation: x"])
def test_retour_de_la_reinitialisation_reste_interne(web_admin, retour):
    r = poster(web_admin, "/admin/comptes/mot-de-passe", page="/connexion",
               identifiant="lea", mot_de_passe="Nouveau123", retour=retour)
    assert r.status_code == 302
    cible = urlsplit(r.headers["Location"])
    assert cible.netloc in ("", "localhost") and cible.path.startswith("/admin/")
    assert "evil" not in r.headers["Location"]


def test_retour_de_la_reinitialisation_vers_la_fiche(web_admin):
    r = poster(web_admin, "/admin/comptes/mot-de-passe", page="/connexion",
               identifiant="lea", mot_de_passe="Nouveau123", retour="A001")
    assert urlsplit(r.headers["Location"]).path == "/admin/lecteurs/A001"


def test_annulation_pour_un_lecteur_sans_reservation_refusee(web_app, web_admin, web_db):
    """La reservation annulee est bien celle du lecteur de l'URL (pas d'IDOR)."""
    m = Mediatheque.charger(web_db)
    m.reserver("D003", "A003")  # Ines attend D003
    m.sauvegarder()
    app = create_app(web_db, secret_key="t", testing=True)
    admin = client_connecte(app, "admin")
    poster(admin, "/admin/lecteurs/A001/annuler/D003", page="/connexion")  # Lea : rien
    assert Mediatheque.charger(web_db).reservations_de("A003")


def test_fiche_lecteur_renvoie_des_copies(web_db):
    m = Mediatheque.charger(web_db)
    s = ouvrir_session(m, "admin", MDP)
    f = s.fiche_lecteur("A001")
    f["adherent"].type = "premium"
    f["emprunts"][0]["document"].titre = "X"
    f["historique"][0]["document"].titre = "Y"
    assert m.adherent("A001").type == "standard"
    assert "X" not in {d.titre for d in m} and "Y" not in {d.titre for d in m}


# ================================================ pagination et recherche : sains
PAGES = ["-5", "0", "abc", "1e3", "10" * 40, "9" * 5000, "１", "١", "", "1.5"]


@pytest.mark.parametrize("page", PAGES)
def test_pagination_parametres_hostiles(web_lea, web_admin, page):
    assert web_lea.get("/catalogue", query_string={"page": page}).status_code == 200
    r = web_admin.get("/admin/journal", query_string={"page": page, "action": "<x>"})
    assert r.status_code == 200


def test_recherche_bornee_a_100_caracteres(web_lea, monkeypatch):
    appels = [0]
    vraie = module_session._variantes

    def comptee(mot):
        appels[0] += 1
        return vraie(mot)

    monkeypatch.setattr(module_session, "_variantes", comptee)
    assert web_lea.get("/catalogue", query_string={"q": "zz " * 2000}).status_code == 200
    assert appels[0] <= 50


def test_guichet_saisie_libre_echappee(web_admin):
    r = poster(web_admin, "/admin/emprunt", page="/connexion",
               id_document="<script>alert(1)</script>", numero='"><img src=x>')
    page = web_admin.get(r.headers["Location"]).get_data(as_text=True)
    assert "<script>alert" not in page and "<img src=x" not in page


# ================================================= connexion et sauvegarde : sain
def test_seule_la_connexion_du_personnel_sauvegarde(web_app, monkeypatch):
    """Pas de retour de W1 : un anonyme ou un adherent ne declenche aucune sauvegarde."""
    m = web_app.extensions["mediatheque"]
    sauvegardes = [0]
    vraie = m.sauvegarder

    def comptee(*a, **k):
        sauvegardes[0] += 1
        return vraie(*a, **k)

    monkeypatch.setattr(m, "sauvegarder", comptee)
    for ident in ("admin", "inconnu", "lea"):
        connecter(web_app.test_client(), ident, "MauvaisMdp1")
    connecter(web_app.test_client(), "lea")
    assert sauvegardes[0] == 0
    assert not [j for j in m.journal if j.action == "connexion"]
    connecter(web_app.test_client(), "admin")
    assert sauvegardes[0] == 1
