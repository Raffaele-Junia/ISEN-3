
import os
import base64
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://www.virustotal.com/api/v3"
TIMEOUT = 15


class VirusTotalError(Exception):
    """Erreur renvoyée par le client VirusTotal."""


def _headers() -> dict[str, str]:
    api_key = os.getenv("VIRUSTOTAL_API_KEY")

    if not api_key:
        raise VirusTotalError(
            "Clé API VirusTotal non définie. Vérifie ton fichier .env."
        )

    return {
        "x-apikey": api_key.strip(),
        "Accept": "application/json",
    }


def get(
    path: str,
    params: dict[str, Any] | None = None
) -> dict[str, Any]:
    url = f"{BASE_URL}{path}"

    try:
        response = requests.get(
            url,
            headers=_headers(),
            params=params,
            timeout=TIMEOUT,
        )
    except requests.RequestException as exc:
        raise VirusTotalError(f"Erreur réseau : {exc}") from exc

    if response.status_code == 401:
        raise VirusTotalError(
            "Clé API invalide (HTTP 401). Vérifie ta clé dans VirusTotal."
        )
    if response.status_code == 403:
        raise VirusTotalError(
            "Accès refusé (HTTP 403). Vérifie les droits de ton compte."
        )
    if response.status_code == 429:
        raise VirusTotalError(
            "Limite de requêtes atteinte (HTTP 429)."
        )

    if not response.ok:
        try:
            detail = response.json()
        except ValueError:
            detail = response.text

        raise VirusTotalError(
            f"Erreur API HTTP {response.status_code} : {detail}"
        )

    try:
        data = response.json()
    except ValueError as exc:
        raise VirusTotalError("Réponse JSON invalide.") from exc

    if not isinstance(data, dict):
        raise VirusTotalError("Format de réponse inattendu.")

    return data


def get_url_analysis(url: str) -> dict[str, Any]:
    """Récupère le rapport VirusTotal existant d'une URL."""
    id = (
        base64.urlsafe_b64encode(url.encode("utf-8"))
        .decode("ascii")
        .rstrip("=")
    )

    return get(f"/urls/{id}")
