from typing import Any

from . import api_client


def search_vehicles(
    make: str | None = None,
    model: str | None = None,
    year: int | None = None
) -> list[dict[str, Any]]:
    data = api_client.search_vehicles(
        make=make,
        model=model,
        year=year,
        limit=10
    )

    results = data.get("results", [])
    return results if isinstance(results, list) else []


def get_vehicle_details(vehicle_id: str) -> dict[str, Any]:
    return api_client.get_vehicle(vehicle_id)


def compare_vehicles(
    first_id: str,
    second_id: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    first = get_vehicle_details(first_id)
    second = get_vehicle_details(second_id)

    return first, second


def display_vehicle(vehicle: dict[str, Any]) -> None:
    title = " ".join(
        str(vehicle.get(key, ""))
        for key in ("year", "make", "model")
    ).strip()

    print(f"\n{title or 'Véhicule sans nom'}")
    print(f"ID             : {vehicle.get('id', '—')}")
    print(f"Puissance      : {vehicle.get('horsepower', '—')} ch")
    print(f"Cylindrée      : {vehicle.get('displacement_l', '—')} L")
    print(f"Cylindres      : {vehicle.get('cylinders', '—')}")
    print(f"Transmission   : {vehicle.get('transmission', '—')}")
    print(f"Motricité      : {vehicle.get('drive_type', '—')}")
    print(f"Carburant      : {vehicle.get('fuel_type', '—')}")
    print(f"Rappels connus : {vehicle.get('recall_count', '—')}")


def display_comparison(
    first: dict[str, Any],
    second: dict[str, Any]
) -> None:
    fields = [
        ("Véhicule", lambda v: f"{v.get('year', '')} {v.get('make', '')} {v.get('model', '')}".strip()),
        ("Puissance (ch)", lambda v: v.get("horsepower", "—")),
        ("Cylindrée (L)", lambda v: v.get("displacement_l", "—")),
        ("Cylindres", lambda v: v.get("cylinders", "—")),
        ("Transmission", lambda v: v.get("transmission", "—")),
        ("Motricité", lambda v: v.get("drive_type", "—")),
        ("Carburant", lambda v: v.get("fuel_type", "—")),
        ("Rappels connus", lambda v: v.get("recall_count", "—")),
    ]

    print("\nComparaison")
    print(f"{'Caractéristique':<20} | {'Véhicule 1':<28} | Véhicule 2")
    print("-" * 78)

    for label, getter in fields:
        print(
            f"{label:<20} | "
            f"{str(getter(first)):<28} | "
            f"{getter(second)}"
        )
