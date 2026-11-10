import sqlite3

import pytest

from mediatheque.documents import Document, Livre
from mediatheque.mediatheque import Mediatheque

FICHE = {"genre": "Science-fiction", "themes": ("dystopie", "pouvoir", "surveillance"),
         "resume": "Winston Smith vit sous le regard de Big Brother.",
         "editeur": "Gallimard", "pages": 400, "isbn": "978-2-07-036822-8", "public": "adulte"}


def test_completer_fiche_normalise():
    d = Livre("D050", "1984", 1949, "George Orwell").completer_fiche(**FICHE)
    assert d.themes == ("dystopie", "pouvoir", "surveillance")
    assert d.isbn == "9782070368228"
    assert d.fiche["themes"] == "dystopie|pouvoir|surveillance"
    assert d.createur == "George Orwell"


@pytest.mark.parametrize("champ,valeur", [
    ("pages", -3), ("isbn", "12AB"), ("public", "vieux"), ("resume", "x" * 1300), ("inconnu", 1)])
def test_completer_fiche_refuse_les_valeurs_invalides(champ, valeur):
    with pytest.raises(ValueError):
        Livre("D050", "T", 2000, "A").completer_fiche(**{champ: valeur})


def test_ancien_csv_sans_fiche():
    d = Document.from_csv_row({"id": "D1", "type": "dvd", "titre": "X", "annee": "2001", "extra": "90"})
    assert d.genre == "" and d.themes == () and d.pages == 0


@pytest.mark.parametrize("nom", ["m.db", "dossier"])
def test_fiche_persistee(m, tmp_path, nom):
    m.ajouter_document(Livre("D050", "1984", 1949, "George Orwell").completer_fiche(**FICHE))
    m.sauvegarder(tmp_path / nom)
    d = Mediatheque.charger(tmp_path / nom)["D050"]
    assert (d.genre, d.themes, d.pages, d.isbn, d.public) == (
        "Science-fiction", ("dystopie", "pouvoir", "surveillance"), 400, "9782070368228", "adulte")


def test_migration_d_une_ancienne_base(m, tmp_path):
    db = tmp_path / "ancienne.db"
    with sqlite3.connect(db) as con:  # schema de la premiere version, sans colonnes de fiche
        con.executescript("""
            CREATE TABLE documents (id TEXT PRIMARY KEY, type TEXT NOT NULL, titre TEXT NOT NULL,
                                    annee INTEGER NOT NULL, extra TEXT NOT NULL);
            INSERT INTO documents VALUES ('D001', 'livre', 'Candide', 1759, 'Voltaire');""")
    con.close()
    m2 = Mediatheque.charger(db)
    assert m2["D001"].titre == "Candide" and m2["D001"].genre == ""
    m2["D001"].completer_fiche(genre="Roman classique")
    m2.sauvegarder()
    assert Mediatheque.charger(db)["D001"].genre == "Roman classique"
