import shutil
import tempfile
from datetime import date
from pathlib import Path

from .documents import Livre
from .exceptions import MediathequeError
from .mediatheque import Mediatheque
from .rapports import (du_type, export_retards_csv, parue_apres,
                       retards, top_emprunteurs)

AUJOURDHUI = date(2026, 11, 5)
TENTATIVES = [("D003", "A002"), ("D001", "A002"), ("D002", "A001"),
              ("D005", "A001"), ("D999", "A003"), ("D004", "A009")]


def main(dossier_source="data"):
    # La demo travaille sur une copie temporaire pour ne jamais modifier data/.
    with tempfile.TemporaryDirectory() as tmp:
        dossier = Path(tmp) / "data"
        shutil.copytree(dossier_source, dossier)
        _demo(dossier)


def _demo(dossier):
    with Mediatheque.charger(dossier) as m:
        dispo = sum(1 for d in m if m.disponible(d.id))
        print(f"Mediatheque : {dispo} documents disponibles sur {len(m)}")

        print("\nDocuments tries par titre :")
        for document in sorted(m):
            print(f"  {document}")

        est_livre = du_type(Livre)
        recent = parue_apres(2010)
        print("\nLivres parus apres 2010 :")
        for document in m.rechercher(lambda d: est_livre(d) and recent(d)):
            print(f"  {document}")

        print()
        for id_document, numero in TENTATIVES:
            try:
                m.emprunter(id_document, numero, AUJOURDHUI)
                print(f"Emprunt {id_document} par {numero} : OK")
            except MediathequeError as e:
                print(f"Emprunt {id_document} par {numero} : refuse ({e})")

        liste_retards = list(retards(m, AUJOURDHUI))
        print(f"\nRetards au {AUJOURDHUI} :")
        for emprunt, document, jours in liste_retards:
            print(f"  {emprunt.id_document} {document.titre} - "
                  f"{emprunt.numero_adherent} - {jours} jours de retard")

        top = top_emprunteurs(m)
        print("\nTop emprunteurs : "
              + ", ".join(f"{numero} ({nb})" for numero, nb in top))

        chemin_retards = dossier / "retards.csv"
        nb = export_retards_csv(chemin_retards, liste_retards)
        print(f"Rapport ecrit dans {chemin_retards.name} "
              f"({nb} ligne{'s' if nb > 1 else ''})")

    print("Demo terminee (copie temporaire, data/ inchange)")


if __name__ == "__main__":
    main()