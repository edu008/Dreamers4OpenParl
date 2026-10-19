"""Web-App und Sidecar-API (PRD 7.5, F10, F13, F20; ADR 0006).

Die Web-App ist eine React-SPA aus web/. FastAPI liefert ihren Build aus web/dist aus: Dateien
direkt, alle übrigen Pfade ausserhalb von /v1 als index.html, damit die Routen der SPA (z. B.
/tags/aps:6.1.9) auch beim Neuladen funktionieren. Ohne Build zeigt die App eine Hinweisseite.

Die API-Dokumentation (Swagger UI) liegt unter /v1/docs. Skripte und Stile kommen aus dem Paket,
nicht von einem CDN (PRD 9, Offline); FastAPIs Standardseiten /docs und /redoc bleiben aus. Das
OpenAPI-Schema steht unter /v1/openapi.json.
"""

import asyncio
import re
import time
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path
from threading import Lock
from typing import Annotated, Literal

import openai
import psycopg
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from psycopg_pool import ConnectionPool, PoolClosed, PoolTimeout
from pydantic import ValidationError

from parltopics import __version__
from parltopics.agent import loop as agent_loop
from parltopics.api import navigate, queries, reviews
from parltopics.api.schemas import (
    AdhocActivated,
    AdhocCreated,
    AdhocIn,
    AdhocPreview,
    AdhocScope,
    AffairRecord,
    AffairsSummary,
    AffairStar,
    AffairTopics,
    AgentIn,
    AgentOut,
    BodyDetail,
    BodyOut,
    Calibration,
    DocDetail,
    DocList,
    GoldLabel,
    GraphNode,
    JobCounts,
    JobsSummary,
    KeywordsIn,
    Lang,
    NavigateIn,
    NavigateOut,
    PageDetail,
    PageOut,
    PageTree,
    PathStep,
    ProposalDecisionIn,
    ProposalDecisionOut,
    ProposalList,
    Reason,
    RelatedTopic,
    ReviewIn,
    ReviewQueue,
    ReviewSummary,
    SearchResult,
    Stats,
    TopicAffairs,
    TopicGraph,
    TopicName,
    TopicOut,
    TopicStar,
)
from parltopics.classify import adhoc, proposals
from parltopics.classify.queue import summary as job_summary
from parltopics.config import Settings, get_settings
from parltopics.export import affairs_csv
from parltopics.llm import JSONExtractionError
from parltopics.registry import Registry, RegistryError, load_registry
from parltopics.registry.edit import TagExists
from parltopics.wiki.tree import (
    Page,
    TreeError,
    ancestors,
    build_tree,
    children,
    linked_querschnitt,
    page_ids,
    subtree_tag_ids,
)

ASSET_CACHE = "public, max-age=31536000, immutable"  # Dateinamen in assets/ tragen einen Hash
SWAGGER = Path(__file__).parent / "static" / "swagger"  # swagger-ui-dist, Apache-2.0

DESCRIPTION = """Sidecar-API von ParlTopics (PRD F10): Themen zu Geschäften aus OpenParlData,
klassifiziert mit Apertus, dazu die gespeicherten OpenParlData-Daten (Geschäfte, Texte, Dokumente,
Parlamente). Geschäfts-IDs sind OpenParlData-IDs. Schreibend sind nur POST /v1/reviews,
POST /v1/proposals/{proposal_id}/decision, POST /v1/adhoc und POST /v1/adhoc/{tag_id}/activate;
im Hack-MVP ohne Anmeldung und Rollen, an jedem Entscheid stehen Name und Zeit.
POST /v1/search/navigate und POST /v1/agent/search fragen Apertus und protokollieren jede Suche.

Ohne Datenbank antworten die Endpunkte unter Geschäfte, Themen, Review und Jobs mit 503;
/healthz und die Seiten unter /v1/pages funktionieren weiter."""

