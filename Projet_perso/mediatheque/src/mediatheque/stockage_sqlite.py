"""Persistance SQLite de la mediatheque.

Toutes les requetes sont parametrees (`?`) : aucune donnee n'est jamais
concatenee dans le SQL. La sauvegarde se fait dans UNE transaction : en cas
d'erreur, la base reste dans son etat precedent (pas de corruption partielle).
"""
import sqlite3
from contextlib import closing
from datetime import date, datetime

from .adherents import Adherent
from .auth import Compte
from .documents import CHAMPS_FICHE, Document
from .emprunt import Emprunt
from .journal import EntreeJournal
from .reservation import Reservation

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id      TEXT PRIMARY KEY,
    type    TEXT NOT NULL,
    titre   TEXT NOT NULL,
    annee   INTEGER NOT NULL,
    extra   TEXT NOT NULL,
    genre   TEXT NOT NULL DEFAULT '',
    themes  TEXT NOT NULL DEFAULT '',
    resume  TEXT NOT NULL DEFAULT '',
    editeur TEXT NOT NULL DEFAULT '',
    pages   INTEGER NOT NULL DEFAULT 0,
    isbn    TEXT NOT NULL DEFAULT '',
    public  TEXT NOT NULL DEFAULT '',
    realisateur TEXT NOT NULL DEFAULT ''
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
CREATE TABLE IF NOT EXISTS reservations (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    id_document      TEXT NOT NULL REFERENCES documents(id),
    numero_adherent  TEXT NOT NULL REFERENCES adherents(numero),
    date_reservation TEXT NOT NULL,
    statut           TEXT NOT NULL CHECK (statut IN
                     ('en_attente', 'disponible', 'honoree', 'annulee', 'expiree')),
    date_disponible  TEXT
);
CREATE TABLE IF NOT EXISTS journal (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    horodatage  TEXT NOT NULL,
    acteur      TEXT NOT NULL,
    action      TEXT NOT NULL,
    cible       TEXT NOT NULL DEFAULT '',
    detail      TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS comptes (
    identifiant      TEXT PRIMARY KEY,
    hash_mdp         BLOB NOT NULL,
    sel              BLOB NOT NULL,
    role             TEXT NOT NULL CHECK (role IN ('adherent', 'responsable')),
    numero_adherent  TEXT REFERENCES adherents(numero)
);
"""


# Colonnes ajoutees apres la premiere version : migrees automatiquement.
# Les noms viennent de cette constante (jamais d'une saisie) : pas d'injection.
_COLONNES_FICHE = {"genre": "TEXT NOT NULL DEFAULT ''", "themes": "TEXT NOT NULL DEFAULT ''",
                   "resume": "TEXT NOT NULL DEFAULT ''", "editeur": "TEXT NOT NULL DEFAULT ''",
                   "pages": "INTEGER NOT NULL DEFAULT 0", "isbn": "TEXT NOT NULL DEFAULT ''",
                   "public": "TEXT NOT NULL DEFAULT ''", "realisateur": "TEXT NOT NULL DEFAULT ''"}


def connecter(chemin):
    con = sqlite3.connect(chemin)
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript(SCHEMA)
    _migrer(con)
    return con


def _migrer(con):
    existantes = {ligne[1] for ligne in con.execute("PRAGMA table_info(documents)")}
    for nom, definition in _COLONNES_FICHE.items():
        if nom not in existantes:
            con.execute(f"ALTER TABLE documents ADD COLUMN {nom} {definition}")
    con.commit()


def charger(chemin):
    """Renvoie un dict {documents, adherents, emprunts, reservations, comptes}."""
    with closing(connecter(chemin)) as con:
        con.row_factory = sqlite3.Row
        documents = [Document.from_csv_row(dict(r)) for r in
                     con.execute("SELECT id, type, titre, annee, extra, " + ", ".join(CHAMPS_FICHE)
                                 + " FROM documents")]
        adherents = [Adherent.from_csv_row(dict(r)) for r in
                     con.execute("SELECT numero, nom, prenom, type FROM adherents")]
        emprunts = [Emprunt.from_csv_row({**dict(r), "date_retour": r["date_retour"] or ""})
                    for r in con.execute(
                        "SELECT id_document, numero_adherent, date_emprunt, date_retour "
                        "FROM emprunts ORDER BY id")]
        reservations = [Reservation.from_csv_row(
                            {**dict(r), "date_disponible": r["date_disponible"] or ""})
                        for r in con.execute(
                            "SELECT id_document, numero_adherent, date_reservation, statut, "
                            "date_disponible FROM reservations ORDER BY id")]
        comptes = [Compte(r["identifiant"], bytes(r["hash_mdp"]), bytes(r["sel"]),
                          r["role"], r["numero_adherent"])
                   for r in con.execute("SELECT identifiant, hash_mdp, sel, role, "
                                        "numero_adherent FROM comptes")]
        journal = [EntreeJournal(datetime.fromisoformat(r["horodatage"]), r["acteur"],
                                 r["action"], r["cible"], r["detail"])
                   for r in con.execute("SELECT horodatage, acteur, action, cible, detail "
                                        "FROM journal ORDER BY id")]
    return {"documents": documents, "adherents": adherents, "emprunts": emprunts,
            "reservations": reservations, "comptes": comptes, "journal": journal}


def sauvegarder(chemin, documents, adherents, emprunts, reservations=(), comptes=(),
                journal=()):
    with closing(connecter(chemin)) as con:
        with con:  # transaction : commit si tout passe, rollback sinon
            con.execute("DELETE FROM journal")
            con.execute("DELETE FROM comptes")
            con.execute("DELETE FROM reservations")
            con.execute("DELETE FROM emprunts")
            con.execute("DELETE FROM documents")
            con.execute("DELETE FROM adherents")
            con.executemany(
                "INSERT INTO documents (id, type, titre, annee, extra, " + ", ".join(CHAMPS_FICHE)
                + ") VALUES (?, ?, ?, ?, ?" + ", ?" * len(CHAMPS_FICHE) + ")",
                [(d.id, d.CLE, d.titre, d.annee, str(d._extra),
                  *(d.fiche[c] for c in CHAMPS_FICHE)) for d in documents])
            con.executemany(
                "INSERT INTO adherents (numero, nom, prenom, type) VALUES (?, ?, ?, ?)",
                [(a.numero, a.nom, a.prenom, a.type) for a in adherents])
            con.executemany(
                "INSERT INTO emprunts (id_document, numero_adherent, date_emprunt, date_retour) "
                "VALUES (?, ?, ?, ?)",
                [(e.id_document, e.numero_adherent, e.date_emprunt.isoformat(),
                  _iso(e.date_retour)) for e in emprunts])
            con.executemany(
                "INSERT INTO reservations (id_document, numero_adherent, date_reservation, "
                "statut, date_disponible) VALUES (?, ?, ?, ?, ?)",
                [(r.id_document, r.numero_adherent, r.date_reservation.isoformat(),
                  r.statut, _iso(r.date_disponible)) for r in reservations])
            con.executemany(
                "INSERT INTO comptes (identifiant, hash_mdp, sel, role, numero_adherent) "
                "VALUES (?, ?, ?, ?, ?)",
                [(c.identifiant, c.hash_mdp, c.sel, c.role, c.numero_adherent)
                 for c in comptes])
            con.executemany(
                "INSERT INTO journal (horodatage, acteur, action, cible, detail) "
                "VALUES (?, ?, ?, ?, ?)",
                [(j.horodatage.isoformat(timespec="seconds"), j.acteur, j.action, j.cible,
                  j.detail) for j in journal])


def _iso(d: date | None):
    return d.isoformat() if d else None
