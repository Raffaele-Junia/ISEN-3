
"""Client HTTP pour l'API CarVector."""

import os
from typing import Any
from urllib.parse import quote
from .config import get_api_key

import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://api.carvector.io/v1"
TIMEOUT = 15


class CarVectorError(Exception):
    """Erreur renvoyée par le client CarVector."""


def _headers() -> dict[str, str]:
    api_key = get_api_key()

    return {
        "Authorization": f"Bearer {api_key}",
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
            timeout=TIMEOUT
        )
    except requests.RequestException as exc:
        raise CarVectorError(f"Erreur réseau : {exc}") from exc

    if response.status_code == 401:
        raise CarVectorError("Clé API invalide (HTTP 401).")

    if response.status_code == 402:
        raise CarVectorError("Accès ou paiement requis (HTTP 402).")

    if response.status_code == 429:
        raise CarVectorError("Limite de requêtes atteinte (HTTP 429).")

    if not response.ok:
        try:
            detail = response.json()
        except ValueError:
            detail = response.text

        raise CarVectorError(
            f"Erreur API HTTP {response.status_code} : {detail}"
        )

    try:
        data = response.json()
    except ValueError as exc:
        raise CarVectorError("Réponse JSON invalide.") from exc

    if not isinstance(data, dict):
        raise CarVectorError("Format de réponse inattendu.")

    if data.get("error"):
        raise CarVectorError(f"Erreur CarVector : {data['error']}")

    return data


def search_vehicles(
    *,
    make: str | None = None,
    model: str | None = None,
    year: int | None = None,
    limit: int = 10
) -> dict[str, Any]:
    params: dict[str, Any] = {
        "limit": max(1, min(limit, 100))
    }

    if make:
        params["make"] = make

    if model:
        params["model"] = model

    if year is not None:
        params["year"] = year

    return get("/vehicles", params=params)


def get_vehicle(vehicle_id: str) -> dict[str, Any]:
    vehicle_id = quote(vehicle_id, safe="")
    return get(f"/vehicles/{vehicle_id}")


def get_recalls(vehicle_id: str) -> dict[str, Any]:
    vehicle_id = quote(vehicle_id, safe="")
    return get(f"/vehicles/{vehicle_id}/recalls")


def lookup_dtc(code: str) -> dict[str, Any]:
    code = quote(code.strip().upper(), safe="")
    return get(f"/dtc/{code}")
