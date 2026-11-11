"""Le lien imite-t-il un site connu ? Analyse de l'adresse elle-même, sans réseau.

C'est ici que se trouvent les arnaques les plus courantes en France :
faux colis (La Poste, Chronopost), fausse amende (ANTAI), faux remboursement
(Ameli, impôts) ou fausse alerte bancaire.
"""

from typing import Any
from urllib.parse import unquote, urlparse

from .checks import add_signal, finalize, new_check
from .net import registrable_domain

TITLE = "Imitation de marque"

# Marque -> domaines officiels.
BRANDS: dict[str, tuple[str, ...]] = {
    "paypal": ("paypal.com", "paypal.fr", "paypal.me"),
    "amazon": ("amazon.com", "amazon.fr", "amazon.de", "amazon.co.uk", "amazonaws.com"),
    "apple": ("apple.com", "icloud.com"),
    "icloud": ("icloud.com", "apple.com"),
    "microsoft": ("microsoft.com", "live.com", "office.com", "microsoftonline.com"),
    "outlook": ("outlook.com", "live.com", "office.com", "microsoft.com"),
    "google": ("google.com", "google.fr", "googleapis.com", "gstatic.com", "youtube.com"),
    "facebook": ("facebook.com", "fb.com", "meta.com"),
    "instagram": ("instagram.com",),
    "netflix": ("netflix.com",),
    "laposte": ("laposte.fr", "laposte.net", "labanquepostale.fr"),
    "colissimo": ("colissimo.fr", "laposte.fr"),
    "chronopost": ("chronopost.fr",),
    "ameli": ("ameli.fr",),
    "impots": ("impots.gouv.fr",),
    "antai": ("antai.gouv.fr",),
    "caf": ("caf.fr",),
    "franceconnect": ("franceconnect.gouv.fr",),
    "doctolib": ("doctolib.fr",),
    "creditagricole": ("credit-agricole.fr", "credit-agricole.com"),
    "bnpparibas": ("bnpparibas", "bnpparibas.com", "bnpparibas.fr"),
    "societegenerale": ("societegenerale.fr", "societegenerale.com"),
    "boursorama": ("boursorama.com", "boursobank.com"),
    "orange": ("orange.fr", "orange.com"),
    "vinted": ("vinted.fr", "vinted.com"),
    "leboncoin": ("leboncoin.fr",),
}

SENSITIVE_WORDS = (
    "login", "signin", "connexion", "verify", "verification", "verifier",
    "account", "compte", "password", "secure", "securite", "update",
    "confirm", "auth", "wallet", "paiement", "payment", "remboursement",
    "colis", "livraison", "amende", "facture", "suspendu", "bloque",
)

SHORTENERS = {
    "bit.ly", "tinyurl.com", "t.co", "goo.gl", "ow.ly", "is.gd", "buff.ly",
    "cutt.ly", "rebrand.ly", "shorturl.at", "tiny.cc", "rb.gy", "t.ly", "s.id",
}

# Extensions très utilisées pour des domaines jetables.
CHEAP_TLDS = {
    "xyz", "top", "click", "zip", "mov", "icu", "buzz", "rest", "cfd",
    "sbs", "monster", "quest", "live", "support", "help", "cyou", "lol",
}

# Noms de marque qui sont aussi des mots courants : on exige un mot exact.
AMBIGUOUS = {"orange", "google"}

HOMOGLYPHS = str.maketrans({"0": "o", "1": "l", "3": "e", "4": "a", "5": "s", "7": "t", "@": "a"})


def _distance(a: str, b: str) -> int:
    """Distance de Levenshtein (nombre de caractères à modifier)."""
    previous = list(range(len(b) + 1))
    for i, char_a in enumerate(a, 1):
        current = [i]
        for j, char_b in enumerate(b, 1):
            current.append(min(
                previous[j] + 1,
                current[j - 1] + 1,
                previous[j - 1] + (char_a != char_b),
            ))
        previous = current
    return previous[-1]


