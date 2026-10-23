import json
import logging
from pathlib import Path
from sqlite3 import Error as SQLiteError
from urllib.parse import urlparse

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from . import analyzer
from .database import (
    get_analysis_by_id,
    get_recent_analyses,
    init_db,
    save_analysis,
)
from .dns_analysis import analyze_dns
from .headers_analysis import analyze_headers
from .phishing_analysis import analyze_phishing
from .scoring import calculate_risk
from .tls_analysis import analyze_tls

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="CyberScope",
    description="Analyse de réputation et de sécurité des URL",
)

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
init_db()

AVAILABLE_MODULES = {
    "virustotal": "VirusTotal",
    "dns": "Analyse DNS et domaine",
    "tls": "Certificat HTTPS / TLS",
    "headers": "En-têtes HTTP",
    "phishing": "Signaux de phishing",
}


def is_valid_url(url: str) -> bool:
    """Vérifie la structure de base de l'URL."""
    try:
        parsed = urlparse(url)

        return (
            parsed.scheme in ("http", "https")
            and bool(parsed.hostname)
            and parsed.username is None
            and parsed.password is None
            and not any(char.isspace() for char in url)
            and parsed.port != 0
        )
    except ValueError:
        return False


def calculate_global_risk(
    selected_modules: list[str],
    modules_results: dict,
    vt_score: int | float | None,
) -> tuple[int | None, str, list[str]]:
    """
    Calcule un score heuristique CyberScope sur 100.

    Les modules en erreur ou sans résultats exploitables sont ignorés.
    Les poids sont normalisés selon les modules effectivement disponibles.
    """
    components: list[tuple[str, float, int]] = []
    reasons: list[str] = []

    # VirusTotal : le score existant est utilisé uniquement si
    # des statistiques réelles ont été récupérées.
    vt = modules_results.get("virustotal")

    if (
        "virustotal" in selected_modules
        and vt_score is not None
        and vt
        and vt.get("status") in ("success", "warning")
        and vt.get("details")
    ):
        components.append(("VirusTotal", float(vt_score), 65))

        details = vt["details"]
        malicious = int(details.get("Malveillants", 0) or 0)
        suspicious = int(details.get("Suspects", 0) or 0)

        if malicious:
            reasons.append(
                f"VirusTotal : {malicious} détection(s) malveillante(s)."
            )

        if suspicious:
            reasons.append(
                f"VirusTotal : {suspicious} détection(s) suspecte(s)."
            )

    # Phishing : indice heuristique de 0 à 10.
    phishing = modules_results.get("phishing")

    if (
        "phishing" in selected_modules
        and phishing
        and phishing.get("status") in ("success", "warning")
    ):
        details = phishing.get("details") or {}

        try:
            heuristic = float(details["Indice heuristique"])
            heuristic = max(0, min(10, heuristic))
            phishing_score = heuristic * 10

            components.append(("Phishing", phishing_score, 20))

            if heuristic > 0:
                reasons.append(
                    f"Phishing : indice heuristique de {heuristic:g}/10."
                )

        except (KeyError, TypeError, ValueError):
            logger.warning("Indice heuristique invalide : %r", details)

    # En-têtes HTTP : signal de configuration.
    headers = modules_results.get("headers")

    if (
        "headers" in selected_modules
        and headers
        and headers.get("status") in ("success", "warning")
    ):
        details = headers.get("details") or {}

        try:
            if "Nombre manquants" in details:
                missing = max(0, int(details["Nombre manquants"]))
                headers_score = min(40, missing * 8)

                components.append(("HTTP Headers", headers_score, 10))

                if missing:
                    reasons.append(
                        f"Configuration HTTP : {missing} en-tête(s) "
                        "de sécurité manquant(s)."
                    )

        except (TypeError, ValueError):
            logger.warning(
                "Nombre d'en-têtes manquants invalide : %r",
                details,
            )

    # TLS : évaluation de la date d'expiration si elle est connue.
    tls = modules_results.get("tls")

    if (
        "tls" in selected_modules
        and tls
        and tls.get("status") in ("success", "warning")
    ):
        details = tls.get("details") or {}
        days_value = details.get("Jours avant expiration")

        if days_value is not None:
            try:
                days = int(days_value)

                if days <= 0:
                    tls_score = 100
                    reasons.append(
                        "TLS : certificat expiré ou arrivant à échéance."
                    )
                elif days <= 7:
                    tls_score = 70
                    reasons.append(
                        f"TLS : certificat expirant dans {days} jour(s)."
                    )
                elif days <= 30:
                    tls_score = 35
                    reasons.append(
                        f"TLS : certificat expirant dans {days} jours."
                    )
                elif days <= 60:
                    tls_score = 15
                    reasons.append(
                        "TLS : certificat à surveiller, "
                        f"expiration dans {days} jours."
                    )
                else:
                    tls_score = 0

                components.append(("TLS", float(tls_score), 5))

            except (TypeError, ValueError):
                logger.warning(
                    "Date d'expiration TLS invalide : %r",
                    days_value,
                )

    # Aucun score ne doit être inventé si aucune donnée n'est exploitable.
    if not components:
        return (
            None,
            "Non évalué",
            [
                "Impossible de calculer un score avec les résultats disponibles."
            ],
        )

    total_weight = sum(weight for _, _, weight in components)

    score = round(
        sum(value * weight for _, value, weight in components)
        / total_weight
    )
    score = max(0, min(100, score))

    if score < 10:
        level = "Faible"
    elif score < 30:
        level = "Modéré"
    elif score < 60:
        level = "Élevé"
    else:
        level = "Critique"

    if not reasons:
        reasons.append(
            "Aucun signal de risque détecté par les contrôles exécutés. "
            "Cela ne garantit pas l'absence de menace."
        )

    return score, level, reasons


