
from typing import Any


def calculate_risk(stats: dict[str, Any]) -> dict[str, Any]:
    """Calcule un indicateur de risque à partir des statistiques."""

    malicious = int(stats.get("malicious", 0))
    suspicious = int(stats.get("suspicious", 0))

    reasons = []

    # Score heuristique, et non probabilité réelle.
    score = min(100, malicious * 15 + suspicious * 5)

    if malicious > 0:
        reasons.append(
            f"{malicious} moteur(s) signalent une détection malveillante."
        )

    if suspicious > 0:
        reasons.append(
            f"{suspicious} moteur(s) signalent un résultat suspect."
        )

    if malicious >= 5:
        level = "Critique"
    elif malicious > 0:
        level = "Élevé"
    elif suspicious >= 3:
        level = "Modéré"
    elif suspicious > 0:
        level = "Faible"
    else:
        level = "Aucun signal détecté"

    if not reasons:
        reasons.append(
            "Aucune détection malveillante ou suspecte dans les statistiques disponibles."
        )

    return {
        "score": score,
        "level": level,
        "reasons": reasons,
    }
