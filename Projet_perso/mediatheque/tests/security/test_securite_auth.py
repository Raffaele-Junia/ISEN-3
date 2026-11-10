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
    """S5 : le delai progressif est plafonne (DELAI_MAX_S) ; un 2e responsable
    peut en plus debloquer immediatement en reinitialisant le mot de passe."""
    m.creer_compte("admin", MDP, RESPONSABLE)
    m.creer_compte("admin2", MDP, RESPONSABLE)
    for _ in range(MAX_ECHECS):
        with pytest.raises(AuthentificationError):
            ouvrir_session(m, "admin", "Mauvais123")
    with pytest.raises(CompteBloqueError):
        ouvrir_session(m, "admin", MDP)
    ouvrir_session(m, "admin2", MDP).reinitialiser_mot_de_passe("admin", "Neuf12345")
    assert ouvrir_session(m, "admin", "Neuf12345").est_responsable


# ------------------------------------------ S5 : delai progressif (backoff)
def _echouer(comptes, n, identifiant="lea"):
    for _ in range(n):
        with pytest.raises(AuthentificationError):
            comptes.authentifier(identifiant, "Mauvais123")


def test_s5_delai_progressif_puis_plafonne(comptes, horloge):
    _echouer(comptes, MAX_ECHECS)
    attentes = []
    for _ in range(12):
        with pytest.raises(CompteBloqueError) as e:
            comptes.authentifier("lea", MDP)
        attentes.append(e.value.secondes_restantes)
        horloge.t += e.value.secondes_restantes
        _echouer(comptes, 1)
    assert attentes[:4] == [1, 2, 4, 8]
    assert max(attentes) == auth.DELAI_MAX_S and attentes[-1] == auth.DELAI_MAX_S


def test_s5_delai_non_contournable(comptes, horloge):
    """Pendant le delai, tout essai est refuse (meme le bon mot de passe, meme
    avec une autre casse) ; a l'expiration le compteur n'est pas remis a zero."""
    _echouer(comptes, MAX_ECHECS)
    for identifiant, mdp in (("lea", MDP), ("lea", "Mauvais123"), ("LEA ", MDP),
                             (" Lea", "Mauvais123")):
        with pytest.raises(CompteBloqueError):
            comptes.authentifier(identifiant, mdp)
    horloge.t += 1
    _echouer(comptes, 1)
    with pytest.raises(CompteBloqueError) as e:
        comptes.authentifier("lea", MDP)
    assert e.value.secondes_restantes == 2


def test_s5_le_responsable_n_est_bloque_que_brievement(comptes, horloge):
    """Un attaquant qui insiste en continu : le responsable attend au plus
    DELAI_MAX_S apres le dernier essai de l'attaquant."""
    for _ in range(50):
        try:
            comptes.authentifier("admin", "Mauvais123")
        except CompteBloqueError as e:
            horloge.t += e.secondes_restantes
        except AuthentificationError:
            pass
    horloge.t += auth.DELAI_MAX_S
    assert comptes.authentifier("admin", MDP).role == RESPONSABLE


def test_s5_compteurs_purges(comptes, horloge, monkeypatch):
    monkeypatch.setattr(auth, "_MAX_SUIVIS", 10)
    for i in range(10):
        _echouer(comptes, 1, f"inconnu{i}")
    horloge.t += auth.OUBLI_S + 1
    _echouer(comptes, 1, "encore")
    assert list(comptes._echecs) == ["encore"]


# --------------------------------------------- S6 : cout scrypt insuffisant
@pytest.mark.xfail(strict=True, reason="faille S6 : scrypt N=2**14, sous le minimum "
                   "OWASP (N=2**17, r=8, p=1)")
def test_s6_cout_scrypt_conforme_owasp():
    assert auth._SCRYPT["n"] >= 2**17
    assert auth._SCRYPT["r"] >= 8
