"""Telecharge UNE FOIS les couvertures des livres depuis Open Library.

    uv run python scripts/telecharger_couvertures.py [--depuis data_demo] [--forcer]

- Les images vont dans src/mediatheque/web/static/couvertures/<id>.jpg : le site
  les sert lui-meme, aucun visiteur n'interroge un service tiers (RGPD, CSP).
- Elles ne sont PAS versionnees (.gitignore) : ce sont des oeuvres protegees,
  utilisees ici dans un cadre de catalogue de bibliotheque / projet etudiant.
- Films et revues gardent la couverture typographique dessinee par le site.
- Garde-fous : vrai JPEG uniquement (signature FFD8FF), 2 Mo maximum, pause
  entre deux requetes, aucune donnee personnelle envoyee.
"""
import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from mediatheque.documents import FORMAT_ID_DOCUMENT
from mediatheque.mediatheque import Mediatheque

RACINE = Path(__file__).resolve().parent.parent
DOSSIER = RACINE / "src" / "mediatheque" / "web" / "static" / "couvertures"
RECHERCHE = "https://openlibrary.org/search.json"
IMAGE = "https://covers.openlibrary.org/b/id/{}-L.jpg?default=false"
ENTETES = {"User-Agent": "MediathequeDesTilleuls/0.1 (projet etudiant ISEN)"}
TAILLE_MAX = 2 * 1024 * 1024
PAUSE_S = 0.4
DUREE_MAX_S = 30
# Seuls ces domaines (et leurs sous-domaines) sont contactes, en HTTPS (F4).
HOTES_AUTORISES = ("openlibrary.org", "archive.org")
_FORMAT_ID = FORMAT_ID_DOCUMENT  # D + 1 a 6 chiffres ASCII (Z7)


def url_autorisee(url):
    parties = urllib.parse.urlsplit(url)
    hote = (parties.hostname or "").lower()
    return parties.scheme == "https" and any(
        hote == h or hote.endswith("." + h) for h in HOTES_AUTORISES)


class _RedirectionsSures(urllib.request.HTTPRedirectHandler):
    """Refuse toute redirection hors HTTPS ou hors des domaines autorises (F4)."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not url_autorisee(newurl):
            raise ValueError(f"redirection refusee vers {newurl}")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


# urlopen passe desormais par ce gestionnaire de redirections (script autonome).
urllib.request.install_opener(urllib.request.build_opener(_RedirectionsSures))


def lire(url, limite=TAILLE_MAX):
    if not url_autorisee(url):
        raise ValueError(f"adresse non autorisee : {url}")
    debut = time.monotonic()
    requete = urllib.request.Request(url, headers=ENTETES)
    with urllib.request.urlopen(requete, timeout=20) as reponse:
        donnees = reponse.read(limite + 1)
        if len(donnees) > limite:
            raise ValueError("reponse trop volumineuse")
        if time.monotonic() - debut > DUREE_MAX_S:
            raise TimeoutError("telechargement trop long")
        return donnees, reponse.headers.get_content_type()


def chercher_couverture(livre):
    """Identifiant de couverture Open Library pour ce livre, ou None."""
    if livre.isbn:
        return f"isbn:{livre.isbn}"
    params = urllib.parse.urlencode({"title": livre.titre, "author": livre.auteur,
                                     "limit": 5, "fields": "cover_i,title"})
    donnees, _ = lire(f"{RECHERCHE}?{params}", limite=512 * 1024)
    for doc in json.loads(donnees).get("docs", []):
        if doc.get("cover_i"):
            return int(doc["cover_i"])
    return None


def telecharger(cle, cible):
    if isinstance(cle, str) and cle.startswith("isbn:"):
        url = f"https://covers.openlibrary.org/b/isbn/{urllib.parse.quote(cle[5:])}-L.jpg?default=false"
    else:
        url = IMAGE.format(int(cle))
    donnees, type_mime = lire(url)
    if type_mime != "image/jpeg" or not donnees.startswith(b"\xff\xd8\xff"):
        raise ValueError(f"pas un JPEG ({type_mime})")
    if len(donnees) < 2000:  # vignette vide / image de remplacement
        raise ValueError("image trop petite")
    tmp = cible.with_suffix(".part")
    tmp.write_bytes(donnees)
    tmp.replace(cible)  # ecriture atomique
    return len(donnees)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--depuis", default=str(RACINE / "data_demo"))
    parser.add_argument("--forcer", action="store_true", help="retelecharger meme si present")
    args = parser.parse_args()

    DOSSIER.mkdir(parents=True, exist_ok=True)
    m = Mediatheque.charger(args.depuis)
    livres = [d for d in sorted(m, key=lambda d: d.id) if d.CLE == "livre"]
    ok = deja = absents = erreurs = 0
    dossier = DOSSIER.resolve()
    for livre in livres:
        cible = (DOSSIER / f"{livre.id}.jpg").resolve()
        # F3 : identifiant au format attendu ET fichier strictement dans le dossier
        if not _FORMAT_ID.fullmatch(livre.id) or cible.parent != dossier:
            erreurs += 1
            print(f"  !! identifiant refuse : {livre.id!r}", file=sys.stderr)
            continue
        if cible.exists() and not args.forcer:
            deja += 1
            continue
        try:
            cle = chercher_couverture(livre)
            time.sleep(PAUSE_S)
            if cle is None:
                absents += 1
                print(f"  -  {livre.id} {livre.titre} : pas de couverture trouvee")
                continue
            taille = telecharger(cle, cible)
            ok += 1
            print(f"  ok {livre.id} {livre.titre} ({taille // 1024} Ko)")
        except (urllib.error.URLError, ValueError, TimeoutError, json.JSONDecodeError) as e:
            erreurs += 1
            print(f"  !! {livre.id} {livre.titre} : {e}", file=sys.stderr)
        time.sleep(PAUSE_S)
    print(f"\n{ok} telechargees, {deja} deja presentes, {absents} introuvables, "
          f"{erreurs} erreurs — dossier : {DOSSIER}")


if __name__ == "__main__":
    main()
