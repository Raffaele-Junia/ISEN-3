
import os
from pathlib import Path
from getpass import getpass

from dotenv import load_dotenv

# Dossier racine du projet
PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / ".env"

load_dotenv(ENV_FILE)


def get_api_key() -> str:
    """Récupère ou demande la clé API de l'utilisateur."""
    api_key = os.getenv("CARVECTOR_API_KEY", "").strip()

    if api_key:
        return api_key

    print("Aucune clé API CarVector configurée.")
    print("Récupère ta clé depuis le site CarVector.")

    api_key = getpass("Entre ta clé API : ").strip()

    if not api_key:
        raise ValueError("La clé API ne peut pas être vide.")

    # Crée le fichier .env s'il n'existe pas
    with ENV_FILE.open("a", encoding="utf-8") as file:
        file.write(f"\nCARVECTOR_API_KEY={api_key}\n")

    os.environ["CARVECTOR_API_KEY"] = api_key

    print("Clé API enregistrée localement.")
    return api_key
