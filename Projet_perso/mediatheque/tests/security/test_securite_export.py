"""Audit securite P1 : injection de formules dans export_retards_csv."""
import csv
from datetime import date

import pytest

from mediatheque.auth import RESPONSABLE
from mediatheque.documents import Livre
from mediatheque.exceptions import MediathequeError
from mediatheque.rapports import export_retards_csv, retards
from mediatheque.session import ouvrir_session

DANGEREUX = ("=", "+", "-", "@", "\t", "\r")


def cellules(chemin):
    with open(chemin, encoding="utf-8", newline="") as f:
        return [c for ligne in list(csv.reader(f))[1:] for c in ligne]


def test_numero_adherent_exporte_est_sur(m, tmp_path):
    """numero_adherent est valide (A\\d{3}) : il ne peut pas porter de formule."""
    m.emprunter("D001", "A001", date(2026, 1, 1))
    chemin = tmp_path / "retards.csv"
    export_retards_csv(chemin, retards(m, date(2026, 11, 5)))
    assert cellules(chemin) and not any(c.startswith(DANGEREUX) for c in cellules(chemin))


CHARGES = ['=HYPERLINK("http://evil.example","x")', "+1+1", "-2+3", "@SUM(1)", "\t=1"]


@pytest.mark.parametrize("charge", CHARGES + ["\r=1", "D001 ", "d001", "D", "", "D1;2"])
def test_s7_id_document_valide_a_la_creation(m, charge):
    """Defense 1 : Session.ajouter_document n'accepte que D suivi de chiffres."""
    m.creer_compte("admin", "Secret123", RESPONSABLE)
    admin = ouvrir_session(m, "admin", "Secret123")
    with pytest.raises(MediathequeError):
        admin.ajouter_document("livre", charge, "Titre", 2020, "Auteur")
    assert charge not in m


@pytest.mark.parametrize("charge", CHARGES)
def test_s7_formule_neutralisee_dans_l_export(m, tmp_path, charge):
    """Defense 2 : meme avec un id falsifie (base modifiee, contournement de
    Session), l'export ne contient aucune cellule interpretable en formule."""
    m.creer_compte("admin", "Secret123", RESPONSABLE)
    admin = ouvrir_session(m, "admin", "Secret123")
    m.ajouter_document(Livre(charge, "Titre", 2020, "Auteur"))  # hors Session
    admin.enregistrer_emprunt(charge, "A001", date(2026, 1, 1))
    chemin = tmp_path / "retards.csv"
    export_retards_csv(chemin, admin.retards(date(2026, 11, 5)))
    contenu = cellules(chemin)
    assert "'" + charge in contenu
    assert not any(c.startswith(DANGEREUX) for c in contenu)


def test_s7_id_valide_accepte_et_exporte_tel_quel(m, tmp_path):
    m.creer_compte("admin", "Secret123", RESPONSABLE)
    admin = ouvrir_session(m, "admin", "Secret123")
    admin.ajouter_document("livre", "D123", "Titre", 2020, "Auteur")
    admin.enregistrer_emprunt("D123", "A001", date(2026, 1, 1))
    chemin = tmp_path / "retards.csv"
    export_retards_csv(chemin, admin.retards(date(2026, 11, 5)))
    assert "D123" in cellules(chemin)
