from .epreuve import Epreuve
from .etudiants import Etudiant, AuditeurLibre, Groupe
from .questions import (
    QuestionQCM,
    QuestionNumerique,
    QuestionOuverte,
    QuestionVraiFaux
)
from .statistiques import moyenne, creer_filtre_admis, INDICATEURS


QUESTIONS = [
    (QuestionQCM, ("Quel mot-cle definit une classe ?", 3,
                   ["def", "class", "struct"], 1)),

    (QuestionNumerique, ("Que vaut 7 / 2 ?", 2, 3.5, 0.01)),

    (QuestionOuverte, ("Citez des principes de la POO.", 3,
                       ["encapsulation", "heritage", "polymorphisme"])),

    (QuestionVraiFaux, ("Python est type statiquement.", 2, False)),
]


COPIES = {
    "E001": [1, 3.5, "Encapsulation, heritage et polymorphisme", False],
    "E002": [0, 3.5, "L'heritage", False],
    "E003": [1, 3.5, "encapsulation et heritage", True],
    "AL01": [2, 4, "", False],
}


def main():
    epreuve = Epreuve("POO Python", 30)

    for classe, arguments in QUESTIONS:
        question = classe(*arguments)
        epreuve.ajouter(question)

    print(epreuve)

    groupe = Groupe("G1")

    groupe.ajouter(Etudiant("Martin", "Lea", "E001"))
    groupe.ajouter(Etudiant("Durand", "Hugo", "E002"))
    groupe.ajouter(Etudiant("Petit", "Ines", "E003"))
    groupe.ajouter(AuditeurLibre("Sami Benali", "AL01"))

    print(groupe)

    notes = []

    for numero, reponses in COPIES.items():

        note = epreuve.corriger(reponses)
        notes.append(note)

        personne = groupe._membres[numero]
        print(f"{personne.nom_complet} : {note:.2f} / 20")


    for nom, fonction in INDICATEURS.items():
        print(f"{nom} : {fonction(notes)}")

    filtre = creer_filtre_admis(10)
    admis = list(filter(filtre, notes))

    print(f"Admis : {len(admis)} / {len(notes)}")


if __name__ == "__main__":
    main()