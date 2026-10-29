import requests
import sys

def main():
    if len(sys.argv) != 2:
        sys.exit("Missing command-line argument" if len(sys.argv) < 2 else "Too many arguments")

    try:
        amount = float(sys.argv[1])
    except ValueError:
        sys.exit("Command-line argument is not a number")

    try:
        response = requests.get(
            "https://rest.coincap.io/v3/assets/bitcoin?apiKey=6739516a4c303c61487a4a1445c90d0cb7281e76a211a8319d63f099509246b6"
        )
        response.raise_for_status()
        data = response.json()["data"]
        price = float(data["priceUsd"])
        trade = amount * price
        print(f"${trade:,.4f}")

    except (requests.RequestException, KeyError, ValueError):
        sys.exit("Could not retrieve Bitcoin price")
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    main()
