"""Audit securite P1 : injection de formules dans export_retards_csv."""
import csv
from datetime import date

import pytest

from mediatheque.auth import RESPONSABLE
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


@pytest.mark.xfail(strict=True, reason="faille S7 : id_document non valide ni neutralise : "
                   "formule executee a l'ouverture de l'export dans un tableur")
@pytest.mark.parametrize("charge", ['=HYPERLINK("http://evil.example","x")',
                                    "+1+1", "-2+3", "@SUM(1)", "\t=1"])
def test_s7_formule_neutralisee_dans_l_export(m, tmp_path, charge):
    m.creer_compte("admin", "Secret123", RESPONSABLE)
    admin = ouvrir_session(m, "admin", "Secret123")
    admin.ajouter_document("livre", charge, "Titre", 2020, "Auteur")  # accepte tel quel
    admin.enregistrer_emprunt(charge, "A001", date(2026, 1, 1))
    chemin = tmp_path / "retards.csv"
    export_retards_csv(chemin, admin.retards(date(2026, 11, 5)))
    assert not any(c.startswith(DANGEREUX) for c in cellules(chemin))
