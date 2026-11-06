
import re

avis = [
    " Super cours ! Ecrivez -moi a lina . m@isen .fr pour les notes .",
    "Le TP etait long mais utile .",
    " Appelez -moi au 06 45 12 78 90 si besoin .",
    " Tres clair . Mon mail : y. benali@gmail .com , tel 07 11 22 33 44. ",
]

motif_email = r"[\w%+-]+(?:\s*\.\s*[\w%+-]+)*\s*@\s*[\w-]+(?:\s*\.\s*[\w-]+)+"
motif_tel = r"\b0[1-9](?:[ .-]?\d{2}){4}\b"


def main():
    print("AVIS PROBLEMATIQUES")

    for texte in avis:
        if re.search(motif_email, texte, re.IGNORECASE) or re.search(motif_tel, texte):
            print(texte)

    print("\nADRESSES EMAIL")

    emails = []

    for texte in avis:
        emails.extend(re.findall(motif_email, texte, re.IGNORECASE))

    print(emails)
    print("\nAVIS PUBLIES")

    for texte in avis:
        texte = re.sub(motif_email, "[email masqué]", texte, flags=re.IGNORECASE)
        texte = re.sub(motif_tel, "[tel masqué]", texte)

        print(texte)


if __name__ == "__main__":
    main()
