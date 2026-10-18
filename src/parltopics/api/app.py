"""Web-App und Sidecar-API. Im Skelett: Startseite und Health-Check (PRD 7.5, F10).

Die interaktive API-Dokumentation von FastAPI ist abgeschaltet, weil sie Skripte von einem CDN
lädt (PRD 9, Offline). Das OpenAPI-Schema bleibt unter /v1/openapi.json erreichbar.
"""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from parltopics import __version__

HERE = Path(__file__).parent

app = FastAPI(
    title="ParlTopics",
    version=__version__,
    docs_url=None,
    redoc_url=None,
    openapi_url="/v1/openapi.json",
)
app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")
templates = Jinja2Templates(directory=HERE / "templates")


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "index.html", {"version": __version__})
