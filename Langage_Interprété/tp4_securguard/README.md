# tp4-securguard

Boîte à outils en ligne de commande (CLI) dédiée à la **sécurité des mots de passe**.
Développée dans le cadre du TP4 — *Gestionnaires de paquets (uv) et outils CLI avec argparse* (ISEN, 1ère année Cycle Ingénieur).

L'application `secuguard` permet :

1. De **générer** un mot de passe sécurisé et personnalisable (longueur, chiffres, symboles).
2. D'**analyser** la robustesse d'un mot de passe existant et d'afficher un diagnostic coloré dans le terminal.

---

## Prérequis

- **Python** ≥ 3.14
- **uv** (gestionnaire de paquets et d'environnements)

Aucune installation manuelle de Python n'est nécessaire : `uv` peut gérer lui-même
l'interpréteur et l'environnement virtuel du projet.

---

## Installation de `uv`

### Linux / macOS

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Windows (PowerShell)

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Après l'installation, **fermer puis rouvrir le terminal**, puis vérifier :

```bash
uv --version
```

### Alternative via pip

```bash
pip install uv
```

---

## Installation du projet

Depuis la racine du projet (`tp4_securguard/`) :

```bash
# 1. Se placer dans le dossier du projet
cd tp4_securguard

# 2. Créer l'environnement virtuel et installer les dépendances
uv sync
```

Cette commande :

- lit `pyproject.toml` et `uv.lock`,
- crée un environnement virtuel isolé dans `.venv/`,
- installe la dépendance `colorama` (et toutes les autres déclarées).

Pour ajouter une nouvelle dépendance au projet :

```bash
uv add <nom_du_paquet>
```

Exemple utilisé dans ce TP :

```bash
uv add colorama
```

---

## Structure du projet

```
tp4_securguard/
├── pyproject.toml          # Métadonnées et dépendances du projet
├── uv.lock                 # Versions verrouillées des dépendances
├── README.md               # Ce fichier
└── src/
    └── secuguard/
        ├── __init__.py     # Marqueur de package
        ├── generator.py    # Génération de mots de passe
        ├── analyzer.py     # Analyse et coloration (colorama)
        └── main.py         # Interface CLI (argparse)
```

---

## Lancement

Toutes les commandes se lancent **depuis la racine du projet**, avec `uv run`,
qui garantit l'exécution dans l'environnement isolé.

### 1. Génération par défaut (longueur 12, chiffres + symboles)

```bash
uv run python -m secuguard.main
```

Sortie attendue :

```
Mot de passe genere : aK9#mP2!xL8q
```

### 2. Génération personnalisée (longueur 16, sans symboles)

```bash
uv run python -m secuguard.main -l 16 --no-symbols
```

Sortie attendue :

```
Mot de passe genere : F8k92A7x1M9p4L0z
```

### 3. Analyse d'un mot de passe faible

```bash
uv run python -m secuguard.main -c "12345"
```

Sortie attendue (en rouge) :

```
[FAIBLE] Mot de passe trop court et prévisible.
```

### 4. Analyse d'un mot de passe fort

```bash
uv run python -m secuguard.main --check "P@ssw0rd2026!Secu"
```

Sortie attendue (en vert) :

```
[FORT] Mot de passe tres solide.
```

---

## Options de la CLI

| Option | Description | Défaut |
|---|---|---|
| `-c`, `--check <MOT_DE_PASSE>` | Analyser le mot de passe fourni | *(non spécifié)* |
| `-l`, `--length <N>` | Longueur du mot de passe à générer | `12` |
| `--no-digits` | Exclure les chiffres du générateur | chiffres inclus |
| `--no-symbols` | Exclure les symboles du générateur | symboles inclus |
| `-h`, `--help` | Afficher l'aide | — |

### Aide intégrée

```bash
uv run python -m secuguard.main --help
```

---

## Niveaux de robustesse (analyseur)

| Niveau | Condition | Couleur |
|---|---|---|
| **FORT** | longueur ≥ 12 **et** lettres **et** chiffres **et** symboles | 🟢 Vert |
| **MOYEN** | longueur ≥ 8 **et** au moins 2 types de caractères | 🟡 Jaune |
| **FAIBLE** | tous les autres cas | 🔴 Rouge |

---

## Dépannage

### `uv : commande introuvable`

L'installateur n'a pas mis à jour le `PATH` de la session courante.
**Fermer et rouvrir le terminal**, puis retester :

```bash
uv --version
```

Si le problème persiste, ajouter manuellement `%USERPROFILE%\.local\bin` (Windows)
ou `$HOME/.local/bin` (Linux/macOS) au `PATH`.

### `error: Expected a Python module at: src\secuguard\__init__.py`

Le fichier `src/secuguard/__init__.py` est manquant. Le créer :

```powershell
New-Item -ItemType File -Path "src\secuguard\__init__.py" -Force
```

Puis relancer `uv sync`.

### `ModuleNotFoundError: No module named 'secuguard'`

Vérifier que le bloc suivant est présent dans `pyproject.toml` :

```toml
[tool.uv.build-backend]
module-name = "secuguard"
module-root = "src"
```

Puis relancer :

```bash
uv sync
```

### Les couleurs ne s'affichent pas

`colorama` gère l'affichage ANSI, y compris sous Windows.
S'assurer que `init(autoreset=True)` est bien appelé en haut de `analyzer.py` :

```python
from colorama import Fore, Style, init

init(autoreset=True)
```

---

## Dépendances

- [colorama](https://pypi.org/project/colorama/) — coloration des sorties terminal.
- [uv](https://docs.astral.sh/uv/) — gestionnaire de paquets et d'environnements.

---

## Auteur

Raffaele FARVACQUE — 1ère année Cycle Ingénieur ISEN