"""La connexion est-elle chiffrée, et le certificat est-il valide ?"""

import socket
import ssl
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from .checks import add_signal, failed, finalize, new_check
from .net import is_public_host

TITLE = "Connexion chiffrée"


def _name_field(certificate: dict, key: str, field: str) -> str | None:
    """Extrait un champ lisible (ex. organizationName) du tuple issuer/subject."""
    for rdn in certificate.get(key, ()):
        for name, value in rdn:
            if name == field:
                return value
    return None


def check_tls(url: str) -> dict[str, Any]:
    check = new_check("tls", TITLE)
    parsed = urlparse(url)

    if parsed.scheme != "https":
        check["headline"] = "Lien en HTTP : tout ce que tu saisis circule en clair."
        add_signal(check, "Le lien n'est pas chiffré (HTTP au lieu de HTTPS).", 30)
        return finalize(check)

    hostname = parsed.hostname or ""
    try:
        port = parsed.port or 443
    except ValueError:
        return failed("tls", TITLE, "Port invalide dans le lien.")

    if not is_public_host(hostname):
        return failed("tls", TITLE, "Hôte injoignable ou adresse non publique.")

    context = ssl.create_default_context()
    try:
        with socket.create_connection((hostname, port), timeout=5) as raw:
            with context.wrap_socket(raw, server_hostname=hostname) as tls:
                certificate = tls.getpeercert() or {}
                version = tls.version()
    except ssl.SSLCertVerificationError as exc:
        check["headline"] = "Certificat invalide : le navigateur afficherait une alerte."
        check["facts"].append(["Erreur", exc.verify_message or str(exc)])
        add_signal(check, "Le certificat HTTPS est invalide ou ne correspond pas au site.", 70)
        return finalize(check)
    except TimeoutError:
        return failed("tls", TITLE, "Connexion HTTPS impossible : le site ne répond pas.")
    except (OSError, ssl.SSLError):
        return failed("tls", TITLE, "Connexion HTTPS impossible : le site refuse la connexion.")

    issuer = _name_field(certificate, "issuer", "organizationName") or "Inconnu"
    owner = _name_field(certificate, "subject", "organizationName")

    check["facts"].append(["Délivré par", issuer])
    if owner:
        check["facts"].append(["Organisation vérifiée", owner])
    check["facts"].append(["Protocole", version or "Inconnu"])

    expiry_text = certificate.get("notAfter")
    if expiry_text:
        expiry = datetime.strptime(expiry_text, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
        days_left = (expiry - datetime.now(timezone.utc)).days
        check["facts"].append(["Expire le", expiry.strftime("%d/%m/%Y")])
        if days_left < 0:
            add_signal(check, "Le certificat HTTPS est expiré.", 60)
        elif days_left <= 7:
            add_signal(check, f"Le certificat expire dans {days_left} jour(s).", 15)

    if version in ("TLSv1", "TLSv1.1"):
        add_signal(check, f"Protocole obsolète ({version}).", 20)

    if not check["signals"]:
        check["status"] = "ok"
    check["headline"] = (
        f"Certificat valide, délivré par {issuer}."
        if not check["signals"] else check["signals"][0]["text"]
    )
    return finalize(check)
