import requests
import sys
import os
from dotenv import load_dotenv

load_dotenv()


def main():
    if len(sys.argv) != 2:
        sys.exit(
            "Missing command-line argument"
            if len(sys.argv) < 2
            else "Too many arguments"
        )

    try:
        amount = float(sys.argv[1])
    except ValueError:
        sys.exit("Command-line argument is not a number")

    api_key = os.getenv("APIKEY")

    if not api_key:
        sys.exit("Missing API key in .env")

    try:
        response = requests.get(
            "https://rest.coincap.io/v3/assets/bitcoin",
            params={"apiKey": api_key},
            timeout=10,
        )
        response.raise_for_status()

        data = response.json()["data"]
        price = float(data["priceUsd"])

        print(f"${amount * price:,.4f}")

    except (requests.RequestException, KeyError, ValueError):
        sys.exit("Could not retrieve Bitcoin price")


if __name__ == "__main__":
    main()
