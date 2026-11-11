"""Le domaine existe-t-il, depuis quand, et qui l'a enregistré ?

Un site de phishing vit rarement plus de quelques semaines : l'âge du domaine
est l'un des signaux les plus fiables dont on dispose sans clé d'API.
"""

import ipaddress
import socket
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any

import dns.exception
import dns.resolver
import requests

from .checks import add_signal, finalize, new_check
from .net import registrable_domain

TITLE = "Âge du domaine"
RDAP_URL = "https://rdap.org/domain/{}"


def _resolver() -> dns.resolver.Resolver:
    resolver = dns.resolver.Resolver()
    resolver.timeout = 1    # par serveur : un DNS de VPN muet ne bloque pas tout
    resolver.lifetime = 3
    return resolver


def _resolve(hostname: str) -> tuple[list[str], bool]:
    """Renvoie (adresses IP, domaine inexistant) via le résolveur du système."""
    try:
        infos = socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
        return sorted({info[4][0] for info in infos}), False
    except (socket.gaierror, OSError, UnicodeError):
        pass

    # Le système ne trouve rien : on distingue « inexistant » de « sans IP ».
    try:
        _resolver().resolve(hostname, "A")
    except dns.resolver.NXDOMAIN:
        return [], True
    except (dns.resolver.NoAnswer, dns.resolver.NoNameservers, dns.exception.Timeout):
        pass
    return [], False


def _has_mail(domain: str) -> bool:
    try:
        _resolver().resolve(domain, "MX")
        return True
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer,
            dns.resolver.NoNameservers, dns.exception.Timeout):
        return False


def _rdap(domain: str) -> tuple[datetime | None, str | None]:
    """Date de création et bureau d'enregistrement via RDAP (successeur de WHOIS)."""
    try:
        response = requests.get(
            RDAP_URL.format(domain),
            timeout=8,
            headers={"Accept": "application/rdap+json"},
        )
        if not response.ok:
            return None, None
        data = response.json()
    except (requests.RequestException, ValueError):
        return None, None

    created = None
    for event in data.get("events", []):
        if event.get("eventAction") == "registration":
            try:
                created = datetime.fromisoformat(event["eventDate"].replace("Z", "+00:00"))
            except (KeyError, ValueError):
                pass

    registrar = None
    for entity in data.get("entities", []):
        if "registrar" in (entity.get("roles") or []):
            vcard = entity.get("vcardArray") or [None, []]
            for field in vcard[1]:
                if field and field[0] == "fn":
                    registrar = str(field[3])
    return created, registrar


def _format_age(days: int) -> str:
    if days < 1:
        return "moins d'un jour"
    if days < 60:
        return f"{days} jour{'s' if days > 1 else ''}"
    if days < 730:
        return f"{days // 30} mois"
    return f"{days // 365} ans"


def check_domain(hostname: str) -> dict[str, Any]:
    check = new_check("domain", TITLE)
    hostname = hostname.lower().rstrip(".")

    try:
        ipaddress.ip_address(hostname)
        check["headline"] = "Le lien pointe vers une adresse IP brute, sans nom de domaine."
        add_signal(check, "Le lien utilise une adresse IP au lieu d'un nom de domaine.", 40)
        return finalize(check)
    except ValueError:
        pass

    domain = registrable_domain(hostname)
    with ThreadPoolExecutor(max_workers=3) as pool:
        resolution = pool.submit(_resolve, hostname)
        mail = pool.submit(_has_mail, domain)
        registration = pool.submit(_rdap, domain)
        addresses, nxdomain = resolution.result()
        has_mail = mail.result()
        created, registrar = registration.result()

    check["facts"].append(["Domaine enregistré", domain])

    if nxdomain:
        check["headline"] = "Ce domaine n'existe pas : le lien ne mène nulle part."
        add_signal(check, "Le domaine n'existe pas dans le DNS.", 40)
        return finalize(check)

    if created:
        age_days = (datetime.now(timezone.utc) - created).days
        check["facts"].append(["Créé le", created.strftime("%d/%m/%Y")])
        check["facts"].append(["Âge", _format_age(age_days)])

        if age_days < 30:
            add_signal(check, f"Domaine créé il y a {_format_age(age_days)} seulement.", 75)
        elif age_days < 180:
            add_signal(check, f"Domaine récent, créé il y a {_format_age(age_days)}.", 35)
        elif age_days < 365:
            add_signal(check, "Domaine de moins d'un an.", 12)

        check["headline"] = f"Domaine enregistré il y a {_format_age(age_days)}."
        if age_days >= 365:
            check["status"] = "ok"
    else:
        check["headline"] = "Date de création introuvable pour ce domaine."

    if registrar:
        check["facts"].append(["Bureau d'enregistrement", registrar])
    check["facts"].append(["Adresses IP", addresses or ["Aucune"]])
    check["facts"].append(["Reçoit des e-mails", "oui" if has_mail else "non"])

    if not addresses:
        add_signal(check, "Le domaine existe mais ne pointe vers aucun serveur.", 20)

    return finalize(check)
