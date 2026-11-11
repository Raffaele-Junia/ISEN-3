"""Réputation du lien auprès de VirusTotal (URL, puis domaine en repli)."""

import base64
import os
from typing import Any

import requests
from dotenv import load_dotenv

from .checks import add_signal, failed, finalize, new_check
from .net import registrable_domain

load_dotenv()

BASE_URL = "https://www.virustotal.com/api/v3"
TIMEOUT = 15
TITLE = "Réputation"


class VirusTotalError(Exception):
    """Erreur renvoyée par le client VirusTotal."""


class NotFound(VirusTotalError):
    """VirusTotal ne connaît pas la ressource demandée."""


def _api_key() -> str | None:
    key = (os.getenv("VIRUSTOTAL_API_KEY") or "").strip()
    return key or None


def _get(path: str, api_key: str) -> dict[str, Any]:
    try:
        response = requests.get(
            f"{BASE_URL}{path}",
            headers={"x-apikey": api_key, "Accept": "application/json"},
            timeout=TIMEOUT,
        )
    except requests.RequestException as exc:
        raise VirusTotalError("VirusTotal est injoignable.") from exc

    if response.status_code == 404:
        raise NotFound()
    if response.status_code == 401:
        raise VirusTotalError("La clé API VirusTotal est refusée.")
    if response.status_code == 429:
        raise VirusTotalError("Quota VirusTotal atteint, réessaie dans une minute.")
    if not response.ok:
        raise VirusTotalError(f"VirusTotal a répondu HTTP {response.status_code}.")

    try:
        data = response.json()
    except ValueError as exc:
        raise VirusTotalError("Réponse VirusTotal illisible.") from exc
    return data.get("data", {}).get("attributes", {}) if isinstance(data, dict) else {}


def _url_id(url: str) -> str:
    return base64.urlsafe_b64encode(url.encode("utf-8")).decode("ascii").rstrip("=")


def _detection_risk(malicious: int, suspicious: int) -> int:
    """Un seul moteur isolé produit souvent des faux positifs : on reste mesuré."""
    if malicious >= 5:
        return 95
    if malicious >= 3:
        return 80
    if malicious == 2:
        return 55
    if malicious == 1:
        return 25
    return min(30, suspicious * 10)


def check_reputation(url: str, hostname: str) -> dict[str, Any]:
    try:
        return _check_reputation(url, hostname)
    except VirusTotalError as exc:
        return failed("reputation", TITLE, str(exc))


def _check_reputation(url: str, hostname: str) -> dict[str, Any]:
    check = new_check("reputation", TITLE)
    api_key = _api_key()

    if api_key is None:
        check["headline"] = (
            "Non vérifiée : ajoute une clé VIRUSTOTAL_API_KEY dans le fichier .env."
        )
        return check

    scope = "lien"
    try:
        attributes = _get(f"/urls/{_url_id(url)}", api_key)
    except NotFound:
        scope = "domaine"
        domain = registrable_domain(hostname)
        try:
            attributes = _get(f"/domains/{domain}", api_key)
        except NotFound:
            check["headline"] = "Ni ce lien ni son domaine ne sont connus de VirusTotal."
            check["facts"].append(["Base VirusTotal", "Aucune trace"])
            return check

    stats = attributes.get("last_analysis_stats") or {}
    malicious = int(stats.get("malicious", 0) or 0)
    suspicious = int(stats.get("suspicious", 0) or 0)
    harmless = int(stats.get("harmless", 0) or 0)
    undetected = int(stats.get("undetected", 0) or 0)
    engines = malicious + suspicious + harmless + undetected

    check["facts"] += [
        ["Analysé au niveau du", scope],
        ["Moteurs consultés", str(engines)],
        ["Malveillant", str(malicious)],
        ["Suspect", str(suspicious)],
        ["Sans détection", str(harmless + undetected)],
    ]

    if scope == "domaine":
        check["facts"].insert(0, ["Remarque", "Ce lien précis n'a jamais été analysé, résultat du domaine."])

    if malicious:
        add_signal(
            check,
            f"{malicious} antivirus sur {engines} classent ce {scope} comme malveillant.",
            _detection_risk(malicious, suspicious),
        )
    elif suspicious:
        add_signal(
            check,
            f"{suspicious} antivirus sur {engines} jugent ce {scope} suspect.",
            _detection_risk(0, suspicious),
        )

    if malicious >= 2:
        check["headline"] = f"Signalé comme malveillant par {malicious} antivirus."
    elif malicious == 1:
        check["headline"] = "Un seul antivirus le signale : possible faux positif."
    elif suspicious:
        check["headline"] = f"{suspicious} antivirus le jugent suspect."
    else:
        check["status"] = "ok"
        check["headline"] = f"Aucun des {engines} antivirus ne le signale."

    return finalize(check)
