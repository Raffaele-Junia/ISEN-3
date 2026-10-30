import sys
from PIL import Image, ImageOps


def main():
    try:
        nb_argument(sys.argv)
    except ValueError:
        sys.exit("Too few command-line arguments")
    except IndexError:
        sys.exit("Too many command-line arguments")

    try:
        is_same_format(sys.argv[1], sys.argv[2])
    except ValueError:
        sys.exit("Input and output have different extensions")

    cs_shirt(sys.argv[1], sys.argv[2])


def nb_argument(n):
    if len(n) < 3:
        raise ValueError
    elif len(n) > 3:
        raise IndexError
    return True


def is_same_format(file1, file2):
    valid_extensions = (".jpg", ".jpeg", ".png")

    extension1 = file1.lower().rsplit(".", 1)[-1]
    extension2 = file2.lower().rsplit(".", 1)[-1]

    if f".{extension1}" not in valid_extensions:
        sys.exit("Invalid input")

    if f".{extension2}" not in valid_extensions:
        sys.exit("Invalid output")

    if extension1 != extension2:
        raise ValueError

    return True


def cs_shirt(file1, file2):
    try:
        image = Image.open(file1)
    except FileNotFoundError:
        sys.exit("Input does not exist")

    shirt = Image.open("shirt.png")

    image = ImageOps.fit(image, shirt.size)
    image.paste(shirt, shirt)
    image.save(file2)


if __name__ == "__main__":
    main()
