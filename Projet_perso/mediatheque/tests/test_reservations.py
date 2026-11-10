from datetime import date, timedelta

import pytest

from conftest import AUJOURDHUI
from mediatheque.adherents import Adherent
from mediatheque.exceptions import DocumentIndisponibleError, ReservationImpossibleError
from mediatheque.mediatheque import Mediatheque
from mediatheque.reservation import (ANNULEE, DELAI_RETRAIT_JOURS, DISPONIBLE,
                                     EN_ATTENTE, EXPIREE, HONOREE, MAX_RESERVATIONS)

J = AUJOURDHUI


@pytest.fixture
def m3(m):
    """D001 emprunte par A001 ; A003 existe aussi."""
    m.ajouter_adherent(Adherent("A003", "Petit", "Ines", "standard"))
    m.emprunter("D001", "A001", J)
    return m


def test_reserver_document_emprunte(m3):
    r = m3.reserver("D001", "A002", J)
    assert r.statut == EN_ATTENTE
    assert m3.file_attente("D001") == [r]


def test_reserver_document_disponible_refuse(m3):
    with pytest.raises(ReservationImpossibleError):
        m3.reserver("D002", "A002", J)


def test_reserver_son_propre_emprunt_refuse(m3):
    with pytest.raises(ReservationImpossibleError):
        m3.reserver("D001", "A001", J)


def test_double_reservation_refusee(m3):
    m3.reserver("D001", "A002", J)
    with pytest.raises(ReservationImpossibleError):
        m3.reserver("D001", "A002", J)


def test_limite_de_reservations(m):
    m.ajouter_adherent(Adherent("A003", "Petit", "Ines", "premium"))
    ids = ["D001", "D002", "D003", "D004"]
    for id_doc in ids:
        m.emprunter(id_doc, "A003", J)
    for id_doc in ids[:MAX_RESERVATIONS]:
        m.reserver(id_doc, "A002", J)
    with pytest.raises(ReservationImpossibleError):
        m.reserver(ids[MAX_RESERVATIONS], "A002", J)


def test_retour_met_de_cote_pour_le_premier(m3):
    r1 = m3.reserver("D001", "A002", J)
    r2 = m3.reserver("D001", "A003", J)
    m3.retourner("D001", J + timedelta(days=2))
    assert (r1.statut, r1.date_disponible) == (DISPONIBLE, J + timedelta(days=2))
    assert r2.statut == EN_ATTENTE
    assert not m3.disponible("D001")                 # pour le public
    assert not m3.disponible("D001", "A003")         # ni pour le 2e de la file
    assert m3.disponible("D001", "A002")             # mais oui pour le 1er


def test_seul_le_reservant_peut_emprunter(m3):
    r = m3.reserver("D001", "A002", J)
    m3.retourner("D001", J)
    with pytest.raises(DocumentIndisponibleError):
        m3.emprunter("D001", "A003", J)
    m3.emprunter("D001", "A002", J)
    assert r.statut == HONOREE
    assert m3.file_attente("D001") == []


def test_expiration_passe_au_suivant(m3):
    r1 = m3.reserver("D001", "A002", J)
    r2 = m3.reserver("D001", "A003", J)
    m3.retourner("D001", J)
    plus_tard = J + timedelta(days=DELAI_RETRAIT_JOURS + 1)
    m3.actualiser_reservations(plus_tard)
    assert r1.statut == EXPIREE
    assert (r2.statut, r2.date_disponible) == (DISPONIBLE, plus_tard)


def test_expiration_sans_suivant_libere_le_document(m3):
    m3.reserver("D001", "A002", J)
    m3.retourner("D001", J)
    m3.emprunter("D001", "A003", J + timedelta(days=DELAI_RETRAIT_JOURS + 1))


def test_annulation_d_une_mise_de_cote(m3):
    r1 = m3.reserver("D001", "A002", J)
    r2 = m3.reserver("D001", "A003", J)
    m3.retourner("D001", J)
    m3.annuler_reservation("D001", "A002", J)
    assert r1.statut == ANNULEE and r2.statut == DISPONIBLE


def test_annuler_sans_reservation(m3):
    with pytest.raises(ReservationImpossibleError):
        m3.annuler_reservation("D001", "A002")


@pytest.mark.parametrize("nom", ["m.db", "dossier"])
def test_reservations_persistees(m3, tmp_path, nom):
    m3.reserver("D001", "A002", J)
    m3.retourner("D001", J)
    m3.reserver("D001", "A003", J)
    m3.sauvegarder(tmp_path / nom)
    m2 = Mediatheque.charger(tmp_path / nom)
    assert m2.reservations == m3.reservations
    assert m2.disponible("D001", "A002") and not m2.disponible("D001")
