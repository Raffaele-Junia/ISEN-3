# Médiathèque : mémoire du projet

Projet perso (ISEN 3) de Raffaele : système de gestion de médiathèque en Python.
**Objectif en cours :** un **site web** (Flask) avec comptes adhérents, catalogue, réservations à l'avance et un accès admin (responsable). Tkinter a été écarté, jugé trop daté.
Maquettes Claude Design de référence : https://claude.ai/artifact/UkHAJYLgKGwd6b9WyRq2pK (connexion, catalogue, mon compte, tableau de bord, gestion).
Plan détaillé et priorités : `docs/RAPPORT_SITUATION.md`. **Mettre à jour la section « Avancement » ci-dessous à chaque palier terminé.**

## Stack
- Python **3.14**, paquet géré par **uv** (`uv_build`), disposition `src/`. Seule dépendance d'exécution : **Flask**.
- Lancer le site : `uv run --system-certs python -m mediatheque.web.app --db mediatheque.db` (http://127.0.0.1:5000). Utiliser `python -m`, car les lanceurs `.exe` de uv (`mediatheque-web`, `mediatheque`) se bloquent sur ce poste.
- Base de démonstration avec comptes de test : `uv run python scripts/creer_demo.py demo.db`. Elle part de `data_demo/` et crée un compte `prenom.nom` par adhérent, plus `admin` (mots de passe dans la docstring du script). Compter environ 25 s.
- Régénérer `data_demo/` : `uv run python scripts/generer_donnees.py [--graine 42]`.
- Le serveur de prévisualisation de Claude est configuré dans `../../.claude/launch.json` (racine du dépôt).
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
| `mediatheque.py` | Moteur métier `Mediatheque`, **sans contrôle d'accès**. `charger(source)` / `sauvegarder()` acceptent un fichier `.db` (SQLite) ou un dossier CSV. `recharger()` relit la source **en place** (les sessions ouvertes gardent le même objet ; les comptes inchangés gardent leur identité). Méthodes : `disponible(id, numero=None)` (un document mis de côté n'est disponible que pour son réservant), `emprunter`, `retourner` (met le document de côté pour le premier de la file), `reserver`, `annuler_reservation`, `actualiser_reservations(jour)` (expirations), `file_attente`, `emprunts_de`, `reservations_de`, `adherent(numero)`, `creer_compte`, `supprimer_document` (refusée s'il existe un historique). Les doublons et les références orphelines sont refusés. L'attribut `comptes` est un `GestionComptes`. |
| `reservation.py` | `@dataclass Reservation(id_document, numero_adherent, date_reservation, statut, date_disponible)`. Statuts : `en_attente`, `disponible` (mis de côté), `honoree`, `annulee`, `expiree`. Constantes `DELAI_RETRAIT_JOURS=3` et `MAX_RESERVATIONS=3`. |
| `auth.py` | `Compte(identifiant, hash_mdp, sel, role, numero_adherent)`. Rôles `adherent` et `responsable`. `GestionComptes` : `creer` (scrypt avec sel, politique de mot de passe), `authentifier` (temps constant, avec un hash leurre tant qu'il reste des hashes anciens (W7), message unique, délai progressif 1, 2, 4… s plafonné à 60 s après 5 échecs ; scrypt N=2**17, paramètres encodés dans le hash, anciens hashes re-hachés à la connexion), `changer_mot_de_passe`, `reinitialiser_mot_de_passe`, `verifier_nouveau` (contrôles sans modifier), `synchroniser` (rechargement). Petit verrou interne pour le registre et les compteurs, jamais tenu pendant un hachage. |
| `session.py` | **Seule porte d'entrée de l'interface.** `ouvrir_session(m, id, mdp)` renvoie une `Session`, et il n'y a aucun autre moyen d'en créer une : `Session(m, compte)` lève une erreur (S4). La session est révoquée si son compte change dans le registre. Les objets renvoyés sont des copies, et seul le responsable peut passer `jour` ou `aujourdhui`. Décorateurs `@connexion_requise` et `@responsable_requis`. Partie adhérent : `catalogue(texte, type_doc)` (liste de couples `(doc, statut)`), `mon_compte()`, `reserver`, `annuler_reservation`, `changer_mot_de_passe`. Partie responsable : `ajouter_document`, `supprimer_document`, `adherents`, `ajouter_adherent` (avec `identifiant`/`mot_de_passe` facultatifs, validés avant toute modification), `creer_compte`, `reinitialiser_mot_de_passe`, `enregistrer_emprunt`, `enregistrer_retour`, `retards`, `statistiques`, `sauvegarder`. Un adhérent n'agit que sur son propre numéro. Un test vérifie que toute méthode publique est bien décorée. |
| `stockage.py` | `lire_*` / `ecrire_*` pour les CSV en UTF-8. `reservations.csv` est optionnel. Les comptes ne sont jamais écrits en CSV. |
| `stockage_sqlite.py` | Tables `documents`, `adherents`, `emprunts`, `reservations` et `comptes`. Clés étrangères et contraintes CHECK, SQL toujours paramétré, sauvegarde complète dans une seule transaction. |
| `init_db.py` | Commande `mediatheque-init` : importe les CSV dans une base SQLite et crée le compte responsable. Refuse d'écraser une base existante. |
| `rapports.py` | Filtres `par_auteur`, `parue_apres`, `du_type` (fermetures). `retards(m, date)` est un générateur de `(emprunt, doc, jours)`. Aussi `top_emprunteurs(m, n)` et `export_retards_csv`. |
| `exceptions.py` | `MediathequeError`, dont héritent `DocumentInconnuError`, `AdherentInconnuError`, `DocumentIndisponibleError` et `QuotaDepasseError`. |
| `main.py` | Scénario de démo en console, sur une **copie temporaire** de `data/`. |
| `web/app.py` | `create_app(db, ..., attente_hachage_s, tentatives_par_ip, fenetre_ip_s, inactivite_s, duree_max_s)` crée l'application Flask (durées et limites configurables pour les tests). Les sessions sont gardées **côté serveur** (`sessions_actives` : jeton → `Session`, `horodatage` : jeton → [créée, vue]) ; le cookie ne contient qu'un jeton signé. Expiration après 30 min d'inactivité ou 12 h (message « Session expirée, reconnectez-vous » sur `/connexion`) ; purge du registre à chaque connexion, 5 sessions au plus par compte. **Le hachage scrypt ne se fait jamais sous le verrou global** : `/connexion` et `/compte/mot-de-passe` hachent sous un `BoundedSemaphore(2)` (503 si saturé), et `LimiteParIP` limite à 10 échecs de connexion par minute et par adresse (429). Un jeton CSRF est exigé sur tout POST (`{{ jeton() }}`, comparé en octets). En-têtes : CSP `script-src 'none'` (aucun JavaScript sur le site), X-Frame-Options et nosniff. Décorateurs `connexion_requise` (prend `verrou` pour toute la vue, sauf `sous_verrou=False` réservé aux vues qui hachent), `responsable_requis` (403 sinon) et `action` (sauvegarde en base après chaque POST, erreur métier transformée en message ; en cas d'exception, `m.recharger()` remet la mémoire au contenu de la base, en place). Redirections internes seulement (`page_precedente`). Routes : `/connexion`, `/catalogue`, `/reserver/<id>`, `/annuler/<id>`, `/compte`, `/admin` (tableau de bord et guichet), `/admin/gestion`, `/admin/retards.csv`. |
| `web/templates/`, `web/static/style.css` | Templates Jinja (échappement automatique) et CSS. **Identité « Médiathèque des Tilleuls »** (nom modifiable avec `MEDIATHEQUE_NOM`), qui remplace le premier style des maquettes. Papier crème `#F3EDE2`, vert reliure `#1E4A38`, moutarde `#D9A21B`. Polices : Fraunces pour les titres, Instrument Sans pour le texte, Courier Prime pour les cotes et étiquettes. Catalogue en étagère de couvertures colorées (`teinte(doc)`, 8 couleurs), cote façon étiquette de dos (`cote(doc)` : `LIV HUG`), statuts en `.tampon`, fiche de prêt cartonnée. Filtres de date `court` et `long`. Textes chaleureux, sans emoji. Ne jamais animer l'opacité depuis 0. |

## Données (`data/*.csv`)
- `documents.csv` : `id,type,titre,annee,extra`
- `adherents.csv` : `numero,nom,prenom,type`
- `emprunts.csv` : `id_document,numero_adherent,date_emprunt,date_retour` (vide = emprunt en cours)

## Règles métier
- Un document ne peut être emprunté qu'une seule fois à la fois. Un adhérent ne peut pas dépasser son quota d'emprunts en cours.
- Durée de prêt : 21 jours pour un livre, 7 jours pour un DVD ou une revue. Le retard se compte en jours après la date limite.
- Réservation : possible seulement si le document est emprunté (ou mis de côté pour quelqu'un d'autre), au maximum 3 actives par adhérent, et jamais sur son propre emprunt. Au retour du document, le premier de la file l'a de côté pendant 3 jours. Ensuite sa réservation expire et le suivant prend la main.
- Seul le responsable enregistre les emprunts et les retours (au guichet). L'adhérent consulte le catalogue et son compte, et réserve ou annule ses réservations.

## Architecture web
- Les vues Flask n'appellent **que** `Session`. Aucune logique métier dans les vues, et jamais d'accès à `session._m`. Seules exceptions : la sauvegarde `m.sauvegarder()` et le rechargement `m.recharger()` après un échec (décorateur `action` et changement de mot de passe).
- Jamais de calcul scrypt sous `verrou` (vue de connexion ou `connexion_requise(sous_verrou=False)` + `emplacement_hachage()`). Exception assumée : les actions du responsable (création de compte, réinitialisation), qui restent atomiques sous le verrou.
- Tout nouveau formulaire POST doit contenir `{{ jeton() }}`. Tout nouvel écran du responsable passe par `@responsable_requis`.
- Pas de JavaScript : la CSP le bloque. Les interactions passent par des formulaires et des liens.

## Avancement
- [x] Système de base (modèle, CSV, rapports, démo console)
- [x] Rapport de situation et plan, agent `security-tester`, `.gitignore`
- [x] P0 : bugs B1–B4 corrigés, tests pytest de base
- [x] P1 : SQLite, comptes et rôles, réservations, `mediatheque-init` (81 tests). Audit de sécurité : voir `docs/securite/` (S1–S7 corrigées).
- [x] Agent `security-fixer` : S1–S7 corrigées (un commit par faille).
- [x] P2 : site web Flask d'après les maquettes Claude Design, vérifié dans le navigateur sur ordinateur et sur mobile. 181 tests au total.
- [x] Jeu de démo `data_demo/` : 136 documents et 45 adhérents, généré par `scripts/generer_donnees.py` (simulation déterministe de 5 mois d'activité). `data/` reste le petit jeu utilisé par les tests.
- [x] P2 bis : audit du site web, `docs/securite/AUDIT_2026-11-10_web.md`. Il trouve les failles W1–W7 (3 moyennes, 4 basses), prouvées par des tests dans `tests/security/test_securite_web*.py`.
- [x] Refonte visuelle « Médiathèque des Tilleuls » (rendu moins « IA »).
- [x] W1–W7 corrigées par l'agent `security-fixer` (un commit par faille, plus les redirections internes). 254 tests au total.
- [ ] P3 : README, journalisation, audit final

## Règles de travail
- Ne jamais modifier `data/` pendant les tests ou les démos : utiliser `tmp_path` ou une copie.
- **Commits réguliers :** un commit par étape terminée, après avoir lancé les tests. Format `type(portée): message` en français, avec les types `feat`, `fix`, `test`, `refactor`, `docs`, `chore`. Ne committer que les fichiers de ce dossier, et ne jamais pousser sans demande.
- **Sécurité :** lancer l'agent `security-tester` à la fin de P1, à la fin de P2 et avant toute démo. SQL toujours paramétré.
