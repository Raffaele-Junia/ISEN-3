import sys


def main():
    try:
        nb_argument(sys.argv)
    except ValueError:
        sys.exit("Too few command-line arguments")
    except IndexError:
        sys.exit("Too many command-line arguments")
    try:
        ispyfile(sys.argv[1])
    except ValueError:
        sys.exit("Not a Python file")
    line = lines(sys.argv[1])
    print(line)


def nb_argument(n):
    if len(n) < 2:
        raise (ValueError)
    elif len(n) > 2:
        raise (IndexError)
    else:
        return True


def ispyfile(file):
    if file.endswith(".py"):
        return True
    else:
        raise (ValueError)


def lines(file):
    count = 0
    try:
        with open(file) as f:
            for line in f:
                if line.strip() and not line.lstrip().startswith("#"):
                    count += 1
    except FileNotFoundError:
        sys.exit("File does not exist")
    return count


if __name__ == "__main__":
    main()
