"""Où mène vraiment le lien ? Suit les redirections et inspecte la page d'arrivée.

Les liens raccourcis (bit.ly...) et les chaînes de redirection servent souvent
à masquer la vraie destination d'un lien de phishing.
"""

import re
from typing import Any
from urllib.parse import urljoin, urlparse

import requests

from .checks import add_signal, failed, finalize, new_check
from .net import is_public_host, registrable_domain

TITLE = "Destination réelle"
MAX_REDIRECTS = 6
MAX_BODY = 512 * 1024
USER_AGENT = "Mozilla/5.0 (compatible; CyberScope/0.2; +link-safety-check)"

SECURITY_HEADERS = (
    "Strict-Transport-Security",
    "Content-Security-Policy",
    "X-Content-Type-Options",
    "Referrer-Policy",
    "Permissions-Policy",
)

PASSWORD_FIELD = re.compile(rb"<input[^>]+type\s*=\s*[\"']?password", re.IGNORECASE)
TITLE_TAG = re.compile(rb"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)


def _allowed(url: str) -> bool:
    """Ne contacte que des hôtes publics, sur les ports web standards."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return False
    if parsed.username is not None or parsed.password is not None:
        return False
    try:
        port = parsed.port
    except ValueError:
        return False
    if port not in (None, 80, 443):
        return False
    return is_public_host(parsed.hostname)


def check_destination(url: str) -> dict[str, Any]:
    """Renvoie le contrôle et, dans check["final_url"], l'adresse d'arrivée."""
    check = new_check("destination", TITLE)
    check["final_url"] = url
    check["has_password_form"] = False

    chain = [url]
    current = url
    response = None

    try:
        for _ in range(MAX_REDIRECTS + 1):
            if not _allowed(current):
                return failed("destination", TITLE,
                              "Destination non publique ou port inhabituel : visite bloquée par sécurité.")

            response = requests.get(
                current,
                timeout=(4, 6),
                allow_redirects=False,
                stream=True,
                headers={"User-Agent": USER_AGENT, "Accept": "text/html,*/*"},
            )
            location = response.headers.get("Location")
            if 300 <= response.status_code < 400 and location:
                response.close()
                current = urljoin(current, location)
                chain.append(current)
                continue
            break
        else:
            add_signal(check, f"Plus de {MAX_REDIRECTS} redirections enchaînées.", 40)
            chain.pop()  # la dernière destination n'a jamais été visitée

        body = b""
        followed_to_end = 300 > response.status_code or response.status_code >= 400
        if followed_to_end and "html" in response.headers.get("Content-Type", ""):
            for chunk in response.iter_content(64 * 1024):
                body += chunk
                if len(body) >= MAX_BODY:
                    break
    except requests.Timeout:
        return failed("destination", TITLE, "Le site ne répond pas : délai dépassé.")
    except requests.RequestException:
        return failed("destination", TITLE, "Le site refuse la connexion ou est hors ligne.")
    finally:
        if response is not None:
            response.close()

    final = chain[-1]
    check["final_url"] = final
    start_domain = registrable_domain(urlparse(url).hostname or "")
    final_domain = registrable_domain(urlparse(final).hostname or "")

    if len(chain) > 1:
        check["facts"].append(["Redirections", chain])
    check["facts"].append(["Page d'arrivée", final])
    check["facts"].append(["Réponse du serveur", f"HTTP {response.status_code}"])

    title = TITLE_TAG.search(body)
    if title:
        page_title = " ".join(title.group(1).decode("utf-8", "replace").split())[:120]
        if page_title:
            check["facts"].append(["Titre de la page", page_title])

    if PASSWORD_FIELD.search(body):
        check["has_password_form"] = True
        check["facts"].append(["Demande un mot de passe", "oui"])

    if final_domain != start_domain:
        add_signal(check, f"Le lien redirige vers un autre site : {final_domain}.", 25)
        check["headline"] = f"Le lien t'envoie en réalité sur {final_domain}."
    elif len(chain) > 1:
        check["headline"] = f"Redirigé {len(chain) - 1} fois, sans changer de site."
    else:
        check["headline"] = "Pas de redirection : la page s'ouvre directement."

    if urlparse(url).scheme == "https" and urlparse(final).scheme == "http":
        add_signal(check, "La redirection abandonne le chiffrement HTTPS.", 35)

    present = [name for name in SECURITY_HEADERS if response.headers.get(name)]
    check["facts"].append([
        "Protections du navigateur",
        f"{len(present)} sur {len(SECURITY_HEADERS)} en-têtes de sécurité",
    ])
    if len(present) <= 1:
        add_signal(check, "Le site n'active presque aucune protection du navigateur.", 10)

    if not check["signals"]:
        check["status"] = "ok"
    return finalize(check)
