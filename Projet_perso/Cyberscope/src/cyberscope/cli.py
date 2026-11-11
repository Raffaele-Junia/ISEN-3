"""Ligne de commande : cyberscope https://lien-suspect.fr [--json]"""

import argparse
import json
import sys

from .analyzer import analyze
from .net import is_valid_url, normalize_url

SYMBOLS = {"ok": "✓", "warn": "!", "danger": "✕", "neutral": "–", "error": "?"}


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="cyberscope",
        description="Vérifie si un lien est sûr avant de cliquer.",
    )
    parser.add_argument("url", help="lien à vérifier (https:// facultatif)")
    parser.add_argument("--json", action="store_true", help="affiche le rapport complet en JSON")
    args = parser.parse_args()

    url = normalize_url(args.url)
    if not is_valid_url(url):
        parser.error("lien invalide. Exemple : https://exemple.fr/page")

    report = analyze(url)

    if args.json:
        json.dump(report, sys.stdout, ensure_ascii=False, indent=2)
        print()
        return

    verdict = report["verdict"]
    score = "–" if verdict["score"] is None else f"{verdict['score']}/100"
    print(f"\n{url}")
    print(f"Site réellement visité : {report['anatomy']['domain']}")
    if report["final_url"] != url:
        print(f"Destination finale     : {report['final_url']}")
    print(f"\n{verdict['label'].upper()}  (risque {score})")
    print(verdict["advice"])

    if verdict["reasons"]:
        print("\nCe qui a pesé :")
        for reason in verdict["reasons"]:
            print(f"  - {reason}")

    print()
    for check in report["checks"]:
        print(f"  {SYMBOLS[check['status']]} {check['title']:<22} {check['headline']}")
    print()

    # Code de sortie exploitable dans un script : 0 sûr, 1 prudence, 2 danger.
    sys.exit({"safe": 0, "caution": 1, "danger": 2}.get(verdict["key"], 3))


if __name__ == "__main__":
    main()
