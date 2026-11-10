"""Genere un jeu de donnees realiste et COHERENT dans data_demo/.

    uv run python scripts/generer_donnees.py [dossier] [--graine 42]

Le catalogue (livres, DVD, revues) et les adherents sont ecrits a la main ;
l'historique (emprunts, retours, reservations) est obtenu en SIMULANT cinq mois
d'activite avec le vrai moteur `Mediatheque` : chaque operation respecte donc les
regles metier (quotas, file d'attente, mise de cote, coherence au chargement).
Le resultat est deterministe pour une graine donnee.
"""
import argparse
import random
from datetime import date, timedelta
from pathlib import Path

from mediatheque.adherents import Adherent
from mediatheque.documents import DVD, Livre, Revue
from mediatheque.exceptions import MediathequeError
from mediatheque.mediatheque import Mediatheque

LIVRES = [
    ("Les Misérables", 1862, "Victor Hugo"), ("Notre-Dame de Paris", 1831, "Victor Hugo"),
    ("Madame Bovary", 1857, "Gustave Flaubert"), ("Germinal", 1885, "Émile Zola"),
    ("L'Assommoir", 1877, "Émile Zola"), ("Le Rouge et le Noir", 1830, "Stendhal"),
    ("Le Père Goriot", 1835, "Honoré de Balzac"), ("Le Comte de Monte-Cristo", 1844, "Alexandre Dumas"),
    ("Les Trois Mousquetaires", 1844, "Alexandre Dumas"), ("Bel-Ami", 1885, "Guy de Maupassant"),
    ("Du côté de chez Swann", 1913, "Marcel Proust"), ("Voyage au bout de la nuit", 1932, "Louis-Ferdinand Céline"),
    ("L'Étranger", 1942, "Albert Camus"), ("La Peste", 1947, "Albert Camus"),
    ("Le Petit Prince", 1943, "Antoine de Saint-Exupéry"), ("Vol de nuit", 1931, "Antoine de Saint-Exupéry"),
    ("La Condition humaine", 1933, "André Malraux"), ("Bonjour tristesse", 1954, "Françoise Sagan"),
    ("Les Choses", 1965, "Georges Perec"), ("W ou le Souvenir d'enfance", 1975, "Georges Perec"),
    ("Zazie dans le métro", 1959, "Raymond Queneau"), ("La Vie devant soi", 1975, "Romain Gary"),
    ("Les Années", 2008, "Annie Ernaux"), ("La Place", 1983, "Annie Ernaux"),
    ("L'Amant", 1984, "Marguerite Duras"), ("Le Grand Meaulnes", 1913, "Alain-Fournier"),
    ("Thérèse Raquin", 1867, "Émile Zola"), ("Candide", 1759, "Voltaire"),
    ("Vingt mille lieues sous les mers", 1870, "Jules Verne"), ("Le Tour du monde en quatre-vingts jours", 1872, "Jules Verne"),
    ("Chanson douce", 2016, "Leïla Slimani"), ("L'Anomalie", 2020, "Hervé Le Tellier"),
    ("Au revoir là-haut", 2013, "Pierre Lemaitre"), ("Petit Pays", 2016, "Gaël Faye"),
    ("Le Consentement", 2020, "Vanessa Springora"), ("Changer l'eau des fleurs", 2018, "Valérie Perrin"),
    ("Les Bienveillantes", 2006, "Jonathan Littell"), ("Riquet à la houppe", 2016, "Amélie Nothomb"),
    ("Stupeur et Tremblements", 1999, "Amélie Nothomb"), ("Vernon Subutex", 2015, "Virginie Despentes"),
    ("1984", 1949, "George Orwell"), ("La Ferme des animaux", 1945, "George Orwell"),
    ("Le Meilleur des mondes", 1932, "Aldous Huxley"), ("Fahrenheit 451", 1953, "Ray Bradbury"),
    ("Dune", 1965, "Frank Herbert"), ("Fondation", 1951, "Isaac Asimov"),
    ("Le Seigneur des anneaux", 1954, "J. R. R. Tolkien"), ("Le Hobbit", 1937, "J. R. R. Tolkien"),
    ("Harry Potter à l'école des sorciers", 1997, "J. K. Rowling"), ("Orgueil et Préjugés", 1813, "Jane Austen"),
    ("Jane Eyre", 1847, "Charlotte Brontë"), ("Les Hauts de Hurlevent", 1847, "Emily Brontë"),
    ("Crime et Châtiment", 1866, "Fiodor Dostoïevski"), ("Anna Karénine", 1877, "Léon Tolstoï"),
    ("Cent ans de solitude", 1967, "Gabriel García Márquez"), ("Le Vieil Homme et la Mer", 1952, "Ernest Hemingway"),
    ("Des souris et des hommes", 1937, "John Steinbeck"), ("Les Raisins de la colère", 1939, "John Steinbeck"),
    ("Beloved", 1987, "Toni Morrison"), ("La Route", 2006, "Cormac McCarthy"),
    ("Le Nom de la rose", 1980, "Umberto Eco"), ("L'Insoutenable Légèreté de l'être", 1984, "Milan Kundera"),
    ("Kafka sur le rivage", 2002, "Haruki Murakami"), ("Norwegian Wood", 1987, "Haruki Murakami"),
    ("L'Alchimiste", 1988, "Paulo Coelho"), ("Le Parfum", 1985, "Patrick Süskind"),
    ("Sapiens", 2011, "Yuval Noah Harari"), ("Une brève histoire du temps", 1988, "Stephen Hawking"),
    ("Le Deuxième Sexe", 1949, "Simone de Beauvoir"), ("Tristes Tropiques", 1955, "Claude Lévi-Strauss"),
    ("Fluent Python", 2022, "Luciano Ramalho"), ("Clean Code", 2008, "Robert C. Martin"),
    ("Design Patterns", 1994, "Erich Gamma"), ("The Pragmatic Programmer", 2019, "David Thomas"),
    ("Structure and Interpretation of Computer Programs", 1996, "Harold Abelson"),
    ("Introduction to Algorithms", 2022, "Thomas H. Cormen"), ("Automate the Boring Stuff with Python", 2019, "Al Sweigart"),
    ("Astérix le Gaulois", 1961, "René Goscinny"), ("Tintin au Tibet", 1960, "Hergé"),
    ("Persepolis", 2000, "Marjane Satrapi"), ("Maus", 1986, "Art Spiegelman"),
    ("L'Arabe du futur", 2014, "Riad Sattouf"), ("Blacksad", 2000, "Juan Díaz Canales"),
]

