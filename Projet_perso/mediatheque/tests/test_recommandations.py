from datetime import date

import pytest

from conftest import AUJOURDHUI
from mediatheque import recommandations as reco
from mediatheque.adherents import Adherent
from mediatheque.auth import ADHERENT, RESPONSABLE
from mediatheque.documents import DVD, Livre
from mediatheque.exceptions import AccesRefuseError, DocumentInconnuError, MediathequeError
from mediatheque.mediatheque import Mediatheque
from mediatheque.session import ouvrir_session

MDP = "Secret123"


@pytest.fixture
def mr():
    """Petit fonds avec fiches : deux dystopies, un Orwell, un film SF, une comedie."""
    m = Mediatheque()
    docs = [
        Livre("D001", "1984", 1949, "George Orwell").completer_fiche(
            genre="Science-fiction", themes=("dystopie", "pouvoir", "surveillance")),
        Livre("D002", "La Ferme des animaux", 1945, "George Orwell").completer_fiche(
            genre="Roman classique", themes=("pouvoir", "révolution")),
        Livre("D003", "Le Meilleur des mondes", 1932, "Aldous Huxley").completer_fiche(
            genre="Science-fiction", themes=("dystopie", "société")),
        DVD("D004", "Matrix", 1999, 136).completer_fiche(
            genre="Science-fiction", themes=("dystopie", "intelligence artificielle")),
        DVD("D005", "Le Dîner de cons", 1998, 80).completer_fiche(
            genre="Comédie", themes=("humour",)),
        Livre("D006", "Fahrenheit 451", 1953, "Ray Bradbury").completer_fiche(
            genre="Science-fiction", themes=("dystopie", "censure")),
    ]
    for d in docs:
        m.ajouter_document(d)
    for i, (nom, prenom) in enumerate([("Martin", "Lea"), ("Durand", "Hugo"), ("Petit", "Ines")], 1):
        m.ajouter_adherent(Adherent(f"A00{i}", nom, prenom, "standard"))
    m.creer_compte("lea", MDP, ADHERENT, "A001")
    m.creer_compte("hugo", MDP, ADHERENT, "A002")
    m.creer_compte("admin", MDP, RESPONSABLE)
    return m


def test_ressemblance_symetrique_et_nulle_sur_soi(mr):
    a, b = mr["D001"], mr["D003"]
    assert reco.ressemblance(a, b) == reco.ressemblance(b, a) > 0
    assert reco.ressemblance(a, a) == 0


def test_similaires_privilegie_genre_et_themes(mr):
    ids = [d.id for d in reco.similaires(mr, "D001")]
    assert ids[0] in ("D003", "D006", "D004")       # dystopies SF d'abord
    assert "D005" not in ids                          # la comedie n'a rien a voir
    assert "D001" not in ids


def test_similaires_croise_livres_et_films(mr):
    assert "D004" in [d.id for d in reco.similaires(mr, "D003")]


def test_co_emprunts_rapprochent_deux_documents(mr):
    sans = reco.ressemblance(mr["D005"], mr["D002"], reco.co_emprunts(mr))
    for num in ("A001", "A002", "A003"):
        mr.emprunter("D005", num, date(2026, 9, 1))
        mr.retourner("D005", date(2026, 9, 2))
        mr.emprunter("D002", num, date(2026, 9, 3))
        mr.retourner("D002", date(2026, 9, 4))
    avec = reco.ressemblance(mr["D005"], mr["D002"], reco.co_emprunts(mr))
    assert avec > sans


def test_pour_adherent_avec_historique(mr):
    mr.emprunter("D001", "A001", AUJOURDHUI)
    resultat = reco.pour_adherent(mr, "A001", aujourdhui=AUJOURDHUI)
    ids = [d.id for d, _ in resultat]
    assert "D001" not in ids                          # deja emprunte
    assert ids and ids[0] in ("D003", "D006", "D004", "D002")
    assert resultat[0][1].startswith("Parce que vous avez lu « 1984 »")


def test_pour_adherent_sans_historique_donne_les_populaires(mr):
    mr.emprunter("D005", "A002", AUJOURDHUI)
    resultat = reco.pour_adherent(mr, "A001", aujourdhui=AUJOURDHUI)
    assert resultat[0][0].id == "D005" and resultat[0][1] == "Très demandé en ce moment"


# --------------------------------------------------------------- Session
def test_session_fiche_ne_revele_pas_l_emprunteur(mr):
    mr.emprunter("D001", "A002", AUJOURDHUI)
    lea = ouvrir_session(mr, "lea", MDP)
    f = lea.fiche("D001")
    assert f["statut"] == "emprunte" and f["retour_prevu"] is not None
    assert f["historique"] is None
    assert [d.id for d, _ in f["meme_createur"]] == ["D002"]
    admin = ouvrir_session(mr, "admin", MDP)
    assert admin.fiche("D001")["historique"][0]["numero"] == "A002"


