"""Combine les contrôles en un verdict unique.

Une moyenne pondérée « dilue » un signal fort : un domaine créé hier noyé au
milieu de quatre contrôles verts donnerait un score rassurant. On combine donc
les risques comme des probabilités indépendantes :

    risque = 1 - Π (1 - confiance_i × risque_i)

Chaque signal ne peut qu'augmenter le score, jamais le faire baisser.
"""

from typing import Any

# Confiance accordée à chaque contrôle (1 = signal très fiable).
CONFIDENCE = {
    "reputation": 1.0,
    "link": 0.9,
    "domain": 0.85,
    "combo": 1.0,
    "tls": 0.8,
    "destination": 0.7,
}

VERDICTS = {
    "safe": (
        "Aucun signal inquiétant",
        "Rien d'anormal n'a été trouvé. Reste vigilant si la page te demande "
        "des informations personnelles ou bancaires.",
    ),
    "caution": (
        "Prudence",
        "Certains signaux appellent à la méfiance. Vérifie qui t'a envoyé ce "
        "lien avant d'y saisir quoi que ce soit.",
    ),
    "danger": (
        "Lien dangereux",
        "Plusieurs signaux forts : n'ouvre pas ce lien et ne saisis aucune "
        "information dessus.",
    ),
    "unknown": (
        "Non évalué",
        "Aucun contrôle n'a pu aboutir. Vérifie l'adresse et ta connexion, "
        "puis relance l'analyse.",
    ),
}


def combined_risk(risks: list[tuple[str, int]]) -> int:
    remaining = 1.0
    for check_id, risk in risks:
        remaining *= 1 - CONFIDENCE.get(check_id, 0.8) * risk / 100
    return round((1 - remaining) * 100)


def verdict_for(score: int | None) -> str:
    if score is None:
        return "unknown"
    if score >= 50:
        return "danger"
    if score >= 20:
        return "caution"
    return "safe"


def build_verdict(checks: list[dict[str, Any]]) -> dict[str, Any]:
    signals: list[tuple[str, dict[str, Any]]] = [
        (check["id"], signal) for check in checks for signal in check["signals"]
    ]
    evaluated = [check for check in checks if check["risk"] is not None]

    score = combined_risk([(cid, s["risk"]) for cid, s in signals]) if evaluated else None
    key = verdict_for(score)
    label, advice = VERDICTS[key]

    reasons = [
        signal["text"]
        for _, signal in sorted(signals, key=lambda item: item[1]["risk"], reverse=True)
        if signal["risk"] >= 10
    ][:5]

    return {
        "score": score,
        "key": key,
        "label": label,
        "advice": advice,
        "reasons": reasons,
    }
