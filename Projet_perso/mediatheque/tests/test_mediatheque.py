from datetime import date

import pytest

from conftest import AUJOURDHUI, DATA
from mediatheque.adherents import Adherent
from mediatheque.documents import Livre
from mediatheque.exceptions import (AdherentInconnuError, DocumentIndisponibleError,
                                    DocumentInconnuError, MediathequeError,
                                    QuotaDepasseError)
from mediatheque.main import main
from mediatheque.mediatheque import Mediatheque
from mediatheque.rapports import (du_type, export_retards_csv, par_auteur,
                                  parue_apres, retards, top_emprunteurs)


def test_emprunt_ok(m):
    e = m.emprunter("D001", "A001", AUJOURDHUI)
    assert e.en_cours
    assert not m.disponible("D001")


def test_document_deja_emprunte(m):
    m.emprunter("D001", "A001", AUJOURDHUI)
    with pytest.raises(DocumentIndisponibleError):
        m.emprunter("D001", "A002", AUJOURDHUI)


def test_document_et_adherent_inconnus(m):
    with pytest.raises(DocumentInconnuError):
        m.emprunter("D999", "A001")
    with pytest.raises(AdherentInconnuError):
        m.emprunter("D001", "A999")
    with pytest.raises(DocumentInconnuError):
        m.disponible("D999")


def test_quota_standard_depasse(m):
    for id_doc in ("D001", "D002", "D003"):
        m.emprunter(id_doc, "A001", AUJOURDHUI)
    with pytest.raises(QuotaDepasseError) as exc:
        m.emprunter("D004", "A001", AUJOURDHUI)
    assert (exc.value.nb_actuel, exc.value.quota) == (3, 3)


def test_retour_libere_le_document(m):
    m.emprunter("D001", "A001", AUJOURDHUI)
    e = m.retourner("D001", date(2026, 11, 10))
    assert e.date_retour == date(2026, 11, 10)
    assert m.disponible("D001")
    m.emprunter("D001", "A002", AUJOURDHUI)


def test_retour_sans_emprunt(m):
    with pytest.raises(MediathequeError):
        m.retourner("D001")


def test_filtres_et_recherche(m):
    livres_recents = m.rechercher(lambda d: du_type(Livre)(d) and parue_apres(2010)(d))
    assert [d.id for d in livres_recents] == ["D001"]
    assert [d.id for d in m.rechercher(par_auteur("martin"))] == ["D004"]


def test_retards_et_top(m, tmp_path):
    m.emprunter("D001", "A001", date(2026, 10, 1))
    m.emprunter("D002", "A001", date(2026, 11, 1))
    liste = list(retards(m, AUJOURDHUI))
    assert [(e.id_document, j) for e, _, j in liste] == [("D001", 14)]
    assert top_emprunteurs(m) == [("A001", 2)]
    chemin = tmp_path / "retards.csv"
    assert export_retards_csv(chemin, liste) == 1
    assert "D001,A001,14" in chemin.read_text(encoding="utf-8")


def test_aller_retour_csv_avec_accents(m, tmp_path):
    m.ajouter_adherent(Adherent("A003", "Lefèvre", "Hélène", "standard"))
    m.emprunter("D001", "A003", AUJOURDHUI)
    m.sauvegarder(tmp_path)
    m2 = Mediatheque.charger(tmp_path)
    assert len(m2) == len(m)
    assert m2._adherents["A003"].prenom == "Hélène"
    assert not m2.disponible("D001")


def test_context_manager_ne_sauvegarde_pas_en_cas_d_erreur(dossier_data):
    avant = (dossier_data / "emprunts.csv").read_bytes()
    with pytest.raises(RuntimeError):
        with Mediatheque.charger(dossier_data) as m:
            m.emprunter("D005", "A003", AUJOURDHUI)
            raise RuntimeError
    assert (dossier_data / "emprunts.csv").read_bytes() == avant


def test_demo_ne_modifie_pas_les_donnees(dossier_data, capsys):
    avant = {p.name: p.read_bytes() for p in dossier_data.iterdir()}
    main(dossier_data)
    assert {p.name: p.read_bytes() for p in dossier_data.iterdir()} == avant
    assert "Fluent Python" in capsys.readouterr().out


def test_chargement_des_vraies_donnees():
    assert len(Mediatheque.charger(DATA)) == 5
