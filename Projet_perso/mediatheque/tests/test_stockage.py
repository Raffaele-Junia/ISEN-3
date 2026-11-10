import sqlite3

import pytest

from conftest import AUJOURDHUI
from mediatheque.adherents import Adherent
from mediatheque.documents import Livre
from mediatheque.emprunt import Emprunt
from mediatheque.exceptions import (AdherentInconnuError, DocumentInconnuError,
                                    MediathequeError)
from mediatheque.mediatheque import Mediatheque


def test_aller_retour_sqlite(m, tmp_path):
    m.ajouter_adherent(Adherent("A003", "Lefèvre", "Hélène", "standard"))
    m.emprunter("D001", "A003", AUJOURDHUI)
    m.retourner("D001", AUJOURDHUI)
    m.emprunter("D002", "A001", AUJOURDHUI)
    db = tmp_path / "m.db"
    m.sauvegarder(db)

    m2 = Mediatheque.charger(db)
    assert len(m2) == len(m)
    assert m2["D002"].duree_min == 148
    assert m2._adherents["A003"].prenom == "Hélène"
    assert m2.emprunts == m.emprunts
    assert m2.disponible("D001") and not m2.disponible("D002")


def test_conversion_csv_vers_sqlite(dossier_data, tmp_path):
    m = Mediatheque.charger(dossier_data)
    db = tmp_path / "m.db"
    m.sauvegarder(db)
    m2 = Mediatheque.charger(db)
    assert {d.id for d in m2} == {d.id for d in m}
    assert len(m2.emprunts) == len(m.emprunts)


def test_titre_malveillant_stocke_tel_quel(m, tmp_path):
    titre = "x'); DROP TABLE documents; --"
    m.ajouter_document(Livre("D010", titre, 2020, "a"))
    db = tmp_path / "m.db"
    m.sauvegarder(db)
    assert Mediatheque.charger(db)["D010"].titre == titre


def test_sauvegarde_atomique(m, tmp_path):
    db = tmp_path / "m.db"
    m.sauvegarder(db)
    m._adherents["A001"]._type = "vip"  # violera la contrainte CHECK
    with pytest.raises(sqlite3.IntegrityError):
        m.sauvegarder(db)
    assert len(Mediatheque.charger(db)) == len(m)  # base intacte


def test_doublons_refuses(m):
    with pytest.raises(MediathequeError):
        m.ajouter_document(Livre("D001", "autre", 2000, "a"))
    with pytest.raises(MediathequeError):
        m.ajouter_adherent(Adherent("A001", "N", "P", "standard"))


def test_emprunt_orphelin_refuse(m):
    with pytest.raises(DocumentInconnuError):
        m.ajouter_emprunt(Emprunt("D999", "A001", AUJOURDHUI))
    with pytest.raises(AdherentInconnuError):
        m.ajouter_emprunt(Emprunt("D001", "A999", AUJOURDHUI))


def test_csv_avec_emprunt_orphelin(dossier_data):
    with open(dossier_data / "emprunts.csv", "a", encoding="utf-8") as f:
        f.write("D999,A001,2026-11-01,\n")
    with pytest.raises(DocumentInconnuError):
        Mediatheque.charger(dossier_data)
