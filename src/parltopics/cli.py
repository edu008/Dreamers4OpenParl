"""Kommandozeile `parltopics` (PRD 10.4).

Funktionsfähig: version, db migrate, registry validate/sync/import-aps, llm check, download,
ingest, inputs, classify, worker, jobs summary. Die übrigen Kommandos zeigen ihre geplante
Schnittstelle und nennen ihren Meilenstein.
"""

import asyncio
import contextlib
from datetime import datetime
from pathlib import Path
from typing import Annotated

import typer

from parltopics import __version__
from parltopics.config import Settings, get_settings

NOT_IMPLEMENTED_EXIT = 3
DATE = ["%Y-%m-%d"]

app = typer.Typer(
    help="ParlTopics: Themen-Klassifikation für OpenParlData mit Apertus.", no_args_is_help=True
)
db_app = typer.Typer(help="Datenbank und Migrationen.", no_args_is_help=True)
registry_app = typer.Typer(help="Tag-Registry registry/tags.yaml.", no_args_is_help=True)
llm_app = typer.Typer(help="LLM-Endpunkt (LLM_BASE_URL).", no_args_is_help=True)
jobs_app = typer.Typer(help="Job-Queue der Klassifikation.", no_args_is_help=True)
app.add_typer(db_app, name="db")
app.add_typer(registry_app, name="registry")
app.add_typer(llm_app, name="llm")
app.add_typer(jobs_app, name="jobs")


def _planned(milestone: str, reference: str) -> None:
    typer.secho(
        f"Noch nicht umgesetzt: Meilenstein {milestone}, PRD {reference}.",
        fg=typer.colors.YELLOW,
        err=True,
    )
    raise typer.Exit(code=NOT_IMPLEMENTED_EXIT)


@app.command()
def version() -> None:
    """Version ausgeben."""
    typer.echo(__version__)


@db_app.command("migrate")
def db_migrate() -> None:
    """Neue Migrationen aus migrations/ anwenden."""
    from parltopics.db import connect, migrate

    settings = get_settings()
    with connect(settings.database_url) as conn:
        applied = migrate(conn, settings.migrations_dir)
    typer.echo("Angewendet: " + ", ".join(applied) if applied else "Schema ist aktuell.")


