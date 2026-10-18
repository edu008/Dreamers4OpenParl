"""Web-App und Sidecar-API (PRD 7.5, F10, F13, F20; ADR 0006).

Die Web-App ist eine React-SPA aus web/. FastAPI liefert ihren Build aus web/dist aus: Dateien
direkt, alle übrigen Pfade ausserhalb von /v1 als index.html, damit die Routen der SPA (z. B.
/tags/aps:6.1.9) auch beim Neuladen funktionieren. Ohne Build zeigt die App eine Hinweisseite.

Die API-Dokumentation (Swagger UI) liegt unter /v1/docs. Skripte und Stile kommen aus dem Paket,
nicht von einem CDN (PRD 9, Offline); FastAPIs Standardseiten /docs und /redoc bleiben aus. Das
OpenAPI-Schema steht unter /v1/openapi.json.
"""

from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path
from threading import Lock
from typing import Annotated, Literal

import psycopg
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from psycopg_pool import ConnectionPool, PoolClosed, PoolTimeout

from parltopics import __version__
from parltopics.api import queries
from parltopics.api.schemas import (
    AffairTopics,
    JobCounts,
    JobsSummary,
    Lang,
    PageDetail,
    PageOut,
    PageTree,
    TopicAffairs,
    TopicOut,
)
from parltopics.classify.queue import summary as job_summary
from parltopics.config import Settings, get_settings
from parltopics.registry import Registry, RegistryError, load_registry
from parltopics.wiki.tree import (
    Page,
    TreeError,
    ancestors,
    build_tree,
    children,
    linked_querschnitt,
    page_ids,
)

ASSET_CACHE = "public, max-age=31536000, immutable"  # Dateinamen in assets/ tragen einen Hash
SWAGGER = Path(__file__).parent / "static" / "swagger"  # swagger-ui-dist, Apache-2.0

DESCRIPTION = """Sidecar-API von ParlTopics (PRD F10): Themen zu Geschäften aus OpenParlData,
klassifiziert mit Apertus. Geschäfts-IDs sind OpenParlData-IDs. Alle Endpunkte lesen nur.

Ohne Datenbank antworten die Endpunkte unter Geschäfte, Themen und Jobs mit 503;
/healthz und die Seiten unter /v1/pages funktionieren weiter."""

TAGS = [
    {"name": "Geschäfte", "description": "Ein Geschäft mit seinen Themen, Belegen und Versionen."},
    {"name": "Themen", "description": "Tags der Registry (APS und Ad-hoc) und ihre Geschäfte."},
    {"name": "Jobs", "description": "Stand der Klassifikation je Aufgabe."},
    {"name": "Seiten", "description": "Seitenbaum des ParlWiki."},
    {"name": "System", "description": "Betrieb."},
]

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
    <li><a href="/v1/docs">API-Dokumentation (Swagger UI)</a></li>
    <li><a href="/v1/pages">Seitenbaum (JSON)</a></li>
    <li><a href="/v1/openapi.json">OpenAPI-Schema</a></li>
  </ul>
