
from typing import Any

from . import api_client


def analyze_url(url: str) -> dict[str, Any]:
    """Récupère le rapport VirusTotal d'une URL.

    Args:
        url: URL à analyser.

    Returns:
        Les données retournées par VirusTotal.

    Raises:
        RuntimeError: Si la requête échoue.
    """
    try:
        return api_client.get_url_analysis(url)
    except api_client.VirusTotalError as e:
        raise RuntimeError(
            f"Erreur lors de l'analyse de l'URL : {e}"
        ) from e


def display_analyse(url: str) -> None:
    """Affiche les statistiques du rapport VirusTotal."""
    try:
        result = analyze_url(url)

        data = result.get("data", {})
        attributes = data.get("attributes", {})
        stats = attributes.get("last_analysis_stats", {})

        if not stats:
            print(f"\nAucune statistique d'analyse disponible pour : {url}")
            print("Le rapport peut être absent ou ne pas contenir ces données.")
            return

        malicious = stats.get("malicious", 0)
        suspicious = stats.get("suspicious", 0)
        harmless = stats.get("harmless", 0)
        undetected = stats.get("undetected", 0)

        print(f"\nAnalyse de : {url}")
        print("-" * 40)
        print(f"Malveillants : {malicious}")
        print(f"Suspects     : {suspicious}")
        print(f"Inoffensifs  : {harmless}")
        print(f"Non détectés : {undetected}")

        if malicious > 0:
            print("\nATTENTION : des moteurs signalent cette URL comme malveillante.")
        elif suspicious > 0:
            print("\nPrudence : des moteurs signalent cette URL comme suspecte.")
        else:
            print("\nAucune détection malveillante ou suspecte dans ces statistiques.")

        print("\nCes résultats ne garantissent pas que l'URL est sûre.")

    except RuntimeError as e:
        print(f"\nErreur : {e}")
