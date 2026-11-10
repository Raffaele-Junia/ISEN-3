"""Persistance SQLite de la mediatheque.

Toutes les requetes sont parametrees (`?`) : aucune donnee n'est jamais
concatenee dans le SQL. La sauvegarde se fait dans UNE transaction : en cas
d'erreur, la base reste dans son etat precedent (pas de corruption partielle).
"""
import sqlite3
from contextlib import closing
from datetime import date

from .adherents import Adherent
from .documents import Document
from .emprunt import Emprunt

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id      TEXT PRIMARY KEY,
    type    TEXT NOT NULL,
    titre   TEXT NOT NULL,
    annee   INTEGER NOT NULL,
    extra   TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS adherents (
    numero  TEXT PRIMARY KEY,
    nom     TEXT NOT NULL,
    prenom  TEXT NOT NULL,
    type    TEXT NOT NULL CHECK (type IN ('standard', 'premium'))
);
CREATE TABLE IF NOT EXISTS emprunts (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    id_document      TEXT NOT NULL REFERENCES documents(id),
    numero_adherent  TEXT NOT NULL REFERENCES adherents(numero),
    date_emprunt     TEXT NOT NULL,
    date_retour      TEXT
);
"""


def connecter(chemin):
    con = sqlite3.connect(chemin)
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript(SCHEMA)
    return con


def charger(chemin):
    """Renvoie (documents, adherents, emprunts) lus depuis la base."""
    with closing(connecter(chemin)) as con:
        con.row_factory = sqlite3.Row
        documents = [Document.from_csv_row(dict(r)) for r in
                     con.execute("SELECT id, type, titre, annee, extra FROM documents")]
        adherents = [Adherent.from_csv_row(dict(r)) for r in
                     con.execute("SELECT numero, nom, prenom, type FROM adherents")]
        emprunts = [Emprunt.from_csv_row({**dict(r), "date_retour": r["date_retour"] or ""})
                    for r in con.execute(
                        "SELECT id_document, numero_adherent, date_emprunt, date_retour "
                        "FROM emprunts ORDER BY id")]
    return documents, adherents, emprunts


def sauvegarder(chemin, documents, adherents, emprunts):
    with closing(connecter(chemin)) as con:
        with con:  # transaction : commit si tout passe, rollback sinon
            con.execute("DELETE FROM emprunts")
            con.execute("DELETE FROM documents")
            con.execute("DELETE FROM adherents")
            con.executemany(
                "INSERT INTO documents (id, type, titre, annee, extra) VALUES (?, ?, ?, ?, ?)",
                [(d.id, d.CLE, d.titre, d.annee, str(d._extra)) for d in documents])
            con.executemany(
                "INSERT INTO adherents (numero, nom, prenom, type) VALUES (?, ?, ?, ?)",
                [(a.numero, a.nom, a.prenom, a.type) for a in adherents])
            con.executemany(
                "INSERT INTO emprunts (id_document, numero_adherent, date_emprunt, date_retour) "
                "VALUES (?, ?, ?, ?)",
                [(e.id_document, e.numero_adherent, e.date_emprunt.isoformat(),
                  _iso(e.date_retour)) for e in emprunts])


def _iso(d: date | None):
    return d.isoformat() if d else None