DVDS = [
    ("Inception", 2010, 148), ("Interstellar", 2014, 169), ("Le Fabuleux Destin d'Amélie Poulain", 2001, 122),
    ("Intouchables", 2011, 112), ("La Haine", 1995, 98), ("Les Quatre Cents Coups", 1959, 99),
    ("À bout de souffle", 1960, 90), ("Le Dîner de cons", 1998, 80), ("La Cité de la peur", 1994, 93),
    ("OSS 117 : Le Caire, nid d'espions", 2006, 99), ("Le Voyage de Chihiro", 2001, 125),
    ("Mon voisin Totoro", 1988, 86), ("Princesse Mononoké", 1997, 134), ("Parasite", 2019, 132),
    ("Pulp Fiction", 1994, 154), ("Le Parrain", 1972, 175), ("Retour vers le futur", 1985, 116),
    ("Matrix", 1999, 136), ("Le Seigneur des anneaux : La Communauté de l'anneau", 2001, 178),
    ("Ratatouille", 2007, 111), ("WALL-E", 2008, 98), ("La La Land", 2016, 128),
    ("Portrait de la jeune fille en feu", 2019, 122), ("Anatomie d'une chute", 2023, 151),
    ("Les Choristes", 2004, 97), ("Le Grand Bleu", 1988, 168), ("Astérix et Obélix : Mission Cléopâtre", 2002, 107),
    ("Shining", 1980, 146), ("Alien", 1979, 117), ("Blade Runner", 1982, 117),
]

REVUES = [
    ("Science et Vie", 2026, [1295, 1296, 1297, 1298]), ("Sciences et Avenir", 2026, [935, 936, 937]),
    ("Courrier international", 2026, [1820, 1821, 1822]), ("Le Monde diplomatique", 2026, [866, 867]),
    ("Philosophie Magazine", 2026, [193, 194]), ("Géo", 2026, [559, 560]),
    ("Pour la Science", 2026, [575, 576]), ("Télérama", 2026, [3901, 3902]),
    ("L'Histoire", 2026, [535]), ("Epsiloon", 2026, [52, 53]),
]

ADHERENTS = [
    ("Martin", "Léa"), ("Durand", "Hugo"), ("Petit", "Inès"), ("Bernard", "Lucas"), ("Dubois", "Chloé"),
    ("Moreau", "Nathan"), ("Laurent", "Manon"), ("Simon", "Théo"), ("Michel", "Camille"), ("Lefebvre", "Louis"),
    ("Leroy", "Jade"), ("Roux", "Gabriel"), ("David", "Louise"), ("Bertrand", "Arthur"), ("Morel", "Alice"),
    ("Fournier", "Raphaël"), ("Girard", "Emma"), ("Bonnet", "Jules"), ("Dupont", "Lina"), ("Lambert", "Adam"),
    ("Fontaine", "Rose"), ("Rousseau", "Sacha"), ("Vincent", "Mila"), ("Muller", "Noah"), ("Lefèvre", "Anna"),
    ("Faure", "Tom"), ("André", "Julia"), ("Mercier", "Ethan"), ("Blanc", "Zoé"), ("Guérin", "Paul"),
    ("Boyer", "Agathe"), ("Garnier", "Victor"), ("Chevalier", "Nina"), ("François", "Mathis"), ("Legrand", "Margaux"),
    ("Gauthier", "Yanis"), ("Garcia", "Clara"), ("Perrin", "Maël"), ("Robin", "Juliette"), ("Clément", "Samuel"),
    ("Nguyen", "Lou"), ("Diallo", "Moussa"), ("Benali", "Yasmine"), ("Kowalski", "Oskar"), ("Da Silva", "Beatriz"),
]

