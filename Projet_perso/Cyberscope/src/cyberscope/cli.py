
import argparse
from urllib.parse import urlparse

from . import analyzer


def is_valid_url(url: str) -> bool:
    """Vérifie que l'URL contient un schéma et un nom d'hôte."""
    parsed = urlparse(url)
    return parsed.scheme in ("http", "https") and bool(parsed.hostname)


def main():
    parser = argparse.ArgumentParser(
        description="CyberScope - outil pour analyser la fiabilité des liens"
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True
    )

    url_parser = subparsers.add_parser(
        "url",
        help="Analyser une URL"
    )
    url_parser.add_argument("url", help="URL à analyser")

    args = parser.parse_args()

    if args.command == "url":
        if not is_valid_url(args.url):
            parser.error(
                "URL invalide. Exemple : https://youtube.com"
            )

        analyzer.display_analyse(args.url)


if __name__ == "__main__":
    main()
