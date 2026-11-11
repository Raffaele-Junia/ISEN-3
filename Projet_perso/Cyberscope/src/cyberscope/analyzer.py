"""Point d'entrée unique : analyse un lien et renvoie un rapport complet.

Utilisé à l'identique par l'interface web, l'API JSON et la ligne de commande.
"""

import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any, Callable
from urllib.parse import urlparse

from .checks import add_signal, failed, finalize, new_check
from .destination_analysis import check_destination
from .domain_analysis import check_domain
from .link_analysis import check_link
from .net import registrable_domain
from .reputation import check_reputation
from .scoring import build_verdict
from .tls_analysis import check_tls

logger = logging.getLogger(__name__)

# Ordre d'affichage : du signal le plus parlant au plus technique.
DISPLAY_ORDER = ("link", "domain", "reputation", "destination", "tls")

TITLES = {
    "link": "Imitation de marque",
    "domain": "Âge du domaine",
    "reputation": "Réputation",
    "destination": "Destination réelle",
    "tls": "Connexion chiffrée",
}


def _safe(check_id: str, function: Callable[..., dict], *args: Any) -> dict[str, Any]:
    """Un contrôle qui plante ne doit jamais faire tomber toute l'analyse."""
    try:
        return function(*args)
    except Exception:
        logger.exception("Le contrôle %s a échoué", check_id)
        return failed(check_id, TITLES[check_id], "Erreur inattendue pendant ce contrôle.")


def anatomy(url: str) -> dict[str, str]:
    """Découpe l'URL pour montrer à l'utilisateur quel est le vrai site."""
    parsed = urlparse(url)
    hostname = parsed.hostname or ""
    domain = registrable_domain(hostname)
    netloc = parsed.netloc
    host_start = netloc.lower().find(hostname)
    before_host = netloc[:host_start] if host_start > 0 else ""
    after_host = netloc[host_start + len(hostname):] if host_start >= 0 else ""
    subdomain = hostname[: -len(domain)] if hostname.endswith(domain) else ""

    rest = parsed.path or ""
    if parsed.query:
        rest += "?" + parsed.query
    if parsed.fragment:
        rest += "#" + parsed.fragment

    return {
        "scheme": parsed.scheme + "://",
        "userinfo": before_host,
        "subdomain": subdomain,
        "domain": domain,
        "port": after_host,
        "rest": rest,
    }


def _combo(destination: dict, domain: dict, link: dict) -> dict[str, Any]:
    """Signaux qui ne deviennent graves qu'ensemble."""
    check = new_check("combo", "Recoupement")
    if destination.get("has_password_form"):
        if (link["risk"] or 0) >= 50:
            add_signal(check, "La page demande un mot de passe tout en imitant une marque.", 90)
        elif (domain["risk"] or 0) >= 35:
            add_signal(check, "La page demande un mot de passe sur un domaine tout récent.", 80)
    return finalize(check)


def analyze(url: str) -> dict[str, Any]:
    hostname = urlparse(url).hostname or ""

    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {
            "reputation": pool.submit(_safe, "reputation", check_reputation, url, hostname),
            "domain": pool.submit(_safe, "domain", check_domain, hostname),
            "destination": pool.submit(_safe, "destination", check_destination, url),
            "tls": pool.submit(_safe, "tls", check_tls, url),
        }
        results = {key: future.result() for key, future in futures.items()}

    final_url = results["destination"].get("final_url") or url
    results["link"] = _safe("link", check_link, url, final_url)

    checks = [results[key] for key in DISPLAY_ORDER]
    combo = _combo(results["destination"], results["domain"], results["link"])
    verdict = build_verdict(checks + [combo])

    return {
        "url": url,
        "final_url": final_url,
        "anatomy": anatomy(url),
        "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "verdict": verdict,
        "checks": checks,
    }
