# Médiathèque : rapport de situation et plan de priorités

*État au 10/11/2026, version 0.1.0*

> **Avancement :** P0 terminé (bugs B1 à B4 et B7 corrigés). P1 terminé (SQLite, comptes et rôles, réservations ; B5 corrigé). Décisions prises : les réservations ont leur propre limite (3 actives), séparée du quota d'emprunts, et un document reste mis de côté 3 jours. Prochaine étape : P2 (interface graphique).

## 1. Ce qui existe

| Module | Rôle | État |
|---|---|---|
| `documents.py` | Hiérarchie `Document` (abstraite) → `Livre`, `DVD`, `Revue`, avec un registre automatique (`__init_subclass__`) | Solide, mais 1 bug sur `DVD` |
| `adherents.py` | `Adherent` (numéro `A###`, type standard/premium, quota 3/6) | Correct |
| `emprunt.py` | `Emprunt` en dataclass : date limite, jours de retard | Correct |
| `mediatheque.py` | Façade métier : charger/sauvegarder, emprunter, retourner, rechercher, gestionnaire de contexte | Correct, mais sans aucun contrôle d'accès |
| `stockage.py` | Lecture et écriture des CSV | Fonctionnel, mais fragile |
| `rapports.py` | Filtres (fermetures), retards (générateur), top emprunteurs, export CSV | Correct |
| `exceptions.py` | Hiérarchie d'erreurs métier | Bonne base |
| `main.py` | Scénario de démonstration en console | Script de démo seulement |

**Points forts :** l'architecture objet est propre (ABC, propriétés, dataclass, dunder methods), les erreurs métier sont typées et la logique est bien séparée du stockage. C'est une bonne base pour ajouter une interface graphique par-dessus.

**Ce qui manque pour le projet visé :** une interface graphique, des comptes et une authentification, des rôles (adhérent ou responsable), les réservations, des tests, un README.

## 2. Bugs et défauts constatés

| # | Gravité | Problème | Où |
|---|---|---|---|
| B1 | Haute | `DVD.duree_min` n'est pas une `@property` : l'affichage donne `<bound method DVD.duree_min ...> min` (vérifié) | `documents.py:108` |
| B2 | Haute | La commande `mediatheque` (le point d'entrée de `pyproject.toml`) lance `__init__.main()`, qui affiche seulement « Hello from mediatheque! ». Le vrai `main` se trouve dans `main.py` | `__init__.py`, `pyproject.toml` |
| B3 | Moyenne | `lire_*` ouvrent les fichiers sans `encoding="utf-8"` alors que l'écriture se fait en UTF-8. Sous Windows (cp1252), un accent casse la relecture | `stockage.py` |
| B4 | Moyenne | `main.py` écrit dans les vraies données (`data/`) à chaque exécution, ce qui ajoute des emprunts à chaque lancement | `main.py` |
| B5 | Moyenne | Aucune cohérence vérifiée au chargement : un emprunt vers un document ou un adhérent inexistant provoque un `KeyError` dans `retards()`, et un ID en double écrase le précédent sans prévenir | `mediatheque.py`, `rapports.py` |
| B6 | Basse | Pas de validation des IDs de documents (`D###`), ni des années, ni d'une date d'emprunt dans le futur | `documents.py`, `mediatheque.py` |
| B7 | Basse | Les fichiers `__pycache__/*.pyc` sont versionnés dans git et il n'y a pas de `.gitignore` | dépôt |
| B8 | Basse | `README.md` vide, description par défaut dans `pyproject.toml` | — |

## 3. Risques de sécurité (à surveiller dès l'ajout de l'interface)

- **Pas d'authentification ni de rôles** : aujourd'hui, n'importe quel code peut tout faire. L'accès « responsable » devra être protégé côté logique métier, pas seulement masqué dans l'interface.
- **Mots de passe** : il ne faudra jamais les stocker en clair dans un CSV. Utiliser un hachage lent (`hashlib.scrypt` ou `pbkdf2_hmac` avec un sel).
- **Injection de formules CSV** : un nom saisi comme `=HYPERLINK(...)` sera exécuté à l'ouverture dans Excel. Il faut neutraliser `= + - @` en début de champ lors de l'export.
- **Écritures concurrentes et corruption** : la sauvegarde réécrit les fichiers directement. Il vaut mieux écrire dans un fichier temporaire puis le renommer (écriture atomique), ou passer à SQLite.
- **Chemins** : `sauvegarder(dossier)` et `export_retards_csv(chemin)` acceptent n'importe quel chemin. Ce n'est pas exploitable tant que l'interface ne laisse pas l'utilisateur choisir le chemin.

## 4. Plan de priorités

### P0 : assainir la base (½ journée)
1. Corriger B1 (DVD), B2 (point d'entrée) et B3 (encodage).
2. Ajouter un `.gitignore` et retirer les `.pyc` du dépôt (B7).
3. Ajouter **pytest** et les premiers tests : emprunt OK, quota dépassé, document indisponible, retour, retards, aller-retour CSV.
4. Isoler la démo : `main.py` travaille sur une copie des données ou n'appelle pas `sauvegarder`.

### P1 : modèle de données pour les nouvelles fonctionnalités (1 à 2 jours)
5. **Passer de CSV à SQLite** (module `sqlite3` de la bibliothèque standard). Cela apporte les transactions, l'intégrité référentielle et l'absence de corruption, ce qui est indispensable dès qu'il y a des comptes et des réservations. Garder `stockage.py` comme couche d'accès (même interface).
6. **Comptes et rôles** : table `comptes(identifiant, hash_mdp, sel, role ∈ {adherent, responsable}, numero_adherent)`, module `auth.py` (`creer_compte`, `verifier`, `exiger_role`).
7. **Réservations** : dataclass `Reservation(id_document, numero_adherent, date_reservation, statut)` avec une file d'attente par document. Règles :
   - on ne peut réserver qu'un document actuellement emprunté ;
   - au retour, le document est bloqué pour le premier réservant pendant N jours ;
   - les réservations comptent dans le quota, ou ont une limite séparée (à décider) ;
   - il faut pouvoir annuler une réservation.
8. Tests pour tout P1, en particulier les règles de réservation et les contrôles de rôle.

### P2 : interface graphique (2 à 4 jours)
Choix recommandé : **Tkinter + ttk**, inclus dans Python, sans dépendance, suffisant pour un projet ISEN. Alternative plus moderne : **PySide6** (Qt), plus jolie mais plus lourde.
9. Écran de **connexion**, avec redirection selon le rôle.
10. **Espace adhérent** : mon compte (emprunts en cours, dates limites, retards, réservations, quota restant), catalogue (liste filtrable par type, titre, auteur et année, avec la disponibilité), bouton « Réserver ».
11. **Espace responsable** : gestion du catalogue (CRUD documents), gestion des adhérents, enregistrer un emprunt ou un retour, tableau des retards, export CSV, statistiques (top emprunteurs).
12. Architecture : l'interface appelle **uniquement** `Mediatheque` et `auth`, sans aucune logique métier dans les vues.

### P3 : finitions
13. README (installation avec `uv`, lancement, captures d'écran), journalisation des actions du responsable, sauvegarde automatique.
14. Audit de sécurité complet par l'agent `security-tester` après P1 et après P2.

## 5. Méthode de travail
- Un commit par étape du plan, au format `type(portée): message` (`fix`, `feat`, `test`, `refactor`, `docs`, `chore`).
- Lancer les tests avant chaque commit.
- Lancer l'agent `security-tester` à la fin de chaque palier (P1, P2).
