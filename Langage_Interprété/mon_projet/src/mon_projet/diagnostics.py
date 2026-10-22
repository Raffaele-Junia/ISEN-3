
"""Fonctions liées aux rappels et aux codes OBD-II."""

from typing import Any

from . import api_client


def get_recalls(vehicle_id: str) -> dict[str, Any]:
    return api_client.get_recalls(vehicle_id)


def lookup_dtc(code: str) -> dict[str, Any]:
    return api_client.lookup_dtc(code)


def display_recalls(data: dict[str, Any]) -> None:
    recalls = data.get("recalls", [])

    print(
        f"\nNombre de rappels trouvés : "
        f"{data.get('count', len(recalls))}"
    )

    if not recalls:
        print("Aucun rappel listé dans la réponse de l'API.")
        return

    for index, recall in enumerate(recalls, start=1):
        print(
            f"\n{index}. "
            f"{recall.get('campaign_id', 'Campagne inconnue')} "
            f"— {recall.get('component', 'Composant non précisé')}"
        )

        print(f"   Problème : {recall.get('summary', 'Non précisé')}")
        print(f"   Risque   : {recall.get('consequence', 'Non précisé')}")
        print(f"   Solution : {recall.get('remedy', 'Non précisée')}")


def display_dtc(data: dict[str, Any]) -> None:
    print(f"\nCode : {data.get('code', '—')}")

    print(
        "Signification : "
        f"{data.get('title', 'Aucune description disponible')}"
    )

    print(f"Catégorie : {data.get('category', '—')}")
    print(f"Gravité : {data.get('severity', '—')}")

    safety_risk = data.get("safety_risk")
    emissions_related = data.get("emissions_related")

    print(f"Risque sécurité : {safety_risk if safety_risk is not None else 'Non renseigné'}")
    print(f"Lié aux émissions : {emissions_related if emissions_related is not None else 'Non renseigné'}")

    print(
        "\nAttention : ces informations sont indicatives "
        "et ne remplacent pas un diagnostic mécanique."
    )
