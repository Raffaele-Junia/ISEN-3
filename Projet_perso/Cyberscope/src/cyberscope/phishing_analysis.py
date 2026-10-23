
import ipaddress
from typing import Any
from urllib.parse import unquote, urlparse


BRAND_NAMES = {
    "paypal", "microsoft", "google", "apple",
    "amazon", "facebook", "instagram", "netflix",
}

SUSPICIOUS_WORDS = {
    "login", "signin", "verify", "verification",
    "account", "password", "secure", "update",
    "wallet", "confirm", "auth",
}


def analyze_phishing(url: str) -> dict[str, Any]:
    result: dict[str, Any] = {
        "title": "Détection de signaux de phishing",
        "status": "success",
        "summary": "",
        "details": {},
        "warnings": [],
    }

    parsed = urlparse(url)
    hostname = (parsed.hostname or "").lower().rstrip(".")
    decoded_url = unquote(url).lower()
    signals: list[str] = []
    points = 0

    if not hostname:
        result["status"] = "error"
        result["summary"] = "Impossible d'extraire le nom d'hôte."
        return result

    try:
        ipaddress.ip_address(hostname)
        signals.append(
            "L'URL utilise une adresse IP directement comme hôte."
        )
        points += 2
    except ValueError:
        pass

    if "@" in parsed.netloc:
        signals.append(
            "L'URL contient un caractère @ dans la partie autorité, "
            "ce qui peut masquer le véritable hôte."
        )
        points += 2

    if len(url) > 200:
        signals.append("L'URL est particulièrement longue.")
        points += 1

    if hostname.startswith("xn--") or ".xn--" in hostname:
        signals.append(
            "Le domaine contient un label Punycode. "
            "Cela peut être légitime, mais mérite une vérification."
        )
        points += 1

    if hostname.count("-") >= 3:
        signals.append(
            "Le nom d'hôte contient plusieurs tirets."
        )
        points += 1

    if hostname.count(".") >= 4:
        signals.append(
            "Le nom d'hôte comporte un nombre élevé de sous-domaines."
        )
        points += 1

    matched_words = sorted(
        word for word in SUSPICIOUS_WORDS
        if word in decoded_url
    )
    if matched_words:
        signals.append(
            "Mots-clés potentiellement sensibles détectés : "
            + ", ".join(matched_words)
            + "."
        )
        points += min(2, len(matched_words))

    labels = hostname.split(".")
    domain_labels = labels[:-1] if len(labels) > 1 else labels

    brand_matches = sorted(
        brand for brand in BRAND_NAMES
        if any(
            brand in label and label != brand
            for label in domain_labels
        )
    )

    if brand_matches:
        signals.append(
            "Le domaine contient des noms de marques dans une forme "
            "qui peut être trompeuse : "
            + ", ".join(brand_matches)
            + ". Vérifie le domaine officiel."
        )
        points += 2

    if parsed.scheme != "https":
        signals.append(
            "L'URL n'utilise pas HTTPS. Cela n'indique pas à lui seul "
            "qu'il s'agit d'un site malveillant."
        )
        points += 1

    result["details"]["Nom d'hôte"] = hostname
    result["details"]["Signaux détectés"] = signals
    result["details"]["Nombre de signaux"] = len(signals)
    result["details"]["Indice heuristique"] = min(points, 10)

    if points >= 5:
        result["status"] = "warning"
        result["summary"] = (
            "Plusieurs signaux méritent une vérification manuelle. "
            "Ce résultat ne prouve pas une tentative de phishing."
        )
    elif points > 0:
        result["status"] = "info"
        result["summary"] = (
            "Quelques caractéristiques sont à examiner. "
            "Elles peuvent aussi être légitimes."
        )
    else:
        result["summary"] = (
            "Aucun des signaux heuristiques implémentés n'a été détecté. "
            "Cela ne garantit pas que l'URL est sûre."
        )

    result["warnings"] = signals
    return result
