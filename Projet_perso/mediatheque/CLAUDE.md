# Médiathèque : mémoire du projet

Projet perso (ISEN 3) de Raffaele : système de gestion de médiathèque en Python.
**Objectif en cours :** une interface graphique avec comptes adhérents, catalogue, réservations à l'avance et un accès admin (responsable).
Plan détaillé et priorités : `docs/RAPPORT_SITUATION.md`. **Mettre à jour la section « Avancement » ci-dessous à chaque palier terminé.**

## Stack
- Python **3.14**, paquet géré par **uv** (`uv_build`), disposition `src/`. Aucune dépendance d'exécution.
- Dépendance de dev : `pytest`. Lancer les tests : `uv run --system-certs pytest -q -p no:cacheprovider`. Sur ce réseau, uv a besoin de `--system-certs`, et OneDrive bloque le cache de pytest, d'où `-p no:cacheprovider`.
- Lancer la démo console : `uv run mediatheque` (elle travaille sur une copie temporaire de `data/`).
- Créer la base : `uv run mediatheque-init --depuis data --db mediatheque.db --admin admin`. Le mot de passe est demandé au clavier, et les fichiers `*.db` sont ignorés par git.
- Ce dossier est un sous-dossier du dépôt git `ISEN-3`. La racine git est deux niveaux au-dessus.

## Carte du code (`src/mediatheque/`)
| Fichier | Contenu clé |
|---|---|
| `documents.py` | `Document(ABC)` : attributs `id, titre, annee, _extra`. Registre auto `Document._registre[CLE]` via `__init_subclass__`. Abstraits : `duree_pret_jour`, `detail`, `from_extra()`. `from_csv_row` choisit la sous-classe selon `row["type"]`. `__eq__`/`__hash__` sur l'id, `__lt__` sur le titre. Sous-classes : `Livre` (clé `livre`, extra = auteur, 21 jours), `DVD` (`dvd`, extra = durée en minutes, 7 jours), `Revue` (`revue`, extra = numéro, 7 jours). |
| `adherents.py` | `Adherent(numero, nom, prenom, type)`. Numéro au format `A\d{3}`, type `standard` (quota 3) ou `premium` (quota 6). Propriétés `quota` et `nom_complet`. |
| `emprunt.py` | `@dataclass Emprunt(id_document, numero_adherent, date_emprunt, date_retour=None)`. Fournit `en_cours`, `date_limite(duree)` et `jours_retard(duree, aujourdhui)`. |
| `mediatheque.py` | Moteur métier `Mediatheque`, **sans contrôle d'accès**. `charger(source)` / `sauvegarder()` acceptent un fichier `.db` (SQLite) ou un dossier CSV. Méthodes : `disponible(id, numero=None)` (un document mis de côté n'est disponible que pour son réservant), `emprunter`, `retourner` (met le document de côté pour le premier de la file), `reserver`, `annuler_reservation`, `actualiser_reservations(jour)` (expirations), `file_attente`, `emprunts_de`, `reservations_de`, `adherent(numero)`, `creer_compte`, `supprimer_document` (refusée s'il existe un historique). Les doublons et les références orphelines sont refusés. L'attribut `comptes` est un `GestionComptes`. |
| `reservation.py` | `@dataclass Reservation(id_document, numero_adherent, date_reservation, statut, date_disponible)`. Statuts : `en_attente`, `disponible` (mis de côté), `honoree`, `annulee`, `expiree`. Constantes `DELAI_RETRAIT_JOURS=3` et `MAX_RESERVATIONS=3`. |
| `auth.py` | `Compte(identifiant, hash_mdp, sel, role, numero_adherent)`. Rôles `adherent` et `responsable`. `GestionComptes` : `creer` (scrypt avec sel, politique de mot de passe), `authentifier` (temps constant, message unique, délai progressif 1, 2, 4… s plafonné à 60 s après 5 échecs ; scrypt N=2**17, paramètres encodés dans le hash, anciens hashes re-hachés à la connexion), `changer_mot_de_passe`, `reinitialiser_mot_de_passe`. |
| `session.py` | **Seule porte d'entrée de l'interface.** `ouvrir_session(m, id, mdp)` renvoie une `Session`. Décorateurs `@connexion_requise` et `@responsable_requis`. Partie adhérent : `catalogue(texte, type_doc)` (liste de couples `(doc, statut)`), `mon_compte()`, `reserver`, `annuler_reservation`, `changer_mot_de_passe`. Partie responsable : `ajouter_document`, `supprimer_document`, `adherents`, `ajouter_adherent`, `creer_compte`, `reinitialiser_mot_de_passe`, `enregistrer_emprunt`, `enregistrer_retour`, `retards`, `statistiques`, `sauvegarder`. Un adhérent n'agit que sur son propre numéro. Un test vérifie que toute méthode publique est bien décorée. |
| `stockage.py` | `lire_*` / `ecrire_*` pour les CSV en UTF-8. `reservations.csv` est optionnel. Les comptes ne sont jamais écrits en CSV. |
| `stockage_sqlite.py` | Tables `documents`, `adherents`, `emprunts`, `reservations` et `comptes`. Clés étrangères et contraintes CHECK, SQL toujours paramétré, sauvegarde complète dans une seule transaction. |
| `init_db.py` | Commande `mediatheque-init` : importe les CSV dans une base SQLite et crée le compte responsable. Refuse d'écraser une base existante. |
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
- Réservation : possible seulement si le document est emprunté (ou mis de côté pour quelqu'un d'autre), au maximum 3 actives par adhérent, et jamais sur son propre emprunt. Au retour du document, le premier de la file l'a de côté pendant 3 jours. Ensuite sa réservation expire et le suivant prend la main.
- Seul le responsable enregistre les emprunts et les retours (au guichet). L'adhérent consulte le catalogue et son compte, et réserve ou annule ses réservations.

## Architecture cible (P2)
- Interface **Tkinter/ttk** : écran de connexion, puis espace adhérent ou espace responsable.
- Les vues n'appellent **que** `Session`. Aucune logique métier dans les vues, et jamais d'accès à `session._m`.

## Avancement
- [x] Système de base (modèle, CSV, rapports, démo console)
- [x] Rapport de situation et plan, agent `security-tester`, `.gitignore`
- [x] P0 : bugs B1–B4 corrigés, tests pytest de base
- [x] P1 : SQLite, comptes et rôles, réservations, `mediatheque-init` (81 tests). Audit de sécurité : voir `docs/securite/` (S1–S7 corrigées).
- [ ] P2 : interface graphique
- [ ] P3 : README, journalisation, audit final

## Règles de travail
- Ne jamais modifier `data/` pendant les tests ou les démos : utiliser `tmp_path` ou une copie.
- **Commits réguliers :** un commit par étape terminée, après avoir lancé les tests. Format `type(portée): message` en français, avec les types `feat`, `fix`, `test`, `refactor`, `docs`, `chore`. Ne committer que les fichiers de ce dossier, et ne jamais pousser sans demande.
- **Sécurité :** lancer l'agent `security-tester` à la fin de P1, à la fin de P2 et avant toute démo. SQL toujours paramétré.
