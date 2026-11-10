"""Outillage des tests de securite du site web (audit P2).

Pas de conftest.py dans tests/security : il masquerait `tests/conftest.py`
pour les modules qui font `from conftest import ...`. Les fixtures `web_*`
sont donc definies ici et importees par les fichiers de tests. Toujours sur
une copie de data/ dans tmp_path : jamais sur data/.
"""
import re
import threading

import pytest

from mediatheque.auth import ADHERENT, RESPONSABLE
from mediatheque.mediatheque import Mediatheque
from mediatheque.web import create_app

MDP = "Secret123"


def jeton_csrf(client, url="/connexion"):
    page = client.get(url).get_data(as_text=True)
    return re.search(r'name="csrf" value="([^"]+)"', page).group(1)


def connecter(client, ident, mdp=MDP):
    return client.post("/connexion", data={"identifiant": ident, "mot_de_passe": mdp,
                                           "csrf": jeton_csrf(client)})


def poster(client, url, page="/catalogue", headers=None, **data):
    return client.post(url, data={**data, "csrf": jeton_csrf(client, page)},
                       headers=headers or {})


def client_connecte(app, ident):
    c = app.test_client()
    assert connecter(c, ident).status_code == 302
    return c


def variable_interne(app, nom):
    """Variable locale de create_app (verrou, sessions_actives...) capturee
    par une vue : on la retrouve dans la fermeture des fonctions de vue."""
    for vue in app.view_functions.values():
        while vue is not None:
            code = getattr(vue, "__code__", None)
            if code is not None and nom in code.co_freevars:
                return vue.__closure__[code.co_freevars.index(nom)].cell_contents
            vue = getattr(vue, "__wrapped__", None)
    raise LookupError(nom)


def verrou_tenu(verrou):
    """Vrai si le verrou est tenu (par n'importe quel thread), teste depuis
    un autre thread (un RLock est reentrant pour son proprietaire)."""
    libre = []

    def essayer():
        ok = verrou.acquire(blocking=False)
        if ok:
            verrou.release()
        libre.append(ok)

    t = threading.Thread(target=essayer)
    t.start()
    t.join()
    return not libre[0]



def base_de_test(dossier_data, tmp_path):
    m = Mediatheque.charger(dossier_data)
    m.creer_compte("admin", MDP, RESPONSABLE)
    m.creer_compte("lea", MDP, ADHERENT, "A001")
    m.creer_compte("ines", MDP, ADHERENT, "A003")
    chemin = tmp_path / "m.db"
    m.sauvegarder(chemin)
    return chemin


@pytest.fixture
def web_db(dossier_data, tmp_path):
    return base_de_test(dossier_data, tmp_path)


@pytest.fixture
def web_app(web_db):
    return create_app(web_db, secret_key="test", testing=True)


@pytest.fixture
def web_app_prod(web_db):
    """TESTING=False : les exceptions donnent une vraie reponse 500."""
    return create_app(web_db, secret_key="test", testing=False)


@pytest.fixture
def web_lea(web_app):
    return client_connecte(web_app, "lea")


@pytest.fixture
def web_ines(web_app):
    return client_connecte(web_app, "ines")


@pytest.fixture
def web_admin(web_app):
    return client_connecte(web_app, "admin")
