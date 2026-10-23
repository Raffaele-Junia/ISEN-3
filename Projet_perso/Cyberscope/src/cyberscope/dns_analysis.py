
import socket
from typing import Any

import dns.exception
import dns.resolver


def analyze_dns(hostname: str) -> dict[str, Any]:
    """Récupère les informations DNS publiques d'un nom d'hôte."""
    result: dict[str, Any] = {
        "title": "Analyse DNS et domaine",
        "status": "info",
        "summary": "",
        "details": {},
        "warnings": [],
    }

    hostname = hostname.rstrip(".").lower()

    if not hostname:
        result["status"] = "error"
        result["summary"] = "Nom de domaine absent."
        return result

    try:
        addresses = sorted({
            item[4][0]
            for item in socket.getaddrinfo(
                hostname, None, type=socket.SOCK_STREAM
            )
        })
        result["details"]["Adresses IP"] = addresses
    except (socket.gaierror, OSError) as exc:
        result["details"]["Résolution IP"] = f"Échec : {exc}"

    resolver = dns.resolver.Resolver()
    resolver.timeout = 2
    resolver.lifetime = 4

    for record_type in ("A", "AAAA", "MX", "NS", "TXT"):
        try:
            answers = resolver.resolve(hostname, record_type)
            values = [str(answer) for answer in answers]
            result["details"][record_type] = values
        except dns.resolver.NoAnswer:
            result["details"][record_type] = [
                "Aucun enregistrement de ce type"
            ]
        except dns.resolver.NXDOMAIN:
            result["status"] = "warning"
            result["summary"] = "Le domaine n'existe pas dans le DNS."
            result["warnings"].append(
                "Le nom de domaine n'a pas été trouvé."
            )
            return result
        except (
            dns.resolver.NoNameservers,
            dns.exception.Timeout,
            dns.resolver.LifetimeTimeout,
        ):
            result["details"][record_type] = [
                "Réponse indisponible ou délai dépassé"
            ]

    if addresses:
        result["status"] = "success"
        result["summary"] = (
            f"Le domaine se résout vers {len(addresses)} adresse(s) IP."
        )
    else:
        result["status"] = "warning"
        result["summary"] = (
            "Aucune adresse IP n'a pu être résolue. "
            "Vérifie le domaine et la disponibilité du DNS."
        )

    return result
