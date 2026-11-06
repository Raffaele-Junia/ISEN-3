
import subprocess


def main():
    groupe = "groupe_A"

    # Première commande : extraire les étudiants du groupe
    resultat = subprocess.run(
        ["findstr", groupe, "inscriptions.txt"],
        capture_output=True,
        text=True
    )

    # Vérifier si des étudiants ont été trouvés
    if resultat.returncode == 1:
        print("Aucun étudiant inscrit dans ce groupe")
        return

    # Deuxième commande : trier les résultats
    tri = subprocess.run(
        ["sort"],
        input=resultat.stdout,
        capture_output=True,
        text=True
    )

    # Afficher la liste triée
    print(tri.stdout)

    # Compter les étudiants
    nombre = len(tri.stdout.splitlines())
    print(f"Nombre d'étudiants : {nombre}")


if __name__ == "__main__":
    main()
