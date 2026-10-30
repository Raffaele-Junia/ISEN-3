from fuel import gauge, convert


def test_gauge():
    assert gauge(25) == "25%"
    assert gauge(50) == "50%"
    assert gauge(100) == "F"
    assert gauge(75) == "75%"
    assert gauge(0) == "E"
    assert gauge(1) == "E"
    assert gauge(99) == "F"


def test_convert():
    assert convert("1/4") == 25
    assert convert("1/2") == 50
    assert convert("1/1") == 100
    assert convert("3/4") == 75
    assert convert("0/4") == 0


def test_convert_errors():
    import pytest

    with pytest.raises(ValueError):
        convert("1/0")

    with pytest.raises(ValueError):
        convert("5/4")

    with pytest.raises(ValueError):
        convert("abc")

    with pytest.raises(ValueError):
        convert("1")
