## Fonctionnalités

- Recherche de véhicules par marque, modèle et année
- Consultation des caractéristiques techniques
- Comparaison de deux véhicules
- Consultation des rappels constructeur
- Recherche de codes de diagnostic OBD-II

## Prérequis

Avant de commencer, installez :

- [Python](https://www.python.org/downloads/)
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- Une clé API [CarVector](https://api.carvector.io/docs/api)
- Git (facultatif, si vous clonez le dépôt)

## Installation

### 1. Récupérer le projet

Si vous utilisez Git :

```bash
git clone https://github.com/Raffaele-Junia/ISEN-3/tree/main/Langage_Interpr%C3%A9t%C3%A9/mon_projet
cd mon_projet
```

Remplacez `https://github.com/Raffaele-Junia/ISEN-3/tree/main/Langage_Interpr%C3%A9t%C3%A9/mon_projet` par l'adresse réelle du dépôt Git.

Vous pouvez aussi télécharger le projet et ouvrir un terminal dans son dossier.

### 2. Installer les dépendances

À la racine du projet, là où se trouve `pyproject.toml`, exécutez :

```bash
uv sync
```

### 3. Configurer la clé API

Au premier lancement, AutoScope peut demander votre clé API si elle n'est pas configurée.

Vous pouvez également créer manuellement un fichier `.env` à la racine du projet, au même niveau que `pyproject.toml` :

```dotenv
CARVECTOR_API_KEY=cv_votre_cle_api
```

Remplacez `cv_votre_cle_api` par votre véritable clé CarVector.

**Sécurité :** ne publiez jamais votre fichier `.env` ni votre clé API sur GitHub. Le fichier `.env` est normalement exclu du suivi Git grâce au `.gitignore`.

## Utilisation

Toutes les commandes suivantes doivent être exécutées depuis la racine du projet.

### 1. Rechercher des véhicules

Rechercher toutes les Ford :

```bash
uv run python -m mon_projet.main search --make Ford
```

Rechercher une Ford Mustang :

```bash
uv run python -m mon_projet.main search --make Ford --model Mustang
```

Rechercher les Ford de 2020 :

```bash
uv run python -m mon_projet.main search --make Ford --year 2020
```

Rechercher les Ford Mustang de 2020 :

```bash
uv run python -m mon_projet.main search --make Ford --model Mustang --year 2020
```

Rechercher une BMW M3 :

```bash
uv run python -m mon_projet.main search --make BMW --model M3
```

### 2. Consulter les détails d'un véhicule

La recherche affiche un identifiant pour chaque résultat. Utilisez cet identifiant dans la commande suivante :

```bash
uv run python -m mon_projet.main details IDENTIFIANT
```

Exemple avec un identifiant obtenu lors d'une recherche :

```bash
uv run python -m mon_projet.main details c1gp1h7vkyuyypo
```

Cet identifiant est un exemple issu d'une recherche précédente ; les identifiants disponibles peuvent varier.

### 3. Comparer deux véhicules

Récupérez deux identifiants grâce à une recherche, puis exécutez :

```bash
uv run python -m mon_projet.main compare IDENTIFIANT_1 IDENTIFIANT_2
```

Exemple :

```bash
uv run python -m mon_projet.main compare c1gp1h7vkyuyypo 1lx639qdiqp7pxe
```

La comparaison affiche les caractéristiques disponibles pour les deux véhicules, notamment la puissance, la cylindrée, la transmission et le carburant.

### 4. Consulter les rappels constructeur

```bash
uv run python -m mon_projet.main recalls IDENTIFIANT
```

Remplacez `IDENTIFIANT` par celui du véhicule recherché.

### 5. Rechercher un code de diagnostic OBD-II

Exemple avec le code `P0420` :

```bash
uv run python -m mon_projet.main dtc P0420
```

Les informations obtenues sont indicatives et ne remplacent pas un diagnostic réalisé par un professionnel.

## Scénario de test complet

Pour tester rapidement les principales fonctionnalités, exécutez ces commandes dans l'ordre :

```bash
# 1. Rechercher une Ford Mustang
uv run python -m mon_projet.main search --make Ford --model Mustang

# 2. Rechercher les Ford de 2020
uv run python -m mon_projet.main search --make Ford --year 2020

# 3. Consulter un véhicule
uv run python -m mon_projet.main details IDENTIFIANT

# 4. Comparer deux véhicules
uv run python -m mon_projet.main compare IDENTIFIANT_1 IDENTIFIANT_2

# 5. Consulter les rappels d'un véhicule
uv run python -m mon_projet.main recalls IDENTIFIANT

# 6. Rechercher un code OBD-II
uv run python -m mon_projet.main dtc P0420
```

Pour les commandes 3 à 5, remplacez les identifiants par ceux obtenus lors de vos propres recherches.

## Dépannage

**Erreur : clé API manquante**

Vérifiez que le fichier `.env` se trouve à la racine du projet et contient la variable `CARVECTOR_API_KEY`.

**Erreur HTTP 401**

Vérifiez que votre clé API est valide et correctement renseignée.

**Erreur HTTP 429**

La limite de requêtes de l'API a peut-être été atteinte. Consultez les conditions de votre offre CarVector.

**Module `mon_projet` introuvable**

Vérifiez que vous êtes dans le dossier contenant `pyproject.toml`, puis exécutez :

```bash
uv sync
```

Vérifiez également que le package est correctement configuré dans `pyproject.toml`.

**Aucun véhicule trouvé**

Essayez une recherche plus générale, sans année ni modèle, ou vérifiez les paramètres utilisés.

## Technologies utilisées

- Python
- uv
- Requests
- python-dotenv
- API CarVector

## Licence

Précisez ici la licence de votre choix avant de publier le projet.

## Avertissement

AutoScope est un projet d'exploration de données automobiles. Les données dépendent de l'API CarVector et de ses disponibilités. Les informations de rappel et de diagnostic ne remplacent pas les informations officielles du constructeur ni l'avis d'un professionnel.
