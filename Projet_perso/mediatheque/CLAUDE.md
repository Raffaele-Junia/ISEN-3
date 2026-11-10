# Médiathèque : mémoire du projet

Projet perso (ISEN 3) de Raffaele : système de gestion de médiathèque en Python.
**Objectif en cours :** une interface graphique avec comptes adhérents, catalogue, réservations à l'avance et un accès admin (responsable).
Plan détaillé et priorités : `docs/RAPPORT_SITUATION.md`. **Mettre à jour la section « Avancement » ci-dessous à chaque palier terminé.**

## Stack
- Python **3.14**, paquet géré par **uv** (`uv_build`), disposition `src/`. Aucune dépendance d'exécution.
- Dépendance de dev : `pytest`. Lancer les tests : `uv run pytest -q`.
- Lancer la démo : `uv run mediatheque` (ou `uv run python -m mediatheque.main`).
- Ce dossier est un sous-dossier du dépôt git `ISEN-3`. La racine git est deux niveaux au-dessus.

## Carte du code (`src/mediatheque/`)
| Fichier | Contenu clé |
|---|---|
| `documents.py` | `Document(ABC)` : attributs `id, titre, annee, _extra`. Registre auto `Document._registre[CLE]` via `__init_subclass__`. Abstraits : `duree_pret_jour`, `detail`, `from_extra()`. `from_csv_row` choisit la sous-classe selon `row["type"]`. `__eq__`/`__hash__` sur l'id, `__lt__` sur le titre. Sous-classes : `Livre` (clé `livre`, extra = auteur, 21 jours), `DVD` (`dvd`, extra = durée en minutes, 7 jours), `Revue` (`revue`, extra = numéro, 7 jours). |
| `adherents.py` | `Adherent(numero, nom, prenom, type)`. Numéro au format `A\d{3}`, type `standard` (quota 3) ou `premium` (quota 6). Propriétés `quota` et `nom_complet`. |
| `emprunt.py` | `@dataclass Emprunt(id_document, numero_adherent, date_emprunt, date_retour=None)`. Fournit `en_cours`, `date_limite(duree)` et `jours_retard(duree, aujourdhui)`. |
| `mediatheque.py` | Façade `Mediatheque` : `charger(dossier)` (méthode de classe), `sauvegarder()`, `disponible(id)`, `emprunter(id, numero, date)`, `retourner(id, date)`, `rechercher(critere)`. Supporte `len`, `in`, `[]`, l'itération sur les documents, et `with` (sauvegarde en sortie s'il n'y a pas d'exception). |
| `stockage.py` | `lire_*` / `ecrire_*` pour les CSV (documents, adhérents, emprunts) en UTF-8. |
| `rapports.py` | Filtres `par_auteur`, `parue_apres`, `du_type` (fermetures). `retards(m, date)` est un générateur de `(emprunt, doc, jours)`. Aussi `top_emprunteurs(m, n)` et `export_retards_csv`. |
| `exceptions.py` | `MediathequeError`, dont héritent `DocumentInconnuError`, `AdherentInconnuError`, `DocumentIndisponibleError` et `QuotaDepasseError`. |
| `main.py` | Scénario de démo en console, sur une **copie temporaire** de `data/`. |

## Données (`data/*.csv`)
- `documents.csv` : `id,type,titre,annee,extra`
- `adherents.csv` : `numero,nom,prenom,type`
- `emprunts.csv` : `id_document,numero_adherent,date_emprunt,date_retour` (vide = emprunt en cours)

## Règles métier
- Un document ne peut être emprunté qu'une seule fois à la fois. Un adhérent ne peut pas dépasser son quota d'emprunts en cours.
- Durée de prêt : 21 jours pour un livre, 7 jours pour un DVD ou une revue. Le retard se compte en jours après la date limite.

## Architecture cible (P1–P2)
- SQLite à la place des CSV, en gardant la même interface de `stockage`. `auth.py` gère les comptes (hachage scrypt ou pbkdf2 avec sel) et les rôles `adherent` / `responsable`.
- `Reservation` : file d'attente par document, réservable uniquement si le document est emprunté.
- Interface **Tkinter/ttk** : écran de connexion, puis espace adhérent ou espace responsable. **Aucune logique métier dans les vues**, et le contrôle des rôles se fait dans la couche métier.

## Avancement
- [x] Système de base (modèle, CSV, rapports, démo console)
- [x] Rapport de situation et plan, agent `security-tester`, `.gitignore`
- [x] P0 : bugs B1–B4 corrigés, tests pytest de base
- [ ] P1 : SQLite, comptes et rôles, réservations
- [ ] P2 : interface graphique
- [ ] P3 : README, journalisation, audit final

## Règles de travail
- Ne jamais modifier `data/` pendant les tests ou les démos : utiliser `tmp_path` ou une copie.
- **Commits réguliers :** un commit par étape terminée, après avoir lancé les tests. Format `type(portée): message` en français, avec les types `feat`, `fix`, `test`, `refactor`, `docs`, `chore`. Ne committer que les fichiers de ce dossier, et ne jamais pousser sans demande.
- **Sécurité :** lancer l'agent `security-tester` à la fin de P1, à la fin de P2 et avant toute démo. SQL toujours paramétré.