@registry_app.command("validate")
def registry_validate(
    path: Annotated[Path | None, typer.Argument(help="Standard: REGISTRY_PATH")] = None,
) -> None:
    """registry/tags.yaml prüfen und scheme_hash je Schema ausgeben (F4)."""
    from parltopics.registry import RegistryError, load_registry, scheme_hash

    path = path or get_settings().registry_path
    try:
        registry = load_registry(path)
    except RegistryError as error:
        typer.secho(str(error), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from error
    typer.echo(f"{path}: gültig, registry_version {registry.registry_version}")
    for scheme in registry.schemes:
        tags = [tag for tag in registry.tags if tag.scheme == scheme]
        active = sum(tag.status == "active" for tag in tags)
        proposed = sum(tag.status == "proposed" for tag in tags)
        typer.echo(
            f"  {scheme:<6} {len(tags):>4} Tags, {active:>4} aktiv, {proposed:>3} vorgeschlagen"
            f"   scheme_hash {scheme_hash(registry, scheme)[:16]}"
        )


@registry_app.command("sync")
def registry_sync() -> None:
    """Registry in die Tabelle tags spiegeln; geänderte Datei ohne neue Version ablehnen (F4)."""
    from parltopics.db import connect
    from parltopics.registry import RegistryError, file_hash, load_registry
    from parltopics.registry.sync import sync_registry

    settings = get_settings()
    path = settings.registry_path
    try:
        registry = load_registry(path)
        with connect(settings.database_url, autocommit=True) as conn:
            result = sync_registry(conn, registry, file_hash(path))
    except RegistryError as error:
        typer.secho(str(error), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from error
    version = registry.registry_version
    if not result.changed:
        typer.echo(f"registry_version {version}: unverändert")
        return
    typer.echo(f"registry_version {version}: {result.tags} Tags neu oder geändert")
    for scheme, digest in result.scheme_hashes.items():
        typer.echo(f"  {scheme:<6} scheme_hash {digest[:16]}")


@registry_app.command("import-aps")
def registry_import_aps(
    xlsx: Annotated[Path, typer.Argument(help="aps_topics.xlsx aus dem hackapertus-Datensatz")],
) -> None:
    """APS-Schema (165 Themen) aus aps_topics.xlsx in registry/tags.yaml übernehmen."""
    from parltopics.registry import RegistryError
    from parltopics.registry.aps_import import import_aps

    registry_path = get_settings().registry_path
    try:
        count, version = import_aps(xlsx, registry_path)
    except (RegistryError, OSError) as error:
        typer.secho(str(error), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from error
    typer.echo(f"{count} APS-Einträge in {registry_path}, registry_version {version}")


@llm_app.command("check")
def llm_check() -> None:
    """Beide Modelle einmal aufrufen und Antwortzeit melden."""
    import openai

    from parltopics.llm import LLMClient

    settings = get_settings()

    async def run() -> tuple[list[tuple[str, bool, str]], list[str]]:
        results: list[tuple[str, bool, str]] = []
        available: list[str] = []
        async with LLMClient(settings) as client:
            for large in (False, True):
                name = settings.llm_name_large if large else settings.llm_name
                try:
                    reply = await client.chat(
                        [{"role": "user", "content": "Antworte nur mit OK."}],
                        large=large,
                        max_tokens=5,
                        attempts=1,
                    )
                except Exception as error:  # Bericht statt Abbruch
                    results.append((name, False, f"{type(error).__name__}: {error}"))
                    # Ein unbekannter Modellname ergibt 404: die gültigen Namen gleich mitliefern.
                    if isinstance(error, openai.NotFoundError) and not available:
                        with contextlib.suppress(openai.OpenAIError):
                            available = await client.models()
                else:
                    detail = (
                        f"{reply.duration_ms} ms, Modell {reply.model}, Antwort {reply.content!r}"
                    )
                    results.append((name, True, detail))
        return results, available

    typer.echo(f"Endpunkt: {settings.llm_base_url}")
    results, available = asyncio.run(run())
    failed = False
    for name, ok, detail in results:
        failed |= not ok
        mark = (
            typer.style("ok    ", fg=typer.colors.GREEN) if ok else typer.style("FEHLER", fg="red")
        )
        typer.echo(f"  {mark} {name}: {detail}")
    if available:
        typer.echo(f"Modelle am Endpunkt: {', '.join(available)}")
    if failed:
        raise typer.Exit(code=1)


@app.command()
def download(
    bundle: Annotated[Path, typer.Option(help="Zielverzeichnis des Import-Bündels")] = Path(
        "data/import"
    ),
    bodies: Annotated[list[str] | None, typer.Option(help="body_keys, z. B. CHE")] = None,
) -> None:
    """Exporte von files.openparldata.ch laden, nur geänderte Dateien (F1). Online-Schritt."""
    from parltopics.download import download as run_download

    loaded, unchanged = run_download(bundle, bodies or None, echo=typer.echo)
    typer.echo(f"{bundle}: {loaded} Dateien geladen, {unchanged} unverändert.")


@app.command()
def ingest(
    bundle: Annotated[Path, typer.Option(help="Import-Bündel")] = Path("data/import"),
) -> None:
    """Import-Bündel in PostgreSQL laden, Zeilenzahlen prüfen (F2)."""
    from parltopics.db import connect
    from parltopics.ingest import ingest as run_ingest

    with connect(get_settings().database_url, autocommit=True) as conn:
        mismatches = run_ingest(conn, bundle, echo=typer.echo)
    for line in mismatches:
        typer.secho(f"Zeilenzahl weicht ab: {line}", fg=typer.colors.RED, err=True)
    if mismatches:
        raise typer.Exit(code=1)


@app.command()
def inputs(
    body: Annotated[list[str] | None, typer.Option(help="body_keys, z. B. CHE")] = None,
    since: Annotated[datetime | None, typer.Option(formats=DATE, help="Geschäfte ab Datum")] = None,
    limit: Annotated[int | None, typer.Option(min=1, help="höchstens so viele Geschäfte")] = None,
) -> None:
    """Klassifikationstexte bauen: HTML weg, Sprache, Längenlimit, input_hash (F3)."""
    from parltopics.db import connect
    from parltopics.inputs import build_inputs

    with connect(get_settings().database_url, autocommit=True) as conn:
        result = build_inputs(
            conn, bodies=body or None, since=since.date() if since else None, limit=limit
        )
    typer.echo(
        f"{result.changed} neu oder geändert, {result.unchanged} unverändert,"
        f" {result.skipped} ohne Text, {result.reopened} Jobs wieder geöffnet"
    )


@app.command()
def classify(
    task: Annotated[str, typer.Option(help="classify:aps (Ad-hoc und Nachklassifizierung: M2)")],
    body: Annotated[list[str] | None, typer.Option(help="body_keys")] = None,
    since: Annotated[datetime | None, typer.Option(formats=DATE, help="Geschäfte ab Datum")] = None,
    limit: Annotated[int | None, typer.Option(min=1, help="höchstens so viele Geschäfte")] = None,
    wait: Annotated[bool, typer.Option(help="Jobs im selben Prozess abarbeiten")] = True,
) -> None:
    """Lauf starten: Jobs öffnen und mit --wait gleich abarbeiten (F5, F18, F19)."""
    from parltopics.classify.queue import TASK_APS, acquire_run_lock, open_jobs
    from parltopics.classify.worker import load_classifier
    from parltopics.db import connect
    from parltopics.registry.sync import synced_version

    if task != TASK_APS:
        raise typer.BadParameter("In M1 gibt es nur classify:aps.", param_hint="--task")
    settings = get_settings()
    classifier = load_classifier(settings)
    # Die Verbindung hält die Lauf-Sperre, bis der Lauf mit --wait fertig ist.
    with connect(settings.database_url, autocommit=True) as conn:
        if synced_version(conn) != classifier.registry_version:
            typer.secho(
                "Registry nicht synchronisiert: zuerst `parltopics registry sync`.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(code=1)
        if not acquire_run_lock(conn, task):
            typer.secho(f"Ein Lauf für {task} läuft bereits.", fg=typer.colors.RED, err=True)
            raise typer.Exit(code=1)
        run = open_jobs(
            conn,
            task=task,
            bodies=body or None,
            since=since.date() if since else None,
            limit=limit,
            kind="full",
            registry_version=classifier.registry_version,
            scheme_hash=classifier.scheme_hash,
            prompt_version=classifier.prompt_version,
        )
        typer.echo(
            f"Lauf {run.run_id}: {run.total} Jobs ({run.new} neu, {run.reopened} wieder geöffnet)"
        )
        if wait and run.total:
            _run_worker(settings, task=task, run_id=run.run_id, once=True)


@app.command()
def worker(
    task: Annotated[str | None, typer.Option(help="nur diese Aufgabe")] = None,
    once: Annotated[bool, typer.Option(help="beenden, wenn keine Jobs mehr offen sind")] = False,
) -> None:
    """Worker: übernimmt offene Jobs nach Priorität; mehrere Prozesse parallel möglich (F19)."""
    _run_worker(get_settings(), task=task, once=once)


def _run_worker(settings: Settings, **options) -> None:
    import logging

    from parltopics.classify.worker import run_worker
    from parltopics.registry import RegistryError

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    try:
        counts = asyncio.run(run_worker(settings, **options))
    except RegistryError as error:
        typer.secho(str(error), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from error
    except KeyboardInterrupt:
        typer.echo("Abgebrochen; laufende Jobs gehen nach dem Timeout zurück auf open.", err=True)
        raise typer.Exit(code=130) from None
    typer.echo("Fertig: " + (", ".join(f"{n} {s}" for s, n in sorted(counts.items())) or "-"))


@jobs_app.command("summary")
def jobs_summary() -> None:
    """Jobs je Aufgabe und Status (F18)."""
    from parltopics.classify.queue import summary
    from parltopics.db import connect

    with connect(get_settings().database_url, autocommit=True) as conn:
        rows = summary(conn)
    if not rows:
        typer.echo("Keine Jobs.")
    for task, status, count in rows:
        typer.echo(f"  {task:<24} {status:<8} {count:>8}")


@app.command()
def adhoc(
    name: Annotated[str, typer.Argument(help="Name des Themas")],
    description_file: Annotated[Path, typer.Option(help="Beschreibung als Textdatei")],
) -> None:
    """Ad-hoc-Thema anlegen und über Kandidaten und Stichprobe auswerten (F8)."""
    _planned("M2", "F8")


@app.command()
def export(
    out: Annotated[Path, typer.Option(help="Zielverzeichnis")] = Path("dist/export"),
) -> None:
    """affair_topics.ndjson.gz und DVS-Liste schreiben (F11, F12)."""
    _planned("M3", "F11, F12")


@app.command()
def pages() -> None:
    """Seitenlauf: offene Seiten von den Tag-Seiten bis Heart zusammenfassen (F23–F25)."""
    _planned("M3", "F23–F25")


@app.command()
def wiki(
    out: Annotated[Path, typer.Option(help="Zielverzeichnis")] = Path("wiki"),
    affair: Annotated[int | None, typer.Option(help="nur dieses Geschäft exportieren")] = None,
) -> None:
    """Markdown-Export: Heart, Bereiche, Kapitel, Tag-Seiten, Querschnitt, Parlamente (F14)."""
    _planned("M3", "F14")


@app.command("eval")
def evaluate(
    gold: Annotated[Path, typer.Option(help="Gold-Set-Verzeichnis")] = Path("data/gold"),
) -> None:
    """Präzision, Recall, Baseline und Konfidenzbänder als Markdown-Bericht (F16)."""
    _planned("M2", "F16")