def render_home(
    request: Request,
    *,
    url: str = "",
    error: str | None = None,
    result: dict | None = None,
    modules_results: dict | None = None,
    selected_modules: list[str] | None = None,
    status_code: int = 200,
):
    """Affiche la page principale et ses résultats."""
    module_list = list((modules_results or {}).values())

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "url": url,
            "error": error,
            "result": result,
            "modules_results": module_list,
            "selected_modules": selected_modules or [],
            "available_modules": AVAILABLE_MODULES,
        },
        status_code=status_code,
    )


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return render_home(request)


@app.post("/analyze", response_class=HTMLResponse)
def analyze(
    request: Request,
    url: str = Form(...),
    modules: list[str] = Form(default=[]),
):
    url = url.strip()

    selected = list(
        dict.fromkeys(
            item for item in modules if item in AVAILABLE_MODULES
        )
    )

    if not is_valid_url(url):
        return render_home(
            request,
            url=url,
            error="URL invalide. Exemple : https://example.com",
            selected_modules=selected,
            status_code=400,
        )

    if not selected:
        return render_home(
            request,
            url=url,
            error="Sélectionne au moins un module d'analyse.",
            status_code=400,
        )

    hostname = urlparse(url).hostname
    modules_results: dict = {}

    # None signifie que les statistiques ne sont pas disponibles.
    # Un véritable 0 reste un résultat valide.
    result = {
        "malicious": None,
        "suspicious": None,
        "harmless": None,
        "undetected": None,
        "risk_score": None,
        "risk_level": "Non évalué",
        "risk_reasons": [],
    }

    # ---------------------------------------------------------
    # VirusTotal
    # ---------------------------------------------------------
    if "virustotal" in selected:
        try:
            report = analyzer.analyze_url(url)

            if not isinstance(report, dict):
                raise ValueError(
                    "La réponse VirusTotal n'est pas un objet JSON valide."
                )

            attributes = report.get("data", {}).get("attributes", {})
            stats = attributes.get("last_analysis_stats")

            expected_keys = (
                "malicious",
                "suspicious",
                "harmless",
                "undetected",
            )

            # Vérifie la présence réelle de statistiques.
            # Un dictionnaire rempli de zéros reste valide si les clés existent.
            stats_available = (
                isinstance(stats, dict)
                and any(key in stats for key in expected_keys)
            )

            if stats_available:
                result["malicious"] = int(stats.get("malicious", 0) or 0)
                result["suspicious"] = int(stats.get("suspicious", 0) or 0)
                result["harmless"] = int(stats.get("harmless", 0) or 0)
                result["undetected"] = int(stats.get("undetected", 0) or 0)

                vt_risk = calculate_risk(stats)

                modules_results["virustotal"] = {
                    "title": "Réputation VirusTotal",
                    "status": (
                        "warning"
                        if result["malicious"] or result["suspicious"]
                        else "success"
                    ),
                    "summary": (
                        f"{result['malicious']} détection(s) malveillante(s), "
                        f"{result['suspicious']} détection(s) suspecte(s)."
                    ),
                    "details": {
                        "Malveillants": result["malicious"],
                        "Suspects": result["suspicious"],
                        "Sans détection": result["harmless"],
                        "Non détectés": result["undetected"],
                    },
                    "warnings": vt_risk["reasons"],
                }

                vt_score = vt_risk["score"]

            else:
                logger.warning(
                    "VirusTotal n'a fourni aucune statistique exploitable "
                    "pour %s. Réponse reçue : %r",
                    url,
                    report,
                )

                modules_results["virustotal"] = {
                    "title": "Réputation VirusTotal",
                    "status": "info",
                    "summary": (
                        "Aucune statistique disponible. "
                        "La réponse ne contient pas de résultats "
                        "d'analyse exploitables."
                    ),
                    "details": {},
                    "warnings": [],
                }

                vt_score = None

        except Exception:
            logger.exception("Échec de l'analyse VirusTotal")

            modules_results["virustotal"] = {
                "title": "Réputation VirusTotal",
                "status": "error",
                "summary": (
                    "L'analyse VirusTotal a échoué. Vérifie la clé API, "
                    "les quotas, la connexion réseau et les journaux "
                    "du terminal."
                ),
                "details": {},
                "warnings": [],
            }

            vt_score = None

    else:
        vt_score = None

    # ---------------------------------------------------------
    # DNS
    # ---------------------------------------------------------
    if "dns" in selected:
        try:
            modules_results["dns"] = analyze_dns(hostname)
        except Exception:
            logger.exception("Échec de l'analyse DNS")

            modules_results["dns"] = {
                "title": "Analyse DNS et domaine",
                "status": "error",
                "summary": (
                    "Une erreur inattendue est survenue pendant l'analyse DNS."
                ),
                "details": {},
                "warnings": [],
            }

    # ---------------------------------------------------------
    # TLS
    # ---------------------------------------------------------
    if "tls" in selected:
        try:
            modules_results["tls"] = analyze_tls(url)
        except Exception:
            logger.exception("Échec de l'analyse TLS")

            modules_results["tls"] = {
                "title": "Certificat HTTPS / TLS",
                "status": "error",
                "summary": (
                    "Une erreur inattendue est survenue pendant l'analyse TLS."
                ),
                "details": {},
                "warnings": [],
            }

    # ---------------------------------------------------------
    # En-têtes HTTP
    # ---------------------------------------------------------
    if "headers" in selected:
        try:
            modules_results["headers"] = analyze_headers(url)
        except Exception:
            logger.exception("Échec de l'audit HTTP")

            modules_results["headers"] = {
                "title": "Audit des en-têtes HTTP",
                "status": "error",
                "summary": (
                    "Une erreur inattendue est survenue pendant l'audit HTTP."
                ),
                "details": {},
                "warnings": [],
            }

    # ---------------------------------------------------------
    # Signaux heuristiques de phishing
    # ---------------------------------------------------------
    if "phishing" in selected:
        try:
            modules_results["phishing"] = analyze_phishing(url)
        except Exception:
            logger.exception("Échec de l'analyse heuristique")

            modules_results["phishing"] = {
                "title": "Détection de signaux de phishing",
                "status": "error",
                "summary": "Une erreur inattendue est survenue.",
                "details": {},
                "warnings": [],
            }

    # ---------------------------------------------------------
    # Calcul du score global
    # ---------------------------------------------------------
    global_score, global_level, global_reasons = calculate_global_risk(
        selected_modules=selected,
        modules_results=modules_results,
        vt_score=vt_score,
    )

    result["risk_score"] = global_score
    result["risk_level"] = global_level
    result["risk_reasons"] = global_reasons

    # ---------------------------------------------------------
    # Sauvegarde en base
    # ---------------------------------------------------------
    # La base existante attend des nombres : les statistiques absentes
    # sont stockées sous forme de 0 pour compatibilité.
    # Dans la page actuelle, elles restent affichées comme N/A.
    try:
        save_analysis(
            url=url,
            risk_score=global_score if global_score is not None else 0,
            risk_level=global_level,
            malicious=result["malicious"] or 0,
            suspicious=result["suspicious"] or 0,
            harmless=result["harmless"] or 0,
            undetected=result["undetected"] or 0,
            risk_reasons=global_reasons,
        )
    except SQLiteError:
        logger.exception(
            "Impossible d'enregistrer l'analyse dans SQLite"
        )

    return render_home(
        request,
        url=url,
        result=result,
        modules_results=modules_results,
        selected_modules=selected,
    )


@app.get("/history", response_class=HTMLResponse)
def history(request: Request):
    analyses = get_recent_analyses(limit=100)

    return templates.TemplateResponse(
        request=request,
        name="history.html",
        context={"analyses": analyses},
    )


@app.get("/history/{analysis_id}", response_class=HTMLResponse)
def history_detail(request: Request, analysis_id: int):
    record = get_analysis_by_id(analysis_id)

    if record is None:
        return render_home(
            request,
            error="Cette analyse n'existe pas dans l'historique.",
            status_code=404,
        )

    result = {
        "malicious": record["malicious"],
        "suspicious": record["suspicious"],
        "harmless": record["harmless"],
        "undetected": record["undetected"],
        "risk_score": record["risk_score"],
        "risk_level": record["risk_level"],
        "risk_reasons": json.loads(record["risk_reasons"]),
    }

    return render_home(
        request,
        url=record["url"],
        result=result,
        error=(
            "Résumé enregistré. Les détails des modules ne sont pas encore "
            "conservés dans l'historique."
        ),
    )