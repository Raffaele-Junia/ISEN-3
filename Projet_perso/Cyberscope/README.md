# CyberScope

**Ce lien est-il sûr ?** Colle un lien reçu par SMS ou par e-mail : CyberScope
l'examine à ta place, sans l'ouvrir dans ton navigateur, et rend un verdict
clair (aucun signal inquiétant, prudence, lien dangereux) avec les raisons
qui l'expliquent.

Le cas d'usage visé : les arnaques du quotidien en France (faux colis
La Poste ou Chronopost, fausse amende ANTAI, faux remboursement Ameli ou impôts,
fausse alerte bancaire, faux PayPal).

## Ce qui est vérifié

| Contrôle | Question posée | Source |
| --- | --- | --- |
| Imitation de marque | Le lien copie-t-il une marque sans en être (nom, sous-domaine, faute de frappe `paypa1`, `@` trompeur) ? | Analyse locale |
| Âge du domaine | Le domaine a-t-il été créé il y a quelques jours ? | RDAP (successeur de WHOIS) + DNS |
| Réputation | Des antivirus l'ont-ils déjà signalé ? Repli sur le domaine si le lien est inconnu | VirusTotal |
| Destination réelle | Où mène vraiment un lien raccourci ou redirigé ? La page demande-t-elle un mot de passe ? | Requête HTTP contrôlée |
| Connexion chiffrée | Le certificat HTTPS est-il valide ? | TLS |

La page d'accueil affiche aussi **l'anatomie du lien** : le domaine réellement
visité est mis en évidence, pour apprendre à repérer
`paypal.com.verification-compte.xyz` au premier coup d'œil.

### Calcul du verdict

Les risques sont combinés comme des probabilités indépendantes
(`1 - Π(1 - confiance × risque)`) plutôt que par une moyenne : un signal fort
(domaine créé hier) n'est jamais « dilué » par quatre contrôles rassurants.
Certains signaux se renforcent entre eux, par exemple une page qui demande un
mot de passe **et** imite une marque. Seuils : moins de 20, aucun signal
inquiétant ; de 20 à 49, prudence ; 50 et plus, lien dangereux.

## Installation

```bash
uv sync
cp .env.exemple .env   # puis renseigne VIRUSTOTAL_API_KEY (gratuite)
```

Sans clé VirusTotal, les autres contrôles fonctionnent normalement.

## Utilisation

Interface web :

```bash
uv run uvicorn cyberscope.web:app --reload --app-dir src
```

Ligne de commande (code de sortie 0 sûr, 1 prudence, 2 danger) :

```bash
uv run cyberscope bit.ly/exemple
uv run cyberscope https://exemple.fr --json
```

API JSON : `GET /api/check?url=https://exemple.fr`

Chaque analyse est enregistrée dans `data/cyberscope.db` et reste consultable
depuis l'historique, avec son rapport complet.

## Sécurité de l'outil lui-même

- Les requêtes vers le site analysé refusent les adresses privées ou locales
  (protection SSRF), à chaque étape de redirection, et seulement sur les ports 80 et 443.
- La page analysée n'est jamais exécutée : seuls les en-têtes et les 512 premiers Ko
  du HTML sont lus.
- Les certificats du système sont utilisés (`truststore`), ce qui permet de
  fonctionner derrière un antivirus ou un proxy qui inspecte le HTTPS.

## Tests

```bash
uv run pytest
```

## Limites

Le verdict est une estimation à partir de signaux publics, pas une garantie.
Un lien jugé sûr peut être piégé, et un site légitime peut déclencher un
signal (domaine récent d'une petite entreprise, par exemple).
