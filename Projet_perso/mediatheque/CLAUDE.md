# Médiathèque : consignes de travail

- Plan de référence : `docs/RAPPORT_SITUATION.md` (priorités P0 → P3).
- Code dans `src/mediatheque/`, tests dans `tests/`. Lancer les tests : `uv run pytest -q`.
- La logique métier reste dans `Mediatheque` et `auth`. L'interface graphique ne fait qu'appeler ces modules.
- Ne jamais modifier `data/` pendant les tests ou les démos : travailler sur une copie.

## Commits réguliers
- **Un commit par étape terminée** du plan (petits commits, jamais plusieurs fonctionnalités mélangées).
- Lancer les tests avant de committer, et ne pas committer si un test échoue.
- Format des messages : `type(portée): message` en français. Types possibles : `feat`, `fix`, `test`, `refactor`, `docs`, `chore`.
- Ne committer que les fichiers de `Projet_perso/mediatheque/`. Ne jamais pousser sans que l'utilisateur le demande.

## Sécurité
- Lancer l'agent `security-tester` à la fin de chaque palier (P1, P2) et avant toute démo.
- Mots de passe hachés (scrypt/pbkdf2 avec sel), SQL paramétré, contrôle des rôles dans la couche métier.
