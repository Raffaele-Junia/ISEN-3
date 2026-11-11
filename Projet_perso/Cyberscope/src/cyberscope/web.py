"""Interface web CyberScope.

    uv run uvicorn cyberscope.web:app --reload
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from sqlite3 import Error as SQLiteError

from fastapi import FastAPI, Form, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .analyzer import anatomy, analyze
from .database import get_recent_analyses, get_report, init_db, save_report
from .net import is_valid_url, normalize_url
from .scoring import VERDICTS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PACKAGE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="CyberScope", description="Vérifie si un lien est sûr avant de cliquer.")
app.mount("/static", StaticFiles(directory=PACKAGE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=PACKAGE_DIR / "templates")
init_db()

EXAMPLES = (
    "https://www.impots.gouv.fr",
    "https://paypal-secure-login.com/verify",
    "https://bit.ly/3x",
)


def _relative_date(value: str) -> str:
    """« il y a 3 min », « hier », ou la date."""
    try:
        moment = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return value or ""
    seconds = (datetime.now(timezone.utc) - moment).total_seconds()
    if seconds < 60:
        return "à l'instant"
    if seconds < 3600:
        return f"il y a {int(seconds // 60)} min"
    if seconds < 86400:
        return f"il y a {int(seconds // 3600)} h"
    if seconds < 172800:
        return "hier"
    return moment.astimezone().strftime("%d/%m/%Y")


templates.env.filters["relative_date"] = _relative_date
templates.env.globals["anatomy"] = anatomy
templates.env.globals["verdict_labels"] = {key: label for key, (label, _) in VERDICTS.items()}


def _home(request: Request, *, url: str = "", error: str | None = None, status_code: int = 200):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"url": url, "error": error, "report": None, "examples": EXAMPLES},
        status_code=status_code,
    )


@app.get("/", response_class=HTMLResponse)
def home(request: Request, url: str = ""):
    return _home(request, url=url)


@app.post("/analyze")
def submit(request: Request, url: str = Form("")):
    url = normalize_url(url)
    if not is_valid_url(url):
        return _home(
            request,
            url=url,
            error="Cette adresse n'est pas un lien web valide. Colle un lien complet, par exemple https://exemple.fr/page.",
            status_code=400,
        )

    report = analyze(url)
    try:
        analysis_id = save_report(report)
    except SQLiteError:
        logger.exception("Impossible d'enregistrer l'analyse")
        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context={"url": url, "report": report, "error": None, "examples": EXAMPLES},
        )
    return RedirectResponse(f"/analyses/{analysis_id}", status_code=303)


@app.get("/analyses/{analysis_id}", response_class=HTMLResponse)
def report_page(request: Request, analysis_id: int):
    summary, report = get_report(analysis_id)
    if summary is None:
        return _home(request, error="Cette analyse n'existe pas ou a été supprimée.", status_code=404)

    if report is None:  # analyse enregistrée par l'ancienne version
        report = {
            "url": summary["url"],
            "final_url": summary["url"],
            "anatomy": anatomy(summary["url"]),
            "checked_at": summary["created_at"],
            "verdict": {
                "score": summary["risk_score"],
                "key": summary["verdict"],
                "label": VERDICTS[summary["verdict"]][0],
                "advice": "Analyse faite avec une ancienne version : le détail des contrôles n'a pas été conservé. Relance-la pour un rapport complet.",
                "reasons": json.loads(summary["risk_reasons"] or "[]"),
            },
            "checks": [],
        }

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"url": report["url"], "report": report, "error": None,
                 "analysis_id": analysis_id, "examples": EXAMPLES},
    )


@app.get("/history", response_class=HTMLResponse)
def history(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="history.html",
        context={"analyses": get_recent_analyses(limit=100)},
    )


@app.get("/history/{analysis_id}")
def legacy_history_detail(analysis_id: int):
    return RedirectResponse(f"/analyses/{analysis_id}", status_code=301)


@app.get("/api/check")
def api_check(url: str = Query(..., description="Lien à vérifier")):
    """Version JSON, pratique pour l'intégrer dans un script ou une extension."""
    url = normalize_url(url)
    if not is_valid_url(url):
        return JSONResponse({"error": "Lien invalide."}, status_code=400)
    return analyze(url)