def _is_official(domain: str, brand: str) -> bool:
    return any(domain == official or domain.endswith("." + official) for official in BRANDS[brand])


def _imitated_brand(hostname: str, domain: str) -> tuple[str, str] | None:
    """Renvoie (marque, manière) si le nom d'hôte copie une marque sans en être."""
    tokens = hostname.replace("-", ".").split(".")
    labels = [label.replace("-", "") for label in hostname.split(".")]
    main_label = domain.split(".")[0]
    normalized = main_label.translate(HOMOGLYPHS).replace("rn", "m").replace("vv", "w")

    for brand in BRANDS:
        if _is_official(domain, brand) or _is_official(hostname, brand):
            continue
        # Mot exact ("paypal-secure.com") ou, pour les noms assez longs et peu
        # ambigus, inclus dans un mot ("ameliremboursement.com").
        found = brand in tokens or brand in labels or (
            len(brand) >= 6 and brand not in AMBIGUOUS
            and any(brand in label for label in labels)
        )
        if found:
            where = "dans le nom" if brand in main_label.replace("-", "") else "dans un sous-domaine"
            return brand, where
        if len(brand) >= 5 and main_label != brand and (
            normalized == brand or (len(brand) >= 6 and _distance(main_label, brand) == 1)
        ):
            return brand, "par une faute de frappe volontaire"
    return None


def check_link(url: str, final_url: str | None = None) -> dict[str, Any]:
    check = new_check("link", TITLE)
    urls = [url] + ([final_url] if final_url and final_url != url else [])

    for index, current in enumerate(urls):
        parsed = urlparse(current)
        hostname = (parsed.hostname or "").lower().rstrip(".")
        domain = registrable_domain(hostname)
        suffix = " (page d'arrivée)" if index else ""

        if index == 0 and domain in SHORTENERS:
            check["facts"].append(["Lien raccourci", f"oui, via {domain}"])

        imitation = _imitated_brand(hostname, domain)
        if imitation:
            brand, how = imitation
            official = BRANDS[brand][0]
            add_signal(
                check,
                f"Imite « {brand} » {how}, mais le vrai site est {domain}, pas {official}{suffix}.",
                70,
            )

        if "@" in parsed.netloc:
            add_signal(check, "Le caractère @ cache la vraie adresse du site.", 60)

        if hostname.startswith("xn--") or ".xn--" in hostname:
            add_signal(check, f"Le domaine utilise des caractères étrangers pouvant imiter des lettres latines{suffix}.", 35)

        if hostname.count(".") >= 4:
            add_signal(check, f"Nombre inhabituel de sous-domaines{suffix}.", 15)

        if hostname.count("-") >= 3:
            add_signal(check, f"Beaucoup de tirets dans le nom du site{suffix}.", 10)

        tld = domain.rsplit(".", 1)[-1]
        if tld in CHEAP_TLDS:
            add_signal(check, f"Extension .{tld}, très prisée des sites jetables{suffix}.", 15)

        decoded = unquote(current).lower()
        words = sorted({word for word in SENSITIVE_WORDS if word in decoded})
        if words:
            add_signal(
                check,
                "Mots typiques des arnaques dans le lien : " + ", ".join(words[:5]) + suffix + ".",
                10 + 5 * min(3, len(words)),
            )

        if len(current) > 200:
            add_signal(check, f"Lien anormalement long{suffix}.", 10)

    check["signals"].sort(key=lambda signal: signal["risk"], reverse=True)
    if not check["signals"]:
        check["status"] = "ok"
        check["headline"] = "L'adresse n'imite aucune marque connue."
    else:
        check["headline"] = (
            check["signals"][0]["text"] if check["signals"][0]["risk"] >= 50
            else f"{len(check['signals'])} détail(s) à vérifier dans l'adresse."
        )
    return finalize(check)
