import shutil
from datetime import date
from pathlib import Path

import pytest

from mediatheque import auth
from mediatheque.adherents import Adherent
from mediatheque.documents import DVD, Livre, Revue
from mediatheque.mediatheque import Mediatheque

DATA = Path(__file__).resolve().parent.parent / "data"
AUJOURDHUI = date(2026, 11, 5)
# Cout scrypt reduit POUR LES TESTS SEULEMENT (la production garde auth._SCRYPT,
# N=2**17, verifie par test_s6_*). Sinon chaque creation de compte prend ~0,5 s.
SCRYPT_TESTS = {"n": 2**10, "r": 8, "p": 1, "dklen": 32}


@pytest.fixture(autouse=True)
def scrypt_rapide(monkeypatch):
    monkeypatch.setattr(auth, "parametres_scrypt", SCRYPT_TESTS)


@pytest.fixture
def m():
    """Mediatheque en memoire, sans emprunt."""
    m = Mediatheque()
    m.ajouter_document(Livre("D001", "Fluent Python", 2022, "Luciano Ramalho"))
    m.ajouter_document(DVD("D002", "Inception", 2010, 148))
    m.ajouter_document(Revue("D003", "Science et Vie", 2024, 1285))
    m.ajouter_document(Livre("D004", "Clean Code", 2008, "Robert Martin"))
    m.ajouter_adherent(Adherent("A001", "Martin", "Lea", "standard"))
    m.ajouter_adherent(Adherent("A002", "Durand", "Hugo", "premium"))
    return m


@pytest.fixture
def dossier_data(tmp_path):
    """Copie de data/ dans un dossier temporaire (ne jamais toucher data/)."""
    dossier = tmp_path / "data"
    shutil.copytree(DATA, dossier)
    return dossier