</body>
</html>
"""

LangQuery = Annotated[Lang, Query(description="Sprache der Titel, sonst Deutsch")]


def page_out(page: Page, lang: Lang) -> PageOut:
    return PageOut(
        page_id=page.page_id,
        kind=page.kind,
        title=page.title_in(lang),
        path=page.path,
        parent_id=page.parent_id,
        linked_from=list(page.linked_from),
    )


class TreeCache:
    """Hält Registry und Seitenbaum im Speicher und lädt neu, wenn sich die Datei ändert.

    Der Schlüssel ist Änderungszeit und Grösse von tags.yaml. Schlägt das Laden fehl, bleibt nichts
    im Cache, und der nächste Aufruf versucht es erneut.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = Lock()
        self._key: tuple[int, int] | None = None
        self._value: tuple[Registry, dict[str, Page]] | None = None

    def get(self) -> tuple[Registry, dict[str, Page]]:
        try:
            stat = self.path.stat()
        except OSError as error:
            raise RegistryError(f"{self.path}: nicht lesbar: {error}") from error
        key = (stat.st_mtime_ns, stat.st_size)
        with self._lock:
            if self._value is None or key != self._key:
                self._value = None
                registry = load_registry(self.path)
                self._value = (registry, build_tree(registry))
                self._key = key
            return self._value


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    # Erst der Start der App öffnet den Pool; fehlt die Datenbank, melden nur ihre Endpunkte 503.
    pool = ConnectionPool(
        settings.database_url, min_size=1, max_size=4, kwargs={"autocommit": True}, open=False
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        pool.open(wait=False)
        try:
            yield
        finally:
            pool.close()

    app = FastAPI(
        title="ParlTopics",
        version=__version__,
        description=DESCRIPTION,
        openapi_tags=TAGS,
        docs_url=None,
        redoc_url=None,
        openapi_url="/v1/openapi.json",
        lifespan=lifespan,
    )
    api = APIRouter(prefix="/v1")
    cache = TreeCache(settings.registry_path)

    def load() -> tuple[Registry, dict[str, Page]]:
        try:
            return cache.get()
        except (RegistryError, TreeError) as error:
            raise HTTPException(503, f"Seitenbaum nicht verfügbar: {error}") from error

    def connection() -> Iterator[psycopg.Connection]:
        try:
            conn = pool.getconn(timeout=5)
        except (PoolClosed, PoolTimeout) as error:
            raise HTTPException(503, "Datenbank nicht erreichbar") from error
        try:
            yield conn
        finally:
            pool.putconn(conn)

    Conn = Annotated[psycopg.Connection, Depends(connection)]
    no_database = {503: {"description": "Datenbank nicht erreichbar"}}
    no_registry = {503: {"description": "Registry nicht lesbar"}}

    @app.get("/healthz", tags=["System"], summary="Lebenszeichen der API")
    def healthz() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    @api.get(
        "/jobs/summary", tags=["Jobs"], summary="Jobs je Aufgabe und Status", responses=no_database
    )
    def jobs_summary(conn: Conn) -> JobsSummary:
        """Zahl der Klassifikations-Jobs je Aufgabe und Status (F18)."""
        tasks: dict[str, JobCounts] = {}
        for task, status, count in job_summary(conn):
            counts = tasks.setdefault(task, JobCounts(task=task))
            setattr(counts, status, count)
            counts.total += count
        return JobsSummary(tasks=list(tasks.values()))

    @api.get(
        "/affairs/{affair_id}/topics",
        tags=["Geschäfte"],
        summary="Themen eines Geschäfts",
        responses={404: {"description": "Geschäft unbekannt"}, **no_database},
    )
    def affair_topics(affair_id: int, conn: Conn) -> AffairTopics:
        """Klassifikationstext, Kurzzusammenfassung und alle Labels mit Konfidenz, Beleg und
        Modell-, Prompt- und Registry-Version. Aktive Labels zuerst, danach der Verlauf
        (superseded, rejected)."""
        affair = queries.affair_topics(conn, affair_id)
        if affair is None:
            raise HTTPException(404, f"Geschäft {affair_id} unbekannt")
        return AffairTopics(**affair)

    @api.get("/topics", tags=["Themen"], summary="Alle Themen", responses=no_database)
    def topics(
        conn: Conn,
        scheme: Annotated[
            Literal["aps", "adhoc"] | None, Query(description="nur dieses Schema")
        ] = None,
    ) -> list[TopicOut]:
        """Tags der Registry mit der Zahl ihrer Geschäfte, sortiert wie der Seitenbaum."""
        return [TopicOut(**row) for row in queries.topics(conn, scheme)]

    @api.get(
        "/topics/{tag_id}/affairs",
        tags=["Themen"],
        summary="Geschäfte eines Themas",
        responses={404: {"description": "Thema unbekannt"}, **no_database},
    )
    def topic_affairs(
        tag_id: str,
        conn: Conn,
        body_key: Annotated[str | None, Query(description="Parlament, z. B. CHE oder ZH")] = None,
        date_from: Annotated[date | None, Query(alias="from", description="ab Datum")] = None,
        date_to: Annotated[date | None, Query(alias="to", description="bis Datum")] = None,
        min_confidence: Annotated[float, Query(ge=0, le=1)] = 0.0,
        limit: Annotated[int, Query(ge=1, le=500)] = 50,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> TopicAffairs:
        """Geschäfte mit aktivem Label, nach Konfidenz und dann neueste zuerst, seitenweise."""
        found = queries.topic_affairs(
            conn,
            tag_id,
            body_key=body_key,
            date_from=date_from,
            date_to=date_to,
            min_confidence=min_confidence,
            limit=limit,
            offset=offset,
        )
        if found is None:
            raise HTTPException(404, f"Thema {tag_id} unbekannt")
        total, items = found
        return TopicAffairs(total=total, limit=limit, offset=offset, items=items)

    @api.get("/pages", tags=["Seiten"], summary="Seitenbaum des ParlWiki", responses=no_registry)
    def pages(lang: LangQuery = "de") -> PageTree:
        """Seitenbaum aus der Registry: Wurzel, Bereiche, Kapitel, Tag- und Querschnittsseiten.

        Status, Kennzahlen und Zusammenfassungen kommen mit wiki_pages in Meilenstein M3 dazu.
        """
        registry, tree = load()
        return PageTree(
            registry_version=registry.registry_version,
            lang=lang,
            pages=[page_out(tree[page_id], lang) for page_id in page_ids(tree.values())],
        )

    @api.get(
        "/pages/{page_id}",
        tags=["Seiten"],
        summary="Eine Seite mit Vorfahren und Unterseiten",
        responses={404: {"description": "Seite unbekannt"}, **no_registry},
    )
    def page_detail(page_id: str, lang: LangQuery = "de") -> PageDetail:
        """Eine Seite mit Vorfahren, Unterseiten und Querschnittsverweisen, ohne den ganzen Baum."""
        registry, tree = load()
        page = tree.get(page_id)
        if page is None:
            raise HTTPException(404, f"Seite {page_id} gibt es nicht")
        linked = (
            [tree[other] for other in page.linked_from if other in tree]
            if page.kind == "querschnitt"
            else linked_querschnitt(tree, page_id)
        )
        return PageDetail(
            registry_version=registry.registry_version,
            lang=lang,
            page=page_out(page, lang),
            ancestors=[page_out(tree[other], lang) for other in reversed(ancestors(tree, page_id))],
            children=[page_out(child, lang) for child in children(tree, page_id)],
            linked=[page_out(other, lang) for other in linked],
        )

    app.include_router(api)

    @app.get("/v1/docs", include_in_schema=False)
    def docs() -> HTMLResponse:
        return get_swagger_ui_html(
            openapi_url="/v1/openapi.json",
            title="ParlTopics API",
            swagger_js_url="/v1/docs/static/swagger-ui-bundle.js",
            swagger_css_url="/v1/docs/static/swagger-ui.css",
            swagger_favicon_url="/favicon.svg",
            # Sonst lädt der Browser ein Prüfbild von validator.swagger.io.
            swagger_ui_parameters={"validatorUrl": None},
        )

    app.mount("/v1/docs/static", StaticFiles(directory=SWAGGER), name="swagger")
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
