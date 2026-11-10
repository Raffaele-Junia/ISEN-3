"""Audit securite P1 : authentification, enumeration, blocage."""
import inspect

import pytest

from mediatheque import auth
from mediatheque.auth import ADHERENT, MAX_ECHECS, RESPONSABLE, GestionComptes
from mediatheque.exceptions import AuthentificationError, CompteBloqueError
from mediatheque.session import ouvrir_session

MDP = "Secret123"


class Horloge:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


@pytest.fixture
def horloge():
    return Horloge()


@pytest.fixture
def comptes(horloge):
    g = GestionComptes(horloge=horloge)
    g.creer("admin", MDP, RESPONSABLE)
    g.creer("lea", MDP, ADHERENT, "A001")
    return g


# ------------------------------------------------- protections verifiees (OK)
def test_hachage_scrypt_sel_aleatoire_et_comparaison_temps_constant():
    source = inspect.getsource(auth)
    assert "hashlib.scrypt" in source
    assert "hmac.compare_digest" in source
    assert "secrets.token_bytes(16)" in source


def test_identifiant_inconnu_hache_quand_meme(comptes, monkeypatch):
    """Pas d'enumeration par le temps : le hachage a lieu dans les deux cas."""
    appels = []
    original = auth.hacher
    monkeypatch.setattr(auth, "hacher", lambda m, s: appels.append(1) or original(m, s))
    for identifiant in ("lea", "personne"):
        with pytest.raises(AuthentificationError):
            comptes.authentifier(identifiant, "Mauvais123")
    assert len(appels) == 2


def test_enumeration_par_message_et_par_blocage_impossible(comptes):
    messages = {}
    for identifiant in ("lea", "personne"):
        for _ in range(MAX_ECHECS):
            with pytest.raises(AuthentificationError) as e:
                comptes.authentifier(identifiant, "Mauvais123")
            messages.setdefault(identifiant, set()).add(str(e.value))
        # identifiant existant ou non : meme blocage, meme message
        with pytest.raises(CompteBloqueError):
            comptes.authentifier(identifiant, "Mauvais123")
    assert messages["lea"] == messages["personne"]


@pytest.mark.parametrize("variante", ["LEA", " lea", "lea ", "Lea", "\tlea\n"])
def test_blocage_non_contournable_par_casse_ou_espaces(comptes, variante):
    for _ in range(MAX_ECHECS):
        with pytest.raises(AuthentificationError):
            comptes.authentifier(variante, "Mauvais123")
    with pytest.raises(CompteBloqueError):
        comptes.authentifier("lea", MDP)


def test_blocage_s_applique_aussi_au_bon_mot_de_passe(comptes, horloge):
    for _ in range(MAX_ECHECS):
        with pytest.raises(AuthentificationError):
            comptes.authentifier("lea", "Mauvais123")
    with pytest.raises(CompteBloqueError):
        comptes.authentifier("lea", MDP)
    horloge.t += auth.DUREE_BLOCAGE_S + 1
    assert comptes.authentifier("lea", MDP).identifiant == "lea"


def test_changer_mot_de_passe_soumis_au_blocage(comptes):
    """Le changement de mot de passe ne sert pas de canal de force brute."""
    for _ in range(MAX_ECHECS):
        with pytest.raises(AuthentificationError):
            comptes.changer_mot_de_passe("lea", "Mauvais123", "Nouveau123")
    with pytest.raises(CompteBloqueError):
        comptes.changer_mot_de_passe("lea", MDP, "Nouveau123")


def test_s5_un_second_responsable_peut_debloquer(m):
    """S5 (risque residuel, pas de xfail) : n'importe qui peut bloquer le
    responsable ; seul remede actuel : un 2e responsable reinitialise le mdp."""
    m.creer_compte("admin", MDP, RESPONSABLE)
    m.creer_compte("admin2", MDP, RESPONSABLE)
    for _ in range(MAX_ECHECS):
        with pytest.raises(AuthentificationError):
            ouvrir_session(m, "admin", "Mauvais123")
    with pytest.raises(CompteBloqueError):
        ouvrir_session(m, "admin", MDP)
    ouvrir_session(m, "admin2", MDP).reinitialiser_mot_de_passe("admin", "Neuf12345")
    assert ouvrir_session(m, "admin", "Neuf12345").est_responsable


# --------------------------------------------- S6 : cout scrypt insuffisant
@pytest.mark.xfail(strict=True, reason="faille S6 : scrypt N=2**14, sous le minimum "
                   "OWASP (N=2**17, r=8, p=1)")
def test_s6_cout_scrypt_conforme_owasp():
    assert auth._SCRYPT["n"] >= 2**17
    assert auth._SCRYPT["r"] >= 8