TAGS = [
    {
        "name": "Geschäfte",
        "description": "Ein Geschäft mit Themen, Belegen und Versionen und seinen gespeicherten"
        " OpenParlData-Daten.",
    },
    {"name": "Themen", "description": "Tags der Registry (APS und Ad-hoc) und ihre Geschäfte."},
    {"name": "Review", "description": "Entscheide von Menschen zu Labels, mit Name und Zeit."},
    {
        "name": "Suche",
        "description": "Volltext ohne Modell; Navigationssuche und Agent mit Apertus.",
    },
    {"name": "Evaluation", "description": "Kalibrierung und Gold-Set aus den Entscheiden."},
    {"name": "Ad-hoc", "description": "Neue Themen ohne Training: Stichwörter, Kandidaten, Jobs."},
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
# shortcut: höchstens zwei Suchen mit Modell (Navigation und Agent) gleichzeitig je API-Prozess;
# mit mehreren Prozessen oder vielen Nutzern ein Limit je Nutzer und Minute (PRD F10, Rate-Limit).
LLM_SEARCH_PARALLEL = 2


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
    llm_searches = asyncio.Semaphore(LLM_SEARCH_PARALLEL)

    @app.get("/healthz", tags=["System"], summary="Lebenszeichen der API")
    def healthz() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    @api.get(
        "/jobs/summary", tags=["Jobs"], summary="Jobs je Aufgabe und Status", responses=no_database
    )
    def jobs_summary(conn: Conn) -> JobsSummary:
        """Zahl der Klassifikations-Jobs je Aufgabe und Status (F18) und die letzten Läufe."""
        tasks: dict[str, JobCounts] = {}
        for task, status, count in job_summary(conn):
            counts = tasks.setdefault(task, JobCounts(task=task))
            setattr(counts, status, count)
            counts.total += count
        return JobsSummary(
            tasks=list(tasks.values()), runs=queries.runs(conn), errors=queries.job_errors(conn)
        )

    @api.get("/stats", tags=["Jobs"], summary="Gesamtzahlen", responses=no_database)
    def stats(conn: Conn) -> Stats:
        """Geschäfte gesamt, mit Text, im Volltext, klassifiziert und mit Thema, dazu die
        Labels und die Entscheide: für die Fortschrittsanzeige «x von 326'396»."""
        return Stats(**queries.stats(conn))

    @api.get("/bodies", tags=["Geschäfte"], summary="Parlamente", responses=no_database)
    def bodies(conn: Conn) -> list[BodyOut]:
        """Parlamente mit klassifizierten Geschäften: Bund, Kantone, Städte, Gemeinden, je nach
        Name. Für Filter (`body_key`) und Übersichten."""
        return [BodyOut(**row) for row in queries.bodies(conn)]

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

    @api.get(
        "/affairs/{affair_id}",
        tags=["Geschäfte"],
        summary="Gespeicherte Daten eines Geschäfts",
        responses={404: {"description": "Geschäft unbekannt"}, **no_database},
    )
    def affair_record(affair_id: int, conn: Conn) -> AffairRecord:
        """Das Geschäft, wie es aus OpenParlData in der Datenbank liegt: alle Felder von
        affairs.raw, Sprachfelder geschachtelt wie bei OpenParlData ({"de": …, "fr": …}), dazu
        das Parlament, alle Texte und die ersten 20 Dokumente. Nicht gespeichert und darum nicht
        dabei: Events, Contributors, Votings, Speeches, Agendas, Meetings und externe Links."""
        record = queries.affair_record(conn, affair_id)
        if record is None:
            raise HTTPException(404, f"Geschäft {affair_id} unbekannt")
        return AffairRecord(**record)

    @api.get(
        "/affairs/{affair_id}/docs",
        tags=["Geschäfte"],
        summary="Dokumente eines Geschäfts",
        responses={404: {"description": "Geschäft unbekannt"}, **no_database},
    )
    def affair_docs(
        affair_id: int,
        conn: Conn,
        limit: Annotated[int, Query(ge=1, le=200)] = 50,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> DocList:
        """Alle Dokumente des Geschäfts seitenweise, nach Datum, ohne ihren Text."""
        total, items = queries.affair_docs(conn, affair_id, limit=limit, offset=offset)
        if total == 0 and not queries.affair_exists(conn, affair_id):
            raise HTTPException(404, f"Geschäft {affair_id} unbekannt")
        return DocList(total=total, limit=limit, offset=offset, items=items)

    @api.get(
        "/docs/{doc_id}",
        tags=["Geschäfte"],
        summary="Ein Dokument mit Text",
        responses={404: {"description": "Dokument unbekannt"}, **no_database},
    )
    def doc_detail(doc_id: int, conn: Conn) -> DocDetail:
        """Ein Dokument mit dem Text, der aus der Datei extrahiert wurde; er kann sehr lang sein.
        Nicht verwechseln: Die API-Dokumentation liegt unter /v1/docs."""
        found = queries.doc(conn, doc_id)
        if found is None:
            raise HTTPException(404, f"Dokument {doc_id} unbekannt")
        return DocDetail(**found)

    @api.get(
        "/bodies/{body_key}",
        tags=["Geschäfte"],
        summary="Gespeicherte Daten eines Parlaments",
        responses={404: {"description": "Parlament unbekannt"}, **no_database},
    )
    def body_detail(body_key: str, conn: Conn) -> BodyDetail:
        """Das Parlament, wie es in bodies.raw liegt (Namen, Typ, Sprachen, Sitze, Wappen), mit
        der Zahl seiner Geschäfte und der klassifizierten. GET /v1/bodies listet nur Parlamente
        mit Labels."""
        found = queries.body_record(conn, body_key)
        if found is None:
            raise HTTPException(404, f"Parlament {body_key} unbekannt")
        return BodyDetail(**found)

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
        if not queries.tag_exists(conn, tag_id):
            raise HTTPException(404, f"Thema {tag_id} unbekannt")
        total, items = queries.topic_affairs(
            conn,
            [tag_id],
            body_key=body_key,
            date_from=date_from,
            date_to=date_to,
            min_confidence=min_confidence,
            limit=limit,
            offset=offset,
        )
        return TopicAffairs(total=total, limit=limit, offset=offset, items=items)

    PageFilter = Annotated[
        str | None, Query(description="nur Themen dieser Seite und der Seiten darunter")
    ]

    def subtree(page_id: str) -> list[str]:
        """Tags der Seite und ihrer Unterseiten; 404, wenn es die Seite nicht gibt."""
        _, tree = load()
        if page_id not in tree:
            raise HTTPException(404, f"Seite {page_id} gibt es nicht")
        return subtree_tag_ids(tree, page_id)

    @api.get(
        "/reviews/queue",
        tags=["Review"],
        summary="Labels mit Prüfbedarf",
        responses={404: {"description": "Seite unbekannt"}, **no_database},
    )
    def review_queue(
        conn: Conn,
        state: Annotated[
            Literal["open", "done"],
            Query(description="open: ohne Entscheid und mit Grund; done: mit Entscheid"),
        ] = "open",
        tag_id: Annotated[str | None, Query(description="nur dieses Thema")] = None,
        body_key: Annotated[str | None, Query(description="Parlament, z. B. CHE oder ZH")] = None,
        page_id: PageFilter = None,
        reason: Annotated[
            list[Reason] | None,
            Query(description="nur Labels mit einem dieser Gründe; mehrfach möglich"),
        ] = None,
        limit: Annotated[int, Query(ge=1, le=500)] = 50,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> ReviewQueue:
        """Warteschlange der Review-Seite (F9). Offen sind aktive Labels ohne Entscheid mit
        mindestens einem Grund: Konfidenz unter `threshold`, kein oder kein gefundener Beleg,
        Stichprobe. Erledigt sind Labels mit Entscheid, auch verworfene. Der Filter «Beleg» der
        Web-App ist reason=no_evidence&reason=evidence_unverified."""
        total, rows = queries.review_queue(
            conn,
            state=state,
            tag_id=tag_id,
            body_key=body_key,
            threshold=settings.confidence_threshold,
            limit=limit,
            offset=offset,
            tag_ids=subtree(page_id) if page_id else None,
            reasons=reason,
        )
        return ReviewQueue(
            threshold=settings.confidence_threshold,
            total=total,
            limit=limit,
            offset=offset,
            items=[{**row, "label": row} for row in rows],
        )

    @api.get(
        "/reviews/summary",
        tags=["Review"],
        summary="Zähler der Warteschlange",
        responses={404: {"description": "Seite unbekannt"}, **no_database},
    )
    def review_summary(
        conn: Conn,
        body_key: Annotated[str | None, Query(description="Parlament, z. B. CHE oder ZH")] = None,
        page_id: PageFilter = None,
    ) -> ReviewSummary:
        """Wie viele Labels offen und erledigt sind, und die offenen je Grund, Bereich,
        Parlament und Thema: für Filter, Zähler und `threshold`, ohne die Warteschlange zu
        laden. Die Zähler folgen body_key und page_id."""
        _, tree = load()
        summary = queries.review_summary(
            conn,
            body_key=body_key,
            tag_ids=subtree(page_id) if page_id else None,
            threshold=settings.confidence_threshold,
        )
        return ReviewSummary(
            threshold=settings.confidence_threshold,
            open=summary["open"],
            done=summary["done"],
            by_reason=summary["reason"],
            by_area=[
                {
                    "page_id": row["key"],
                    "title": tree[row["key"]].title if row["key"] in tree else row["key"],
                    "count": row["count"],
                }
                for row in summary["area"]
            ],
            by_body=summary["body"],
            by_topic=summary["topic"],
        )

    @api.get(
        "/topics/{tag_id}/related",
        tags=["Themen"],
        summary="Verwandte Themen",
        responses={404: {"description": "Thema unbekannt"}, **no_database},
    )
    def topic_related(
        tag_id: str, conn: Conn, limit: Annotated[int, Query(ge=1, le=50)] = 10
    ) -> list[RelatedTopic]:
        """Zuerst die in der Registry als verwandt eingetragenen Themen (related), dann die
        Themen mit den meisten gemeinsamen Geschäften. shared zählt aktive Labels."""
        if not queries.tag_exists(conn, tag_id):
            raise HTTPException(404, f"Thema {tag_id} unbekannt")
        registry, _ = load()
        shared = {row["tag_id"]: row for row in queries.co_topics(conn, tag_id, limit)}
        known = {tag.tag_id: tag for tag in registry.tags}
        curated = known[tag_id].related if tag_id in known else []
        related = []
        for other in curated:
            if other not in known:
                continue
            row = shared.pop(other, None)
            related.append(
                RelatedTopic(
                    tag_id=other,
                    name_de=known[other].pref_label.de,
                    shared=row["shared"] if row else 0,
                    in_registry=True,
                )
            )
        return related + [RelatedTopic(**row, in_registry=False) for row in shared.values()]

    @api.get(
        "/graph/topics",
        tags=["Themen"],
        summary="Themen-Graph",
        responses={
            404: {"description": "Bereich unbekannt"},
            503: {"description": "Registry nicht lesbar oder Datenbank nicht erreichbar"},
        },
    )
    def graph_topics(
        conn: Conn,
        area: Annotated[
            str | None,
            Query(
                description="Bereich wie aps:6, all für alle Themen; ohne: ein Knoten je Bereich"
            ),
        ] = None,
        min_weight: Annotated[int, Query(ge=1, description="nur Kanten ab so vielen")] = 1,
        limit: Annotated[int, Query(ge=1, le=500, description="höchstens so viele Kanten")] = 60,
        lang: LangQuery = "de",
    ) -> TopicGraph:
        """Themen untereinander (F20, Sicht 3): Ohne area ein Knoten je APS-Bereich, mit area
        die Themen dieses Bereichs, mit area=all jedes freigegebene Thema (APS und Ad-hoc).
        Kantengewicht = Zahl der Geschäfte, die beide Knoten tragen. Das Layout rechnet die
        Web-App."""
        _, tree = load()
        if area not in (None, "all") and (area not in tree or tree[area].kind != "bereich"):
            raise HTTPException(404, f"Bereich {area} gibt es nicht")
        nodes, edges, hidden = queries.topic_graph(
            conn, area=area, min_weight=min_weight, limit=limit
        )
        return TopicGraph(
            area=area,
            nodes=[
                GraphNode(
                    id=node["node"],
                    label=tree[node["node"]].title_in(lang)
                    if node["node"] in tree
                    else node["node"],
                    kind=tree[node["node"]].kind if node["node"] in tree else "tag",
                    count=node["count"],
                    group=node["node"].split(".")[0]
                    if node["node"].startswith("aps:")
                    else "adhoc",
                )
                for node in nodes
            ],
            edges=edges,
            hidden=hidden,
        )

    @api.get(
        "/graph/topics/{tag_id}",
        tags=["Themen"],
        summary="Graph: ein Thema und seine Geschäfte",
        responses={404: {"description": "Thema unbekannt"}, **no_database},
    )
    def graph_topic(
        tag_id: str,
        conn: Conn,
        min_confidence: Annotated[float, Query(ge=0, le=1)] = 0.0,
        limit: Annotated[int, Query(ge=1, le=200)] = 200,
    ) -> TopicStar:
        """Sicht 1 (PRD 7.5): das Thema in der Mitte, seine Geschäfte darum, nach Konfidenz und
        höchstens 200. Dieselben Zeilen wie GET /v1/topics/{tag_id}/affairs."""
        name = queries.tag_name(conn, tag_id)
        if name is None:
            raise HTTPException(404, f"Thema {tag_id} unbekannt")
        total, items = queries.topic_affairs(
            conn,
            [tag_id],
            body_key=None,
            date_from=None,
            date_to=None,
            min_confidence=min_confidence,
            limit=limit,
            offset=0,
        )
        return TopicStar(center=TopicName(tag_id=tag_id, name_de=name), total=total, nodes=items)

    @api.get(
        "/graph/affairs/{affair_id}",
        tags=["Geschäfte"],
        summary="Graph: ein Geschäft und seine Nachbarn",
        responses={404: {"description": "Geschäft unbekannt"}, **no_database},
    )
    def graph_affair(
        affair_id: int, conn: Conn, limit: Annotated[int, Query(ge=1, le=50)] = 50
    ) -> AffairStar:
        """Sicht 2 (PRD 7.5): das Geschäft mit seinen aktiven Themen und die Geschäfte, die
        Themen mit ihm teilen, höchstens 50. Ohne aktives Thema keine Nachbarn."""
        center = queries.hits(conn, [affair_id])
        if not center:
            raise HTTPException(404, f"Geschäft {affair_id} unbekannt")
        return AffairStar(center=center[0], neighbours=queries.neighbours(conn, affair_id, limit))

    @api.get("/proposals", tags=["Review"], summary="Tag-Vorschläge", responses=no_database)
    def proposal_list(
        conn: Conn,
        state: Annotated[
            Literal["open", "done"], Query(description="open: zu entscheiden; done: entschieden")
        ] = "open",
        limit: Annotated[int, Query(ge=1, le=200)] = 50,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> ProposalList:
        """Vorschläge des Modells für fehlende Themen, gruppiert und mit Empfehlung (F7): new,
        duplicate_of oder child_of. Offene zuerst nach der Zahl betroffener Geschäfte."""
        total, rows = queries.proposals(conn, state=state, limit=limit, offset=offset)
        return ProposalList(total=total, limit=limit, offset=offset, items=rows)

    @api.post(
        "/proposals/{proposal_id}/decision",
        tags=["Review"],
        summary="Entscheid zu einem Tag-Vorschlag",
        responses={
            404: {"description": "Vorschlag unbekannt"},
            409: {"description": "Schon entschieden, oder das Tag gibt es schon"},
            422: {"description": "merged ohne Tag oder ungültiges Tag"},
            **no_database,
        },
    )
    def proposal_decision(
        proposal_id: int, body: ProposalDecisionIn, conn: Conn
    ) -> ProposalDecisionOut:
        """accepted legt ein Ad-hoc-Thema mit Status proposed an und öffnet Jobs für die
        betroffenen Geschäfte; ein Mensch schaltet es später frei (/v1/adhoc/{tag_id}/activate).
        merged und rejected halten den Entscheid mit Name und Zeit fest."""
        try:
            decided = proposals.decide(
                conn,
                settings,
                proposal_id,
                decision=body.decision,
                by=body.user_name,
                name_de=body.name_de,
                definition_de=body.description_de,
                broader=body.broader,
                related_tag_id=body.related_tag_id,
            )
        except proposals.ProposalNotFound as error:
            raise HTTPException(404, str(error)) from error
        except (proposals.ProposalDecided, TagExists) as error:
            raise HTTPException(409, str(error)) from error
        except (ValueError, RegistryError) as error:
            raise HTTPException(422, str(error)) from error
        return ProposalDecisionOut(
            proposal=queries.proposal(conn, proposal_id),
            tag_id=decided.tag_id,
            run_id=decided.run.run_id if decided.run else None,
            jobs=decided.run.total if decided.run else None,
        )

    @api.post(
        "/reviews",
        tags=["Review"],
        summary="Entscheid zum Label eines Themas",
        responses={
            404: {"description": "Kein passendes Label, Thema unbekannt oder Geschäft ohne Text"},
            409: {"description": "Für das Thema gibt es schon ein aktives Label"},
            503: {"description": "Datenbank nicht erreichbar oder Migration 0004 fehlt (undo)"},
        },
    )
    def review(body: ReviewIn, conn: Conn) -> AffairTopics:
        """Bestätigt, verwirft, ändert oder setzt ein Thema an einem Geschäft, oder nimmt den
        letzten Entscheid zu diesem Thema zurück (undo). Labels werden nie gelöscht, nur ihr Status
        ändert sich; jede Aktion steht mit Name und Zeit in der Tabelle reviews.

        Antwort: das Geschäft wie unter GET /v1/affairs/{affair_id}/topics. Ein change nimmt man
        mit undo auf beiden Themen zurück: auf dem alten (wieder aktiv) und dem neuen (entfernt).
        """
        reviews.apply(conn, body)
        affair = queries.affair_topics(conn, body.affair_id)
        assert affair is not None  # ein Label hängt immer an einem Geschäft (Fremdschlüssel)
        return AffairTopics(**affair)

    @api.post(
        "/adhoc/keywords",
        tags=["Ad-hoc"],
        summary="Stichwörter für ein neues Thema",
        responses={
            502: {"description": "Antwort des Modells unbrauchbar"},
            503: {"description": "LLM nicht erreichbar"},
        },
    )
    async def adhoc_keywords(body: KeywordsIn) -> adhoc.Keywords:
        """Apertus 70B schlägt Suchbegriffe in DE, FR und IT vor (generate_keywords). Ein Mensch
        prüft und ergänzt sie, bevor POST /v1/adhoc das Thema anlegt."""
        try:
            return await adhoc.suggest_keywords(settings, body.name_de, body.description_de)
        except openai.APIError as error:
            raise HTTPException(503, f"LLM nicht erreichbar: {type(error).__name__}") from error
        except (JSONExtractionError, ValidationError) as error:
            raise HTTPException(502, "Die Antwort des Modells ist unbrauchbar") from error

    @api.post(
        "/adhoc/preview",
        tags=["Ad-hoc"],
        summary="Kandidaten für Stichwörter zählen",
        responses=no_database,
    )
    def adhoc_preview(body: AdhocScope, conn: Conn) -> AdhocPreview:
        """Wie viele Geschäfte die Stichwörter treffen und wie gross die Stichprobe ist, ohne
        etwas anzulegen und ohne Modell. Beispiele: die neuesten Kandidaten."""
        candidates, sample = adhoc.find_affairs(
            conn, body.keywords, bodies=body.bodies, since=body.since
        )
        return AdhocPreview(
            candidates=len(candidates),
            sample=len(sample),
            examples=queries.affair_heads(conn, candidates[:5]),
        )

    @api.post(
        "/adhoc",
        tags=["Ad-hoc"],
        summary="Ad-hoc-Thema anlegen und auswerten",
        responses={
            409: {"description": "Das Thema gibt es schon"},
            422: {"description": "Ungültige Angaben, etwa ein unbekanntes broader-Tag"},
            **no_database,
        },
    )
    def adhoc_create(body: AdhocIn, conn: Conn) -> AdhocCreated:
        """Legt das Thema mit Status proposed in der Registry an und öffnet Jobs
        classify:adhoc:<name> für Kandidaten und Stichprobe. Die Worker prüfen sie mit
        Apertus; die Treffer erscheinen sofort als vorläufig (tag_status proposed). Ohne
        Anmeldung im Hack-MVP; user_name steht im Tag (created.by) und im Lauf."""
        try:
            created = adhoc.create(
                conn,
                settings,
                name_de=body.name_de,
                definition_de=body.description_de,
                keywords=body.keywords,
                by=body.user_name,
                broader=body.broader,
                bodies=body.bodies,
                since=body.since,
            )
        except TagExists as error:
            raise HTTPException(409, str(error)) from error
        except RegistryError as error:
            raise HTTPException(422, str(error)) from error
        return AdhocCreated(
            tag_id=created.tag_id,
            registry_version=created.registry_version,
            run_id=created.run.run_id,
            jobs=created.run.total,
            candidates=created.candidates,
            sample=created.sample,
        )

    @api.post(
        "/adhoc/{tag_id}/activate",
        tags=["Ad-hoc"],
        summary="Ad-hoc-Thema freischalten",
        responses={
            404: {"description": "Kein Ad-hoc-Thema der Registry"},
            409: {"description": "Schon aktiv"},
            **no_database,
        },
    )
    def adhoc_activate(tag_id: str, conn: Conn) -> AdhocActivated:
        """Setzt ein bewährtes Thema von proposed auf active. Ab dann bietet Stufe 2 von
        classify:aps es allen Geschäften an, und es bekommt eine Querschnittsseite."""
        registry, _ = load()
        tag = next((tag for tag in registry.tags if tag.tag_id == tag_id), None)
        if tag is None or tag.scheme != "adhoc":
            raise HTTPException(404, f"{tag_id} ist kein Ad-hoc-Thema der Registry")
        if tag.status == "active":
            raise HTTPException(409, f"{tag_id} ist schon aktiv")
        registry = adhoc.activate(conn, settings, tag_id)
        return AdhocActivated(
            tag_id=tag_id, status="active", registry_version=registry.registry_version
        )

    @api.get(
        "/eval/calibration",
        tags=["Evaluation"],
        summary="Trefferquote je Konfidenzband",
        responses=no_database,
    )
    def eval_calibration(conn: Conn) -> Calibration:
        """Wie ehrlich ist die Konfidenz? Je Band der Anteil der Modell-Labels, die ein Mensch
        bestätigt hat (verworfen und ersetzt zählen als falsch). Für den Bericht zählt die
        Stichprobe, denn die übrige Warteschlange wählt nach tiefer Konfidenz aus."""
        bands = queries.calibration(conn)
        return Calibration(
            threshold=settings.confidence_threshold,
            reviewed=sum(band["reviewed"] for band in bands),
            confirmed=sum(band["confirmed"] for band in bands),
            bands=bands,
        )

    @api.get("/eval/gold", tags=["Evaluation"], summary="Gold-Set (Export)", responses=no_database)
    def eval_gold(conn: Conn) -> list[GoldLabel]:
        """Alle aktuellen Entscheide als Gold-Labels, ältester zuerst: bestätigt und von Hand
        gesetzt gehören dazu, verworfen und ersetzt nicht. Mit Modell-, Prompt- und
        Registry-Version und dem Text (input_hash), auf den sich der Entscheid bezieht."""
        return [GoldLabel(**row) for row in queries.gold(conn)]

    @api.get("/search", tags=["Suche"], summary="Volltextsuche", responses=no_database)
    def search(
        conn: Conn,
        q: Annotated[
            str | None,
            Query(
                min_length=2,
                max_length=200,
                description='Suchbegriffe; "…" für eine Wortfolge, -wort schliesst aus,'
                " or für oder; ohne q die neuesten Geschäfte",
            ),
        ] = None,
        topic: Annotated[str | None, Query(description="nur mit diesem aktiven Thema")] = None,
        body_key: Annotated[str | None, Query(description="Parlament, z. B. CHE oder ZH")] = None,
        level: Annotated[
            Literal["country", "canton", "city", "municipality"] | None,
            Query(description="Ebene des Parlaments"),
        ] = None,
        language: Annotated[
            Lang | None, Query(description="Sprache des Klassifikationstexts")
        ] = None,
        date_from: Annotated[date | None, Query(alias="from", description="ab Datum")] = None,
        date_to: Annotated[date | None, Query(alias="to", description="bis Datum")] = None,
        limit: Annotated[int, Query(ge=1, le=50)] = 20,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> SearchResult:
        """Volltextsuche über die Klassifikationstexte (Titel und Texte), ohne Sprachangabe: Die
        Begriffe werden deutsch, französisch und italienisch auf ihren Stamm zurückgeführt. Rang
        nach ts_rank_cd, Treffer im Titel zählen mehr. Je Treffer ein Ausschnitt mit markierten
        Begriffen und die aktiven Themen. Ohne q: alle Geschäfte mit Klassifikationstext,
        neueste zuerst, ohne Rang und Ausschnitt; die Filter gelten gleich."""
        start = time.perf_counter()
        total, items = queries.search(
            conn,
            q=q,
            topic=topic,
            body_key=body_key,
            level=level,
            language=language,
            date_from=date_from,
            date_to=date_to,
            limit=limit,
            offset=offset,
        )
        duration_ms = round((time.perf_counter() - start) * 1000)
        return SearchResult(
            q=q, total=total, limit=limit, offset=offset, duration_ms=duration_ms, items=items
        )

    @api.post(
        "/search/navigate",
        tags=["Suche"],
        summary="Suche in eigenen Worten",
        responses={
            429: {"description": "Zu viele Suchen gleichzeitig"},
            503: {"description": "LLM, Registry oder Datenbank nicht erreichbar"},
        },
    )
    async def search_navigate(body: NavigateIn, conn: Conn) -> NavigateOut:
        """Navigationssuche (F26): Apertus geht von Heart über Bereich und Kapitel zur Tag-Seite,
        mit Rückweg und höchstens NAVIGATE_MAX_STEPS Modellaufrufen, wählt dort die passenden
        Geschäfte und antwortet in belegten Aussagen. Findet der Baum nichts, liefert die
        Volltextsuche die Kandidaten. Ohne Treffer keine Antwort. Dauert einige Sekunden; jede
        Suche steht in search_runs."""
        if llm_searches.locked():
            raise HTTPException(429, "Zu viele Suchen gleichzeitig, bitte gleich nochmals")
        registry, tree = load()
        start = time.perf_counter()
        async with llm_searches:
            try:
                searched = await navigate.search(settings, conn, registry, tree, body.query)
            except openai.APIError as error:
                elapsed = round((time.perf_counter() - start) * 1000)
                await asyncio.to_thread(navigate.log_error, conn, body.query, elapsed)
                raise HTTPException(503, f"LLM nicht erreichbar: {type(error).__name__}") from error
        result = searched.result
        hits = await asyncio.to_thread(queries.hits, conn, result.affair_ids)
        related: dict[str, str] = {}
        for page_id in result.path:
            page = tree.get(page_id)
            if page is not None and page.tag_id is not None:
                related[page.tag_id] = page.title
        for hit in hits:
            for topic in hit["topics"]:
                related.setdefault(topic["tag_id"], topic["name_de"])
        return NavigateOut(
            query=body.query,
            answer=searched.answer,
            statements=[statement.model_dump() for statement in result.statements],
            hits=hits,
            related_topics=[
                TopicName(tag_id=tag_id, name_de=name) for tag_id, name in list(related.items())[:8]
            ],
            path=[
                PathStep(
                    page_id=page_id,
                    title=tree[page_id].title if page_id in tree else "Volltextsuche",
                )
                for page_id in result.path
            ],
            status=result.status,
            steps=result.steps,
            fallback_used=result.fallback_used,
            filters=result.filters.model_dump() if result.filters else None,
            duration_ms=searched.duration_ms,
            search_run_id=searched.run_id,
        )

    @api.post(
        "/agent/search",
        tags=["Suche"],
        summary="Agent: Frage mit Werkzeugen beantworten",
        responses={
            429: {"description": "Zu viele Suchen gleichzeitig"},
            503: {"description": "LLM, Registry oder Datenbank nicht erreichbar"},
        },
    )
    async def agent_search(body: AgentIn, conn: Conn) -> AgentOut:
        """Agent (F21, ARCHITEKTUR 4): Apertus 70B beantwortet die Frage mit höchstens sechs
        lesenden Werkzeugen (Volltext, Tags, Geschäft, Zählung, Navigationssuche, Seite,
        Stichwörter, Entwurf eines Ad-hoc-Themas) und zitiert nur Geschäfte, die ein Werkzeug
        geliefert hat. Dauert bis zu einer Minute; jede Sitzung steht in agent_runs. Ein
        Entwurf in proposal legt nichts an: Erst POST /v1/adhoc durch einen Menschen tut das."""
        if llm_searches.locked():
            raise HTTPException(429, "Zu viele Suchen gleichzeitig, bitte gleich nochmals")
        registry, tree = load()
        start = time.perf_counter()
        async with llm_searches:
            try:
                ran = await agent_loop.search(settings, conn, registry, tree, body.query)
            except openai.APIError as error:
                elapsed = round((time.perf_counter() - start) * 1000)
                await asyncio.to_thread(agent_loop.log_error, settings, conn, body.query, elapsed)
                raise HTTPException(503, f"LLM nicht erreichbar: {type(error).__name__}") from error
        outcome = ran.outcome
        return AgentOut(
            query=body.query,
            answer=outcome.answer,
            cited_affair_ids=outcome.cited_ids,
            hits=await asyncio.to_thread(queries.hits, conn, outcome.cited_ids),
            tool_calls=outcome.tool_calls,
            proposal=outcome.proposal,
            status=outcome.status,
            steps=outcome.steps,
            duration_ms=ran.duration_ms,
            agent_run_id=ran.run_id,
        )

    @api.get("/pages", tags=["Seiten"], summary="Seitenbaum des ParlWiki", responses=no_registry)
    def pages(lang: LangQuery = "de") -> PageTree:
        """Seitenbaum aus der Registry: Wurzel, Bereiche, Kapitel, Tag- und Querschnittsseiten.

        Status, Kennzahl und Zusammenfassung einer Seite liefert GET /v1/pages/{page_id}.
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
        """Eine Seite mit Vorfahren, Unterseiten und Querschnittsverweisen, ohne den ganzen Baum.
        summary kommt aus dem Seitenlauf (parltopics pages): Status, Zahl der Geschäfte,
        Kurzzusammenfassung und belegte Aussagen; ohne Lauf oder ohne Datenbank null."""
        registry, tree = load()
        page = tree.get(page_id)
        if page is None:
            raise HTTPException(404, f"Seite {page_id} gibt es nicht")
        summary = None
        try:
            with pool.connection(timeout=1) as conn:
                summary = queries.wiki_page(conn, page_id)
        except (PoolClosed, PoolTimeout, psycopg.Error):
            pass  # ohne Datenbank oder Seitenlauf: die Seite kommt aus der Registry
        linked = (
            [tree[other] for other in page.linked_from if other in tree]
            if page.kind == "querschnitt"
            else linked_querschnitt(tree, page_id)
        )
        tag = registry.get(page.tag_id) if page.tag_id else None
        return PageDetail(
            registry_version=registry.registry_version,
            lang=lang,
            page=page_out(page, lang),
            ancestors=[page_out(tree[other], lang) for other in reversed(ancestors(tree, page_id))],
            children=[page_out(child, lang) for child in children(tree, page_id)],
            linked=[page_out(other, lang) for other in linked],
            definition=(getattr(tag.definition, lang) or tag.definition.de) if tag else None,
            alt_labels=(getattr(tag.alt_labels, lang) or tag.alt_labels.de) if tag else [],
            related=[page_out(tree[other], lang) for other in tag.related if other in tree]
            if tag
            else [],
            summary=summary,
        )

    def affair_filters(
        body_key: Annotated[str | None, Query(description="Parlament, z. B. CHE oder ZH")] = None,
        level: Annotated[
            list[Literal["country", "canton", "city", "municipality"]] | None,
            Query(description="Ebene des Parlaments; mehrfach möglich, z. B. Bund und Kantone"),
        ] = None,
        affair_type: Annotated[
            str | None, Query(alias="type", description="harmonisierter Typ, z. B. Motion")
        ] = None,
        date_from: Annotated[date | None, Query(alias="from", description="ab Datum")] = None,
        date_to: Annotated[date | None, Query(alias="to", description="bis Datum")] = None,
        min_confidence: Annotated[float, Query(ge=0, le=1)] = 0.0,
        running: Annotated[
            bool,
            Query(description="nur laufende Geschäfte: ohne Enddatum, nicht als inaktiv markiert"),
        ] = False,
    ) -> dict:
        """Filter der Geschäfte einer Seite, mit den Namen von queries.topic_affairs. Die DVS-Liste
        (F12) ist level=country&level=canton&running=true auf adhoc:digitalisierung-breit."""
        return {
            "body_key": body_key,
            "level": level,
            "affair_type": affair_type,
            "date_from": date_from,
            "date_to": date_to,
            "min_confidence": min_confidence,
            "running": running,
        }

    AffairFilters = Annotated[dict, Depends(affair_filters)]
    page_errors = {
        404: {"description": "Seite unbekannt"},
        503: {"description": "Registry nicht lesbar oder Datenbank nicht erreichbar"},
    }

    @api.get(
        "/pages/{page_id}/affairs",
        tags=["Seiten"],
        summary="Geschäfte einer Seite und ihrer Unterseiten",
        responses=page_errors,
    )
    def page_affairs(
        page_id: str,
        conn: Conn,
        filters: AffairFilters,
        limit: Annotated[int, Query(ge=1, le=500)] = 50,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> TopicAffairs:
        """Geschäfte mit aktivem Label auf dieser Seite oder einer Seite darunter: auf einer
        Tag- oder Querschnittsseite die ihres Tags, auf Kapitel, Bereich und Heart die aller
        Unterseiten. Eine Zeile je Geschäft und Thema: Ein Geschäft mit zwei Themen eines
        Kapitels erscheint zweimal. Verlinkte Querschnittsseiten zählen nicht dazu."""
        total, items = queries.topic_affairs(
            conn, subtree(page_id), **filters, limit=limit, offset=offset
        )
        return TopicAffairs(total=total, limit=limit, offset=offset, items=items)

    @api.get(
        "/pages/{page_id}/affairs/summary",
        tags=["Seiten"],
        summary="Auswertung der Geschäfte einer Seite",
        responses=page_errors,
    )
    def page_affairs_summary(page_id: str, conn: Conn, filters: AffairFilters) -> AffairsSummary:
        """Kennzahlen und Verteilungen wie die Auswertung der Web-App, über alle Geschäfte der
        Seite statt einer geladenen Auswahl. Die Kennzahlen folgen allen Filtern; jede
        Verteilung lässt ihren eigenen weg (by_level ohne level, by_body ohne body_key, by_year
        ohne from und to, by_type ohne type), damit sie die Alternativen zeigt."""
        return AffairsSummary(**queries.page_summary(conn, subtree(page_id), **filters))

    @api.get(
        "/pages/{page_id}/affairs.csv",
        tags=["Seiten"],
        summary="Geschäfte einer Seite als CSV",
        response_class=StreamingResponse,
        responses={200: {"content": {"text/csv": {}}}, **page_errors},
    )
    def page_affairs_csv(page_id: str, conn: Conn, filters: AffairFilters) -> StreamingResponse:
        """Alle Zeilen wie GET /v1/pages/{page_id}/affairs, ohne Grenze, als CSV wie der Export
        der Web-App: Semikolon, UTF-8 mit BOM, Formelzeichen entschärft. Die DVS-Liste (F12)
        ist /v1/pages/adhoc:digitalisierung-breit/affairs.csv."""
        rows = queries.stream_topic_affairs(conn, subtree(page_id), **filters)
        name = re.sub(r"[^a-z0-9]+", "-", page_id, flags=re.IGNORECASE)
        return StreamingResponse(
            affairs_csv(rows),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{name}.csv"'},
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
