
import sys
import csv


def main():
    try:
        nb_argument(sys.argv)
    except ValueError:
        sys.exit("Too few command-line arguments")
    except IndexError:
        sys.exit("Too many command-line arguments")

    try:
        iscsvfile(sys.argv[1])
        iscsvfile(sys.argv[2])
    except ValueError:
        sys.exit("Not a CSV file")

    after(sys.argv[1], sys.argv[2])


def nb_argument(n):
    if len(n) < 3:
        raise ValueError
    elif len(n) > 3:
        raise IndexError
    return True


def iscsvfile(file):
    if file.endswith(".csv"):
        return True
    else:
        raise ValueError


def after(before, after):
    try:
        with open(before) as bef, open(after, "w", newline="") as af:
            reader = csv.DictReader(bef)

            writer = csv.DictWriter(
                af,
                fieldnames=["first", "last", "house"]
            )

            writer.writeheader()

            for row in reader:
                last, first = row["name"].split(",")

                writer.writerow({
                    "first": first.strip(),
                    "last": last.strip(),
                    "house": row["house"]
                })

    except FileNotFoundError:
        sys.exit(f"Could not read {before}")


if __name__ == "__main__":
    main()
