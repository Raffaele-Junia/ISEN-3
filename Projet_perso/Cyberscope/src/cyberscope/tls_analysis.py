
import socket
import ssl
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse
import ipaddress

def analyze_tls(url: str) -> dict[str, Any]:
    result: dict[str, Any] = {
        "title": "Certificat HTTPS / TLS",
        "status": "info",
        "summary": "",
        "details": {},
        "warnings": [],
    }

    parsed = urlparse(url)

    if parsed.scheme != "https" or not parsed.hostname:
        result["status"] = "warning"
        result["summary"] = (
            "Cette URL n'utilise pas HTTPS : aucun certificat TLS "
            "ne peut être vérifié pour cette adresse."
        )
        return result

    hostname = parsed.hostname

    try:
        port = parsed.port or 443
    except ValueError:
        result["status"] = "error"
        result["summary"] = "Port HTTPS invalide."
        return result

    try:
        addresses = socket.getaddrinfo(
            hostname, port, type=socket.SOCK_STREAM
        )
        if not addresses or any(
            not ipaddress.ip_address(item[4][0]).is_global
            for item in addresses
        ):
            result["status"] = "error"
            result["summary"] = (
                "Connexion refusée : le domaine résout vers "
                "une adresse non publique."
            )
            return result
    except (OSError, ValueError):
        result["status"] = "error"
        result["summary"] = (
            "Impossible de résoudre le domaine vers une adresse publique."
        )
        return result    

    context = ssl.create_default_context()

    try:
        with socket.create_connection(
            (hostname, port), timeout=5
        ) as raw_socket:
            with context.wrap_socket(
                raw_socket, server_hostname=hostname
            ) as tls_socket:
                certificate = tls_socket.getpeercert()
                result["details"]["Version TLS"] = tls_socket.version()
                result["details"]["Émetteur"] = str(
                    certificate.get("issuer", "Inconnu")
                )
                result["details"]["Valide à partir du"] = (
                    certificate.get("notBefore", "Inconnu")
                )
                result["details"]["Expire le"] = (
                    certificate.get("notAfter", "Inconnu")
                )

                expiry_text = certificate.get("notAfter")
                if expiry_text:
                    expiry = datetime.strptime(
                        expiry_text, "%b %d %H:%M:%S %Y %Z"
                    ).replace(tzinfo=timezone.utc)

                    remaining_days = (
                        expiry - datetime.now(timezone.utc)
                    ).days
                    result["details"]["Jours avant expiration"] = (
                        remaining_days
                    )

                    if remaining_days < 0:
                        result["status"] = "warning"
                        result["warnings"].append(
                            "Le certificat est expiré."
                        )
                    elif remaining_days <= 30:
                        result["status"] = "warning"
                        result["warnings"].append(
                            "Le certificat expire dans 30 jours ou moins."
                        )

        if result["status"] == "info":
            result["status"] = "success"

        if result["status"] == "success":
            result["summary"] = (
                "La connexion TLS a réussi et le certificat a été vérifié."
            )
        else:
            result["summary"] = (
                "La connexion TLS a réussi, mais le certificat "
                "présente un avertissement."
            )

    except (OSError, ssl.SSLError, ValueError) as exc:
        result["status"] = "warning"
        result["summary"] = (
            "Impossible de valider le certificat ou d'établir "
            "une connexion TLS."
        )
        result["details"]["Erreur"] = str(exc)

    return result
