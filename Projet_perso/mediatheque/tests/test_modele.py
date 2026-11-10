from datetime import date

import pytest

from mediatheque.adherents import Adherent
from mediatheque.documents import DVD, Document, Livre, Revue
from mediatheque.emprunt import Emprunt


def test_detail_dvd_affiche_la_duree():
    assert str(DVD("D002", "Inception", 2010, 148)) == "[DVD] Inception (2010) - 148 min"


def test_durees_de_pret():
    assert Livre("D1", "t", 2000, "a").duree_pret_jour == 21
    assert DVD("D2", "t", 2000, 90).duree_pret_jour == 7
    assert Revue("D3", "t", 2000, 1).duree_pret_jour == 7


def test_from_csv_row_choisit_la_bonne_classe():
    doc = Document.from_csv_row(
        {"id": "D9", "type": "dvd", "titre": "X", "annee": "2001", "extra": "95"})
    assert isinstance(doc, DVD) and doc.duree_min == 95


def test_from_csv_row_type_inconnu():
    with pytest.raises(ValueError):
        Document.from_csv_row(
            {"id": "D9", "type": "vinyle", "titre": "X", "annee": "2001", "extra": ""})


def test_egalite_et_tri_des_documents():
    a = Livre("D1", "B", 2000, "x")
    assert a == Livre("D1", "autre", 1999, "y")
    assert sorted([a, Livre("D2", "A", 2000, "x")])[0].titre == "A"


@pytest.mark.parametrize("numero", ["A01", "B001", "A0001", "a001", ""])
def test_numero_adherent_invalide(numero):
    with pytest.raises(ValueError):
        Adherent(numero, "N", "P", "standard")


def test_type_adherent_invalide():
    with pytest.raises(ValueError):
        Adherent("A001", "N", "P", "vip")


def test_quota_selon_type():
    assert Adherent("A001", "N", "P", "standard").quota == 3
    assert Adherent("A002", "N", "P", "premium").quota == 6


def test_jours_retard():
    e = Emprunt("D1", "A001", date(2026, 10, 1))
    assert e.date_limite(21) == date(2026, 10, 22)
    assert e.jours_retard(21, date(2026, 10, 22)) == 0
    assert e.jours_retard(21, date(2026, 11, 5)) == 14
    e.date_retour = date(2026, 10, 25)
    assert e.jours_retard(21, date(2026, 12, 31)) == 3
