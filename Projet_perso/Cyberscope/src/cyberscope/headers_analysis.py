
import ipaddress
import socket
from typing import Any
from urllib.parse import urlparse

import requests


SECURITY_HEADERS = {
    "Content-Security-Policy": (
        "Limite les sources de contenu autorisées dans la page."
    ),
    "Strict-Transport-Security": (
        "Indique au navigateur d'utiliser HTTPS pour les connexions futures."
    ),
    "X-Content-Type-Options": (
        "Empêche certains types de détection automatique du contenu."
    ),
    "Referrer-Policy": (
        "Contrôle les informations envoyées dans l'en-tête Referer."
    ),
    "Permissions-Policy": (
        "Contrôle l'accès à certaines fonctionnalités du navigateur."
    ),
}


def _host_is_public(hostname: str) -> bool:
    """Contrôle préliminaire contre les accès aux IP privées ou locales."""
    try:
        literal_ip = ipaddress.ip_address(hostname)
        return literal_ip.is_global
    except ValueError:
        pass

    try:
        addresses = socket.getaddrinfo(
            hostname, None, type=socket.SOCK_STREAM
        )
    except (socket.gaierror, OSError):
        return False

    if not addresses:
        return False

    for item in addresses:
        try:
            address = ipaddress.ip_address(item[4][0])
        except ValueError:
            return False
        if not address.is_global:
            return False

    return True


def analyze_headers(url: str) -> dict[str, Any]:
    result: dict[str, Any] = {
        "title": "Audit des en-têtes HTTP",
        "status": "info",
        "summary": "",
        "details": {},
        "warnings": [],
    }

    parsed = urlparse(url)

    if (
        parsed.scheme not in ("http", "https")
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
    ):
        result["status"] = "error"
        result["summary"] = "URL invalide pour une requête HTTP."
        return result

    try:
        port = parsed.port
    except ValueError:
        result["status"] = "error"
        result["summary"] = "Port invalide."
        return result

    if port is not None and not (
        (parsed.scheme == "http" and port == 80)
        or (parsed.scheme == "https" and port == 443)
    ):
        result["status"] = "warning"
        result["summary"] = (
            "Par sécurité, l'audit HTTP n'accepte que les ports 80 et 443."
        )
        return result

    if not _host_is_public(parsed.hostname):
        result["status"] = "error"
        result["summary"] = (
            "La cible ne peut pas être contactée : hôte non public, "
            "résolution DNS impossible ou adresse potentiellement privée."
        )
        return result

    try:
        response = requests.get(
            url,
            timeout=(3, 5),
            allow_redirects=False,
            stream=True,
            headers={"User-Agent": "CyberScope-Security-Audit/1.0"},
        )

        try:
            result["details"]["Code HTTP"] = response.status_code
            result["details"]["Type de contenu"] = response.headers.get(
                "Content-Type", "Non précisé"
            )

            if 300 <= response.status_code < 400:
                result["warnings"].append(
                    "Le serveur répond par une redirection. "
                    "La destination n'a pas été suivie."
                )
                result["details"]["Destination de redirection"] = (
                    response.headers.get("Location", "Non précisée")
                )

            present = []
            missing = []

            for header, description in SECURITY_HEADERS.items():
                value = response.headers.get(header)
                if value:
                    present.append({
                        "name": header,
                        "value": value,
                        "description": description,
                    })
                else:
                    missing.append({
                        "name": header,
                        "description": description,
                    })

            result["details"]["En-têtes présents"] = present
            result["details"]["En-têtes manquants"] = missing
            result["details"]["Nombre présents"] = len(present)
            result["details"]["Nombre manquants"] = len(missing)

            if missing:
                result["status"] = "warning"
                result["summary"] = (
                    f"{len(missing)} en-tête(s) de sécurité "
                    "attendu(s) n'ont pas été trouvés."
                )
                result["warnings"].extend(
                    f"En-tête absent : {item['name']}"
                    for item in missing
                )
            else:
                result["status"] = "success"
                result["summary"] = (
                    "Tous les en-têtes de sécurité contrôlés sont présents."
                )
        finally:
            response.close()

    except requests.RequestException as exc:
        result["status"] = "error"
        result["summary"] = (
            "La requête HTTP a échoué. Le site peut être indisponible "
            "ou avoir refusé la connexion."
        )
        result["details"]["Erreur"] = str(exc)

    return result
