import pytest

from mediatheque import init_db
from mediatheque.mediatheque import Mediatheque
from mediatheque.session import ouvrir_session


def test_init_cree_la_base_et_l_admin(dossier_data, tmp_path, monkeypatch, capsys):
    reponses = iter(["Admin1234", "Admin1234"])
    monkeypatch.setattr(init_db.getpass, "getpass", lambda _: next(reponses))
    db = tmp_path / "m.db"
    assert init_db.main(["--depuis", str(dossier_data), "--db", str(db)]) == 0
    m = Mediatheque.charger(db)
    assert len(m) == 5
    assert ouvrir_session(m, "admin", "Admin1234").est_responsable


def test_init_refuse_d_ecraser(dossier_data, tmp_path, monkeypatch):
    db = tmp_path / "m.db"
    db.write_bytes(b"")
    monkeypatch.setattr(init_db.getpass, "getpass", lambda _: "Admin1234")
    assert init_db.main(["--depuis", str(dossier_data), "--db", str(db)]) == 1
    assert db.read_bytes() == b""


def test_init_confirmation_differente(dossier_data, tmp_path, monkeypatch):
    reponses = iter(["Admin1234", "Autre1234"])
    monkeypatch.setattr(init_db.getpass, "getpass", lambda _: next(reponses))
    assert init_db.main(["--depuis", str(dossier_data), "--db", str(tmp_path / "m.db")]) == 1
    assert not (tmp_path / "m.db").exists()