DEBUT = date(2026, 6, 1)
FIN = date(2026, 11, 9)  # veille de "aujourd'hui" : il reste des emprunts en cours et en retard


def construire_catalogue(m):
    n = 0
    def prochain_id():
        nonlocal n
        n += 1
        return f"D{n:03d}"
    for titre, annee, auteur in LIVRES:
        m.ajouter_document(Livre(prochain_id(), titre, annee, auteur))
    for titre, annee, duree in DVDS:
        m.ajouter_document(DVD(prochain_id(), titre, annee, duree))
    for titre, annee, numeros in REVUES:
        for numero in numeros:
            m.ajouter_document(Revue(prochain_id(), titre, annee, numero))


def construire_adherents(m, rng):
    for i, (nom, prenom) in enumerate(ADHERENTS, start=1):
        m.ajouter_adherent(Adherent(f"A{i:03d}", nom, prenom,
                                    "premium" if rng.random() < 0.25 else "standard"))


def simuler(m, rng):
    adherents = [a.numero for a in m.adherents]
    documents = [d.id for d in m]
    # quelques "gros lecteurs" et des documents plus demandes que d'autres
    activite = {a: rng.choice([0.03, 0.06, 0.06, 0.10, 0.18]) for a in adherents}
    popularite = {d: rng.choice([1, 1, 1, 2, 3, 6]) for d in documents}
    # retard "naturel" de chaque adherent : la plupart rendent a temps
    retardataire = {a: rng.random() < 0.2 for a in adherents}

    marges = {}  # (document, date d'emprunt) -> jours de retard prevus pour ce pret

    jour = DEBUT
    while jour <= FIN:
        m.actualiser_reservations(jour)
        # retours : souvent en avance, parfois pile a la date, les retardataires bien apres
        for e in list(m.emprunts):
            if not e.en_cours:
                continue
            cle = (e.id_document, e.date_emprunt)
            if cle not in marges:
                marges[cle] = (rng.choice([3, 8, 15, 30, 60])
                               if retardataire[e.numero_adherent] else rng.choice([-10, -5, -2, 0, 0]))
            limite = e.date_limite(m[e.id_document].duree_pret_jour)
            if jour > e.date_emprunt and (jour >= limite + timedelta(days=marges[cle])
                                          or rng.random() < 0.02):
                m.retourner(e.id_document, jour)
        # nouveaux emprunts et reservations (pas le dimanche : mediatheque fermee)
        if jour.weekday() != 6:
            for a in adherents:
                if rng.random() >= activite[a]:
                    continue
                cible = rng.choices(documents, weights=[popularite[d] for d in documents])[0]
                try:
                    if m.disponible(cible, a):
                        m.emprunter(cible, a, jour)
                    elif rng.random() < 0.5:
                        m.reserver(cible, a, jour)
                except MediathequeError:
                    pass  # quota atteint, deja reserve... comme dans la vraie vie
                # un reservant vient chercher son document mis de cote
            for r in m.reservations:
                if r.statut == "disponible" and rng.random() < 0.6:
                    try:
                        m.emprunter(r.id_document, r.numero_adherent, jour)
                    except MediathequeError:
                        pass
        jour += timedelta(days=1)
    m.actualiser_reservations(FIN)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("dossier", nargs="?", default="data_demo")
    parser.add_argument("--graine", type=int, default=42)
    args = parser.parse_args()

    rng = random.Random(args.graine)
    m = Mediatheque()
    construire_catalogue(m)
    construire_adherents(m, rng)
    simuler(m, rng)
    m.sauvegarder(Path(args.dossier))

    # relecture : prouve que le jeu passe tous les controles de coherence
    m2 = Mediatheque.charger(args.dossier)
    en_cours = [e for e in m2.emprunts if e.en_cours]
    en_retard = [e for e in en_cours
                 if e.jours_retard(m2[e.id_document].duree_pret_jour, FIN + timedelta(days=1))]
    actives = [r for r in m2.reservations if r.active]
    print(f"{args.dossier}/ : {len(m2)} documents, {len(m2.adherents)} adherents, "
          f"{len(m2.emprunts)} emprunts ({len(en_cours)} en cours, {len(en_retard)} en retard), "
          f"{len(m2.reservations)} reservations ({len(actives)} actives)")


if __name__ == "__main__":
    main()
