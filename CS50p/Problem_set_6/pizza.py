import sys
import csv
import tabulate

def main():
    try:
        nb_argument(sys.argv)
    except ValueError:
        sys.exit("Too few command-line arguments")
    except IndexError:
        sys.exit("Too many command-line arguments")
    try:
        iscsvfile(sys.argv[1])
    except ValueError:
        sys.exit("Not a CSV file")
    result = remaster(sys.argv[1])
    print(result)


def nb_argument(n):
    if len(n) < 2:
        raise (ValueError)
    elif len(n) > 2:
        raise (IndexError)
    else:
        return True


def iscsvfile(file):
    if file.endswith(".csv"):
        return True
    else:
        raise (ValueError)

def remaster(file):
    try:
        with open(file) as f:
            reader = csv.DictReader(f)
            return tabulate.tabulate(reader, headers="keys", tablefmt="grid")

    except FileNotFoundError:
        sys.exit("File does not exist")

if __name__ == "__main__":
    main()
