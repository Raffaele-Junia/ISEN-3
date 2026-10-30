
import pytest
import csv
from scourgify import nb_argument, iscsvfile, after


def test_nb_argument():
    assert nb_argument(["scourgify.py", "before.csv", "after.csv"]) == True


def test_error_nb_argument():
    with pytest.raises(ValueError):
        nb_argument(["scourgify.py"])

    with pytest.raises(ValueError):
        nb_argument(["scourgify.py", "before.csv"])

    with pytest.raises(IndexError):
        nb_argument(["scourgify.py", "before.csv", "after.csv", "extra.csv"])


def test_iscsvfile():
    assert iscsvfile("before.csv") == True

    with pytest.raises(ValueError):
        iscsvfile("before.txt")

    with pytest.raises(ValueError):
        iscsvfile("before.csv.txt")


def test_after(tmp_path):
    before = tmp_path / "before.csv"
    after_file = tmp_path / "after.csv"

    before.write_text(
        'name,house\n'
        '"Potter, Harry",Gryffindor\n'
        '"Malfoy, Draco",Slytherin\n',
        encoding="utf-8"
    )

    after(str(before), str(after_file))

    with open(after_file, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    assert rows == [
        {"first": "Harry", "last": "Potter", "house": "Gryffindor"},
        {"first": "Draco", "last": "Malfoy", "house": "Slytherin"}
    ]


def test_after_missing_file(tmp_path):
    before = tmp_path / "missing.csv"
    after_file = tmp_path / "after.csv"

    with pytest.raises(SystemExit):
        after(str(before), str(after_file))
