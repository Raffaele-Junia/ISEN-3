
from pathlib import Path


def main():
    rendus = [
        Path("rendus/groupe_A/dupont_tp3.py"),
        Path("rendus/groupe_A/martin_tp3.txt"),
        Path("rendus/groupe_B/benali_tp3.py"),
    ]

    groupe(rendus)
    python(rendus)
    construire(rendus)


def groupe(rendus):
    for p in rendus:
        groupe = p.parent.name
        name = p.stem.split("_")[0]
        print(f"{name} : {groupe}")


def python(rendus):
    for p in rendus:
        if p.suffix != ".py":
            print("rendu refusé : mauvaise extension")


def construire(rendus):
    for p in rendus:
        groupe = p.parent.name
        name = p.stem.split("_")[0]

        rapport = Path("rapports") / {groupe} / f"{name}_rapport.pdf"

        if rapport.exists():
            print(f"Rapport trouvé : {rapport}")
        else:
            print(f"rapport manquant : {rapport}")


if __name__ == "__main__":
    main()
