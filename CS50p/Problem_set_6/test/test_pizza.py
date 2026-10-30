
import pytest
from pizza import nb_argument, iscsvfile, remaster


def test_nb_argument():
    assert nb_argument(["pizza.py", "regular.csv"]) == True


def test_error_nb_argument():
    with pytest.raises(ValueError):
        nb_argument(["pizza.py"])

    with pytest.raises(IndexError):
        nb_argument(["pizza.py", "regular.csv", "sicilian.csv"])


def test_iscsvfile():
    assert iscsvfile("regular.csv") == True

    with pytest.raises(ValueError):
        iscsvfile("sicilian.txt")

    with pytest.raises(ValueError):
        iscsvfile("regular.csv.txt")


def test_remaster():
    with pytest.raises(SystemExit):
        remaster("invalid_file.csv")


def test_remaster_output():
    result = remaster("sicilian.csv")

    assert "Sicilian Pizza" in result
    assert "Small" in result
    assert "Large" in result
    assert "$33.50" in result
    assert "$47.95" in result