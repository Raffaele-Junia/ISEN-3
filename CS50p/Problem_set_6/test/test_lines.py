
from lines import nb_argument, ispyfile, lines
import pytest

def test_nb_argument():
    assert nb_argument(["lines.py", "hello.py"]) == True

def test_error_nb_argument():
    with pytest.raises(ValueError):
        nb_argument(["lines.py"])

    with pytest.raises(IndexError):
        nb_argument(["lines.py", "hello.py", "goodbye.py"])

def test_ispyfile():
    assert ispyfile("hello.py") == True

    with pytest.raises(ValueError):
        ispyfile("hello.txt")

    with pytest.raises(ValueError):
        ispyfile("hello.py.txt")

def test_lines():
    assert lines("hello.py") == 2
    assert lines("even.py") == 5

    with pytest.raises(SystemExit):
        lines("hell.py")