def test_session_fiche_inconnue(mr):
    with pytest.raises(DocumentInconnuError):
        ouvrir_session(mr, "lea", MDP).fiche("D999")


def test_session_similaires_exclut_le_meme_auteur_deja_affiche(mr):
    lea = ouvrir_session(mr, "lea", MDP)
    ids = [d.id for d, _ in lea.similaires("D001")]
    assert "D002" not in ids and ids


def test_session_pour_moi_reserve_a_soi(mr):
    lea = ouvrir_session(mr, "lea", MDP)
    with pytest.raises(AccesRefuseError):
        lea.pour_moi(numero="A002")
    assert isinstance(lea.pour_moi(), list)


def test_session_catalogue_par_genre_et_theme(mr):
    lea = ouvrir_session(mr, "lea", MDP)
    assert {d.id for d, _ in lea.catalogue(genre="Comédie")} == {"D005"}
    assert {d.id for d, _ in lea.catalogue("dystopie")} == {"D001", "D003", "D004", "D006"}
    assert ("Science-fiction", 4) in lea.genres()


def test_session_ajouter_document_avec_fiche(mr):
    admin = ouvrir_session(mr, "admin", MDP)
    d = admin.ajouter_document("livre", "D010", "Dune", "1965", "Frank Herbert",
                               genre="Science-fiction", themes="désert|pouvoir", pages="600")
    assert d.themes == ("désert", "pouvoir") and d.pages == 600


# ------------------------------------------------- retours du panel UX
def test_recherche_sans_accents_et_dans_le_resume(mr):
    mr["D001"].completer_fiche(resume="Big Brother vous regarde, écrit par Orwell.")
    lea = ouvrir_session(mr, "lea", MDP)
    assert {d.id for d, _ in lea.catalogue("big brother")} == {"D001"}
    assert {d.id for d, _ in lea.catalogue("diner")} == {"D005"}       # « Dîner »
    assert {d.id for d, _ in lea.catalogue("ORWELL ferme")} == {"D002"}  # tous les mots


def test_catalogue_par_public(mr):
    mr["D005"].completer_fiche(public="jeunesse")
    lea = ouvrir_session(mr, "lea", MDP)
    assert {d.id for d, _ in lea.catalogue(public="jeunesse")} == {"D005"}
    assert ("jeunesse", 1) in lea.publics()


def test_ajouter_document_saisie_invalide_message_clair(mr):
    admin = ouvrir_session(mr, "admin", MDP)
    with pytest.raises(MediathequeError, match="durée en minutes"):
        admin.ajouter_document("dvd", "D020", "Film", "2001", "2h05")
    with pytest.raises(MediathequeError, match="année"):
        admin.ajouter_document("livre", "D021", "Livre", "deux mille", "Auteur")


def test_mis_de_cote_pour(mr):
    mr.emprunter("D001", "A002", AUJOURDHUI)
    mr.reserver("D001", "A001", AUJOURDHUI)
    mr.retourner("D001", AUJOURDHUI)
    admin = ouvrir_session(mr, "admin", MDP)
    assert admin.mis_de_cote_pour("D001").numero == "A001"
    assert admin.mis_de_cote_pour("D003") is None


def test_synonymes_de_recherche(mr):
    lea = ouvrir_session(mr, "lea", MDP)
    assert {d.id for d, _ in lea.catalogue("sf")} == {"D001", "D003", "D004", "D006"}
    assert {d.id for d, _ in lea.catalogue("film")} == {"D004", "D005"}
    # un mot de deux lettres sans synonyme n'est cherche qu'en mot entier
    assert lea.catalogue("ar") == []


def test_realisateur_et_meme_createur(mr):
    from mediatheque.documents import DVD
    mr["D004"].completer_fiche(realisateur="Lana et Lilly Wachowski")
    mr.ajouter_document(DVD("D007", "Matrix Reloaded", 2003, 138).completer_fiche(
        realisateur="Lana et Lilly Wachowski", genre="Science-fiction"))
    lea = ouvrir_session(mr, "lea", MDP)
    assert [d.id for d, _ in lea.fiche("D004")["meme_createur"]] == ["D007"]
    assert {d.id for d, _ in lea.catalogue("wachowski")} == {"D004", "D007"}


def test_reservation_indique_le_retour_prevu_sans_l_emprunteur(mr):
    mr.emprunter("D001", "A002", AUJOURDHUI)
    lea = ouvrir_session(mr, "lea", MDP)
    lea.reserver("D001")
    r = lea.mon_compte()["reservations"][0]
    assert r["retour_prevu"] is not None
    assert "A002" not in str(r) and "Durand" not in str(r)
