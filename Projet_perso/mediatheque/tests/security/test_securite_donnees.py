"""Audit securite P1 : base SQLite falsifiee, integrite, injection SQL, ecrasement."""
import sqlite3
from contextlib import closing
from datetime import date

import pytest

from mediatheque import init_db
from mediatheque.adherents import Adherent
from mediatheque.auth import ADHERENT, RESPONSABLE
from mediatheque.documents import Livre
from mediatheque.emprunt import Emprunt
from mediatheque.exceptions import MediathequeError
from mediatheque.mediatheque import Mediatheque

MDP = "Secret123"
ERREURS_CHARGEMENT = (MediathequeError, ValueError, TypeError, sqlite3.Error)


@pytest.fixture
def db(m, tmp_path):
    """Base saine : 4 documents, A001/A002, un compte responsable et un adherent."""
    m.creer_compte("admin", MDP, RESPONSABLE)
    m.creer_compte("lea", MDP, ADHERENT, "A001")
    chemin = tmp_path / "m.db"
    m.sauvegarder(chemin)
    return chemin


def executer(chemin, sql, params=()):
    with closing(sqlite3.connect(chemin)) as con, con:
        con.execute(sql, params)


def copier_compte(chemin, identifiant, role, numero):
    executer(chemin, "INSERT INTO comptes SELECT ?, hash_mdp, sel, ?, ? FROM comptes "
             "WHERE identifiant = 'lea'", (identifiant, role, numero))


# ------------------------------------------------- protections verifiees (OK)
def test_role_falsifie_refuse(tmp_path):
    """Base fabriquee sans les CHECK du schema : le role est revalide en Python."""
    chemin = tmp_path / "pirate.db"
    with closing(sqlite3.connect(chemin)) as con:
        con.execute("CREATE TABLE comptes (identifiant, hash_mdp, sel, role, numero_adherent)")
        con.execute("INSERT INTO comptes VALUES ('x', x'00', x'00', 'admin', NULL)")
        con.commit()
    with pytest.raises(ValueError, match="role invalide"):
        Mediatheque.charger(chemin)


def test_compte_adherent_sans_numero_refuse(db):
    copier_compte(db, "orphelin", ADHERENT, None)
    with pytest.raises(ValueError):
        Mediatheque.charger(db)


def test_compte_lie_a_un_adherent_inexistant_refuse(db):
    with closing(sqlite3.connect(db)) as con:  # foreign_keys OFF par defaut
        con.execute("INSERT INTO comptes SELECT 'fantome', hash_mdp, sel, 'adherent', 'A999' "
                    "FROM comptes WHERE identifiant = 'lea'")
        con.commit()
    with pytest.raises(MediathequeError):
        Mediatheque.charger(db)


def test_deux_comptes_pour_le_meme_adherent_refuses(db):
    """Sinon un second identifiant pourrait agir au nom de A001."""
    copier_compte(db, "lea2", ADHERENT, "A001")
    with pytest.raises(MediathequeError, match="deja un compte"):
        Mediatheque.charger(db)


def test_injection_sql_inoffensive(m, tmp_path):
    charge = "x'); DROP TABLE documents; --"
    m.ajouter_document(Livre("D'9", charge, 2020, charge))
    m.ajouter_adherent(Adherent("A009", charge, "Robert'); --", "standard"))
    chemin = tmp_path / "m.db"
    m.sauvegarder(chemin)
    m2 = Mediatheque.charger(chemin)
    assert m2["D'9"].titre == charge
    assert m2.adherent("A009").prenom == "Robert'); --"
    assert len(m2) == len(m)


def test_sauvegarde_echouee_laisse_la_base_intacte(m, db):
    m2 = Mediatheque.charger(db)
    m2._emprunts.append(Emprunt("D404", "A001", date(2026, 1, 1)))  # orphelin -> FK
    with pytest.raises(sqlite3.IntegrityError):
        m2.sauvegarder()
    m3 = Mediatheque.charger(db)
    assert len(m3) == len(m) and len(m3.comptes) == 2


def test_init_db_n_ecrase_pas_un_fichier_existant(dossier_data, tmp_path):
    cible = tmp_path / "precieux.db"
    cible.write_bytes(b"donnees a ne pas perdre")
    with pytest.raises(MediathequeError, match="existe deja"):
        init_db.initialiser(dossier_data, cible, "admin", MDP)
    assert cible.read_bytes() == b"donnees a ne pas perdre"


# ------------------------------- S3 : integrite metier non verifiee au chargement
@pytest.mark.xfail(strict=True, reason="faille S3 : deux emprunts en cours du meme "
                   "document acceptes au chargement")
def test_s3_double_emprunt_en_cours_refuse(db):
    for numero in ("A001", "A002"):
        executer(db, "INSERT INTO emprunts (id_document, numero_adherent, date_emprunt) "
                 "VALUES ('D001', ?, '2026-10-01')", (numero,))
    with pytest.raises(ERREURS_CHARGEMENT):
        Mediatheque.charger(db)


@pytest.mark.xfail(strict=True, reason="faille S3 : quota depasse accepte au chargement")
def test_s3_quota_depasse_refuse(db):
    for id_document in ("D001", "D002", "D003", "D004"):  # A001 standard : quota 3
        executer(db, "INSERT INTO emprunts (id_document, numero_adherent, date_emprunt) "
                 "VALUES (?, 'A001', '2026-10-01')", (id_document,))
    with pytest.raises(ERREURS_CHARGEMENT):
        Mediatheque.charger(db)


@pytest.mark.xfail(strict=True, reason="faille S3 : reservation 'disponible' sans "
                   "date_disponible acceptee, puis TypeError a chaque operation (deni de service)")
def test_s3_reservation_disponible_sans_date(db):
    executer(db, "INSERT INTO reservations (id_document, numero_adherent, date_reservation, "
             "statut, date_disponible) VALUES ('D001', 'A001', '2026-10-01', 'disponible', NULL)")
    try:
        m = Mediatheque.charger(db)
    except (MediathequeError, ValueError):
        return  # refus propre au chargement : comportement attendu
    m.emprunter("D004", "A002", date(2026, 11, 5))  # leve TypeError aujourd'hui


@pytest.mark.xfail(strict=True, reason="faille S3 : date de retour anterieure a "
                   "l'emprunt acceptee au chargement")
def test_s3_dates_incoherentes_refusees(db):
    executer(db, "INSERT INTO emprunts (id_document, numero_adherent, date_emprunt, "
             "date_retour) VALUES ('D001', 'A001', '2026-10-01', '2020-01-01')")
    with pytest.raises(ERREURS_CHARGEMENT):
        Mediatheque.charger(db)
