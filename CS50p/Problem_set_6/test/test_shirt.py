
import pytest
from PIL import Image
from shirt import nb_argument, is_same_format, cs_shirt


def test_nb_argument():
    assert nb_argument(["shirt.py", "before.jpg", "after.jpg"]) == True

    with pytest.raises(ValueError):
        nb_argument(["shirt.py"])

    with pytest.raises(ValueError):
        nb_argument(["shirt.py", "before.jpg"])

    with pytest.raises(IndexError):
        nb_argument(["shirt.py", "before.jpg", "after.jpg", "extra.jpg"])


def test_is_same_format():
    assert is_same_format("before.jpg", "after.jpg") == True
    assert is_same_format("before.PNG", "after.png") == True
    assert is_same_format("before.jpeg", "after.jpeg") == True

    with pytest.raises(SystemExit):
        is_same_format("before.bmp", "after.bmp")

    with pytest.raises(SystemExit):
        is_same_format("before.jpg", "after.bmp")

    with pytest.raises(ValueError):
        is_same_format("before.jpg", "after.png")


def test_cs_shirt(tmp_path):
    before = tmp_path / "before.jpg"
    after = tmp_path / "after.jpg"

    # Create a test input image
    image = Image.new("RGB", (600, 800), "white")
    image.save(before)

    # Create a transparent test shirt
    shirt = Image.new("RGBA", (300, 400), (255, 0, 0, 128))
    shirt.save("shirt.png")

    cs_shirt(str(before), str(after))

    assert after.exists()

    result = Image.open(after)
    assert result.size == (300, 400)


def test_cs_shirt_missing_file(tmp_path):
    before = tmp_path / "missing.jpg"
    after = tmp_path / "after.jpg"

    with pytest.raises(SystemExit):
        cs_shirt(str(before), str(after))
