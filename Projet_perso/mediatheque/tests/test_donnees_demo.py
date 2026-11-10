from pathlib import Path

from mediatheque.mediatheque import Mediatheque

DATA_DEMO = Path(__file__).resolve().parent.parent / "data_demo"


def test_jeu_de_demo_coherent():
    """data_demo/ (genere par scripts/generer_donnees.py) passe tous les controles."""
    m = Mediatheque.charger(DATA_DEMO)
    assert len(m) >= 100 and len(m.adherents) >= 40
    assert any(e.en_cours for e in m.emprunts)
    assert any(r.active for r in m.reservations)
    types = {d.CLE for d in m}
    assert types == {"livre", "dvd", "revue"}
