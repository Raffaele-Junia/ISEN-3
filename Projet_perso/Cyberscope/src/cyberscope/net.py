"""Outils réseau partagés : validation d'URL, domaine enregistré, hôtes publics."""

import ipaddress
import socket
from urllib.parse import urlparse

# Suffixes à deux niveaux les plus courants. Ce n'est pas la Public Suffix
# List complète, mais cela couvre l'essentiel des liens rencontrés en France.
SECOND_LEVEL_SUFFIXES = {
    "co.uk", "org.uk", "ac.uk", "gov.uk", "gouv.fr", "asso.fr", "com.fr",
    "com.au", "net.au", "org.au", "co.jp", "co.nz", "com.br", "com.cn",
    "co.in", "co.za", "com.mx", "com.tr", "com.es", "co.kr", "com.sg",
}


def normalize_url(raw: str) -> str:
    """Ajoute https:// si l'utilisateur a collé un domaine nu."""
    raw = raw.strip()
    if raw and "://" not in raw:
        raw = "https://" + raw
    return raw


def is_valid_url(url: str) -> bool:
    """Vérifie la structure de base de l'URL."""
    try:
        parsed = urlparse(url)
        return (
            parsed.scheme in ("http", "https")
            and bool(parsed.hostname)
            and parsed.port != 0
            and not any(char.isspace() for char in url)
            and len(url) <= 2048
        )
    except ValueError:
        return False


def registrable_domain(hostname: str) -> str:
    """Renvoie le domaine réellement enregistré (ex. login.paypal.com.evil.io -> evil.io)."""
    hostname = hostname.lower().rstrip(".")
    try:
        ipaddress.ip_address(hostname)
        return hostname
    except ValueError:
        pass

    labels = hostname.split(".")
    if len(labels) <= 2:
        return hostname
    if ".".join(labels[-2:]) in SECOND_LEVEL_SUFFIXES:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:])


def is_public_host(hostname: str) -> bool:
    """Refuse les hôtes qui résolvent vers une adresse privée ou locale (anti-SSRF)."""
    try:
        return ipaddress.ip_address(hostname).is_global
    except ValueError:
        pass

    try:
        addresses = socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
    except (socket.gaierror, OSError, UnicodeError):
        return False

    if not addresses:
        return False

    for item in addresses:
        try:
            if not ipaddress.ip_address(item[4][0]).is_global:
                return False
        except ValueError:
            return False
    return True
