"""Persistance SQLite de la mediatheque.

Toutes les requetes sont parametrees (`?`) : aucune donnee n'est jamais
concatenee dans le SQL. La sauvegarde se fait dans UNE transaction : en cas
d'erreur, la base reste dans son etat precedent (pas de corruption partielle).

Le journal est en AJOUT SEUL (Z3) : la sauvegarde n'y insere que les nouvelles
entrees, et deux declencheurs refusent tout UPDATE ou DELETE sur la table. Seule
`purger_journal` (duree de conservation, lancee a la main par un responsable)
suspend celui des suppressions, le temps de sa transaction.
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

# Declencheurs d'ajout seul du journal (Z3). `connecter` les cree aussi dans
# les bases existantes ; `purger_journal` les recree apres sa suppression.
DECLENCHEUR_MODIFICATION = (
    "CREATE TRIGGER IF NOT EXISTS journal_sans_modification BEFORE UPDATE ON journal "
    "BEGIN SELECT RAISE(ABORT, 'journal en ajout seul : modification interdite'); END")
DECLENCHEUR_SUPPRESSION = (
    "CREATE TRIGGER IF NOT EXISTS journal_sans_suppression BEFORE DELETE ON journal "
    "BEGIN SELECT RAISE(ABORT, 'journal en ajout seul : suppression interdite'); END")
SCHEMA += f"{DECLENCHEUR_MODIFICATION};\n{DECLENCHEUR_SUPPRESSION};\n"


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


def _etat_journal(con):
    """(plus petit id, plus grand id) du journal. Il change a chaque ajout ou
    purge (les modifications sont interdites par les declencheurs) et se lit
    en O(log n) sur la cle primaire."""
    return tuple(con.execute("SELECT MIN(id), MAX(id) FROM journal").fetchone())


def _lire_journal(con):
    return [EntreeJournal(datetime.fromisoformat(r["horodatage"]), r["acteur"],
                          r["action"], r["cible"], r["detail"])
            for r in con.execute("SELECT horodatage, acteur, action, cible, detail "
                                 "FROM journal ORDER BY id")]


def charger(chemin, journal_connu=None):
    """Renvoie un dict {documents, adherents, emprunts, reservations, comptes,
    journal, etat_journal}. Si `journal_connu` (un `etat_journal` lu plus tot)
    est encore l'etat de la base, le journal n'est pas relu : `journal` vaut None."""
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
        etat = _etat_journal(con)
        journal = (None if journal_connu is not None and etat == tuple(journal_connu)
                   else _lire_journal(con))
    return {"documents": documents, "adherents": adherents, "emprunts": emprunts,
            "reservations": reservations, "comptes": comptes, "journal": journal,
            "etat_journal": etat}


def sauvegarder(chemin, documents, adherents, emprunts, reservations=(), comptes=(),
                journal=(), journal_deja_ecrit=None):
    """Reecrit les donnees et AJOUTE au journal les seules entrees `journal[n:]`,
    ou n vaut `journal_deja_ecrit` (entrees deja en base) ou, a defaut, le
    nombre de lignes du journal de la base. Renvoie le nouvel etat du journal."""
    journal = list(journal)
    with closing(connecter(chemin)) as con:
        with con:  # transaction : commit si tout passe, rollback sinon
            if journal_deja_ecrit is None:
                journal_deja_ecrit = con.execute("SELECT COUNT(*) FROM journal").fetchone()[0]
            if journal_deja_ecrit > len(journal):
                raise ValueError("le journal de la base contient des entrees absentes de la "
                                 "memoire : rechargez avant de sauvegarder")
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
                  j.detail) for j in journal[journal_deja_ecrit:]])
            return _etat_journal(con)


def purger_journal(chemin, avant, entree_purge):
    """Supprime les entrees du journal anterieures a `avant` (duree de
    conservation) puis ajoute `entree_purge` (qui a purge, combien), dont le
    detail est forme par `entree_purge(n)`. Le declencheur de suppression est
    suspendu le temps de LA transaction puis recree : en cas d'erreur, rien
    n'est supprime et il reste en place. Renvoie le nombre d'entrees supprimees."""
    limite = avant.isoformat(timespec="seconds")
    with closing(connecter(chemin)) as con:
        con.isolation_level = None  # transaction explicite : le DDL en fait partie
        con.execute("BEGIN IMMEDIATE")
        try:
            n = con.execute("SELECT COUNT(*) FROM journal WHERE horodatage < ?",
                            (limite,)).fetchone()[0]
            con.execute("DROP TRIGGER journal_sans_suppression")
            con.execute("DELETE FROM journal WHERE horodatage < ?", (limite,))
            con.execute(DECLENCHEUR_SUPPRESSION)
            j = entree_purge(n)
            con.execute("INSERT INTO journal (horodatage, acteur, action, cible, detail) "
                        "VALUES (?, ?, ?, ?, ?)",
                        (j.horodatage.isoformat(timespec="seconds"), j.acteur, j.action,
                         j.cible, j.detail))
            con.execute("COMMIT")
        except BaseException:
            con.execute("ROLLBACK")
            raise
    return n


def _iso(d: date | None):
    return d.isoformat() if d else None
