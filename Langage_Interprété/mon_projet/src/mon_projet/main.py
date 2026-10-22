
import argparse

from . import api_client, diagnostics, vehicles


def main():
    parser = argparse.ArgumentParser(
        description="AutoScope - Explorateur automobile avec CarVector"
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True
    )

    search_parser = subparsers.add_parser(
        "search",
        help="Rechercher un véhicule"
    )
    search_parser.add_argument("--make", help="Marque du véhicule")
    search_parser.add_argument("--model", help="Modèle du véhicule")
    search_parser.add_argument("--year", type=int, help="Année du véhicule")

    details_parser = subparsers.add_parser(
        "details",
        help="Afficher les détails d'un véhicule"
    )
    details_parser.add_argument("vehicle_id", help="Identifiant du véhicule")

    compare_parser = subparsers.add_parser(
        "compare",
        help="Comparer deux véhicules"
    )
    compare_parser.add_argument("first_id", help="ID du premier véhicule")
    compare_parser.add_argument("second_id", help="ID du second véhicule")

    recalls_parser = subparsers.add_parser(
        "recalls",
        help="Consulter les rappels d'un véhicule"
    )
    recalls_parser.add_argument("vehicle_id", help="Identifiant du véhicule")

    dtc_parser = subparsers.add_parser(
        "dtc",
        help="Rechercher un code de diagnostic OBD-II"
    )
    dtc_parser.add_argument("code", help="Code OBD-II, par exemple P0420")

    args = parser.parse_args()

    try:
        if args.command == "search":
            results = vehicles.search_vehicles(
                make=args.make,
                model=args.model,
                year=args.year
            )

            if not results:
                print("Aucun véhicule trouvé.")
                return

            for vehicle in results:
                print(
                    f"{vehicle.get('id', '—')} | "
                    f"{vehicle.get('year', '')} "
                    f"{vehicle.get('make', '')} "
                    f"{vehicle.get('model', '')}"
                )

        elif args.command == "details":
            vehicle = vehicles.get_vehicle_details(args.vehicle_id)
            vehicles.display_vehicle(vehicle)

        elif args.command == "compare":
            first, second = vehicles.compare_vehicles(
                args.first_id,
                args.second_id
            )
            vehicles.display_comparison(first, second)

        elif args.command == "recalls":
            data = diagnostics.get_recalls(args.vehicle_id)
            diagnostics.display_recalls(data)

        elif args.command == "dtc":
            data = diagnostics.lookup_dtc(args.code)
            diagnostics.display_dtc(data)

    except api_client.CarVectorError as exc:
        parser.exit(1, f"Erreur : {exc}\n")


if __name__ == "__main__":
    main()
