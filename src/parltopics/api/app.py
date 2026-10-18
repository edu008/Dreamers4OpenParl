"""Web-App und Sidecar-API (PRD 7.5, F10, F13, F20; ADR 0006).

Die Web-App ist eine React-SPA aus web/. FastAPI liefert ihren Build aus web/dist aus: Dateien
direkt, alle übrigen Pfade ausserhalb von /v1 als index.html, damit die Routen der SPA (z. B.
/tags/aps:6.1.9) auch beim Neuladen funktionieren. Ohne Build zeigt die App eine Hinweisseite.

Die interaktive API-Dokumentation von FastAPI ist abgeschaltet, weil sie Skripte von einem CDN
lädt (PRD 9, Offline). Das OpenAPI-Schema bleibt unter /v1/openapi.json erreichbar.
"""

from pathlib import Path

from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

from parltopics import __version__
from parltopics.config import Settings, get_settings
from parltopics.registry import RegistryError, load_registry
from parltopics.wiki.tree import TreeError, build_tree, page_ids

ASSET_CACHE = "public, max-age=31536000, immutable"  # Dateinamen in assets/ tragen einen Hash

NO_BUILD_PAGE = """<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>ParlTopics</title>
  <style>
    body { font-family: system-ui, sans-serif; max-width: 40rem; margin: 3rem auto; padding: 0 1rem;
           line-height: 1.5; color: #1f2933; }
    code { background: #f1f3f5; padding: 0.1rem 0.3rem; border-radius: 0.25rem; }
  </style>
</head>
<body>
  <h1>ParlTopics</h1>
  <p>Die Web-App ist noch nicht gebaut. Mit <code>make web-build</code> entsteht
     <code>web/dist</code>; für die Entwicklung startet <code>make web-dev</code> Vite.</p>
  <ul>
    <li><a href="/healthz">Health-Check</a></li>
    <li><a href="/v1/pages">Seitenbaum (JSON)</a></li>
    <li><a href="/v1/openapi.json">OpenAPI-Schema</a></li>
  </ul>
</body>
</html>
"""


class PageOut(BaseModel):
    page_id: str
    kind: str
    title: str
    path: str
    parent_id: str | None
    linked_from: list[str]


class PageTree(BaseModel):
    registry_version: str
    pages: list[PageOut]


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(
        title="ParlTopics",
        version=__version__,
        docs_url=None,
        redoc_url=None,
        openapi_url="/v1/openapi.json",
    )
    api = APIRouter(prefix="/v1")

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    @api.get("/pages")
    def pages() -> PageTree:
        """Seitenbaum aus der Registry: Heart, Bereiche, Kapitel, Tag- und Querschnittsseiten.

        Status, Kennzahlen und Zusammenfassungen kommen mit wiki_pages in Meilenstein M3 dazu.
        """
        try:
            registry = load_registry(settings.registry_path)
            tree = build_tree(registry)
        except (RegistryError, TreeError) as error:
            raise HTTPException(503, f"Seitenbaum nicht verfügbar: {error}") from error
        return PageTree(
            registry_version=registry.registry_version,
            pages=[
                PageOut(
                    page_id=page.page_id,
                    kind=page.kind,
                    title=page.title,
                    path=page.path,
                    parent_id=page.parent_id,
                    linked_from=list(page.linked_from),
                )
                for page in (tree[page_id] for page_id in page_ids(tree.values()))
            ],
        )

    app.include_router(api)
    add_web(app, settings.web_dist_dir)
    return app


def add_web(app: FastAPI, dist: Path) -> None:
    """Liefert die SPA aus. Muss als letzte Route registriert werden (fängt alle Pfade)."""

    @app.api_route("/{path:path}", methods=["GET", "HEAD"], include_in_schema=False)
    def web(path: str):
        if path == "v1" or path.startswith("v1/"):
            raise HTTPException(404, "Unbekannter API-Pfad")
        root = dist.resolve()
        index = root / "index.html"
        if not index.is_file():
            return HTMLResponse(NO_BUILD_PAGE)
        try:
            candidate = (root / path).resolve()
        except (OSError, ValueError):
            raise HTTPException(404, "Ungültiger Pfad") from None
        if path and candidate.is_relative_to(root) and candidate.is_file():
            headers = {"Cache-Control": ASSET_CACHE} if path.startswith("assets/") else None
            return FileResponse(candidate, headers=headers)
        if path.startswith("assets/"):
            raise HTTPException(404, "Datei nicht gefunden")
        return FileResponse(index, headers={"Cache-Control": "no-cache"})


app = create_app()
