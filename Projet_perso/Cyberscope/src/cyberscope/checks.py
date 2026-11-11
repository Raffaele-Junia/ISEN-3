"""Format commun renvoyé par chaque contrôle."""

from typing import Any

# ok      : rien d'inquiétant
# warn    : à surveiller
# danger  : signal fort
# neutral : information sans jugement (contrôle non applicable, donnée absente)
# error   : le contrôle n'a pas pu s'exécuter
STATUSES = ("ok", "warn", "danger", "neutral", "error")


def new_check(check_id: str, title: str) -> dict[str, Any]:
    return {
        "id": check_id,
        "title": title,
        "status": "neutral",
        "headline": "",
        "facts": [],      # [libellé, valeur] affichés dans le détail
        "signals": [],    # {"text": str, "risk": int 0-100}
        "risk": None,     # None = le contrôle ne contribue pas au verdict
    }


def add_signal(check: dict[str, Any], text: str, risk: int) -> None:
    check["signals"].append({"text": text, "risk": max(0, min(100, risk))})


def finalize(check: dict[str, Any]) -> dict[str, Any]:
    """Déduit le risque et le statut à partir des signaux, si non fixés."""
    if check["status"] == "error":
        return check

    if check["signals"]:
        top = max(signal["risk"] for signal in check["signals"])
        check["risk"] = top if check["risk"] is None else max(check["risk"], top)
    elif check["risk"] is None and check["status"] != "neutral":
        check["risk"] = 0

    if check["status"] in ("ok", "neutral") and check["risk"] is not None:
        if check["risk"] >= 50:
            check["status"] = "danger"
        elif check["risk"] >= 15:
            check["status"] = "warn"
        elif check["signals"]:
            check["status"] = "ok"   # signaux mineurs seulement

    check["signals"].sort(key=lambda signal: signal["risk"], reverse=True)
    return check


def failed(check_id: str, title: str, message: str) -> dict[str, Any]:
    check = new_check(check_id, title)
    check["status"] = "error"
    check["headline"] = message
    return check
