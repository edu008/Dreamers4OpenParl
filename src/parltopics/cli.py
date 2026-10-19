"""Kommandozeile `parltopics` (PRD 10.4).

Kommandos, die noch nicht umgesetzt sind, zeigen ihre geplante Schnittstelle, nennen ihren
Meilenstein und enden mit Exit-Code 3.
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
proposals_app = typer.Typer(help="Tag-Vorschläge des Modells (F7).", no_args_is_help=True)
app.add_typer(db_app, name="db")
app.add_typer(registry_app, name="registry")
app.add_typer(llm_app, name="llm")
app.add_typer(jobs_app, name="jobs")
app.add_typer(proposals_app, name="proposals")


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


@registry_app.command("activate")
def registry_activate(
    tag_id: Annotated[str, typer.Argument(help="Ad-hoc-Tag, z. B. adhoc:velowege")],
    by: Annotated[str, typer.Option(help="wer freischaltet")] = "cli",
) -> None:
    """Ad-hoc-Thema freischalten: proposed → active, danach in Stufe 2 von classify:aps."""
    from parltopics.classify.adhoc import activate
    from parltopics.db import connect
    from parltopics.registry import RegistryError

    settings = get_settings()
    try:
        with connect(settings.database_url, autocommit=True) as conn:
            registry = activate(conn, settings, tag_id, by=by)
    except RegistryError as error:
        typer.secho(str(error), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from error
    typer.echo(f"{tag_id} ist aktiv, registry_version {registry.registry_version}")


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


@registry_app.command("apply-descriptions")
def registry_apply_descriptions() -> None:
    """Beschreibungen und Synonyme aus registry/aps_descriptions.yaml übernehmen."""
    from parltopics.registry import RegistryError
    from parltopics.registry.aps_import import refresh_descriptions

    registry_path = get_settings().registry_path
    try:
        count, version = refresh_descriptions(registry_path)
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
        f" {result.skipped} ohne Text, {result.reopened} Jobs wieder geöffnet,"
        f" {result.indexed} im Volltext neu"
    )


@app.command()
def classify(
    task: Annotated[str, typer.Option(help="classify:aps; Ad-hoc-Themen: parltopics adhoc")],
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
        raise typer.BadParameter(
            "classify öffnet nur classify:aps; Ad-hoc-Themen legt `parltopics adhoc` an.",
            param_hint="--task",
        )
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


@proposals_app.command("group")
def proposals_group(
    model: Annotated[bool, typer.Option(help="Empfehlung von 70B; ohne: nur Bezeichnungen")] = True,
) -> None:
    """Rohvorschläge gruppieren und gegen die Registry prüfen; nach jedem Lauf (ARCHITEKTUR 2)."""
    from parltopics.classify.proposals import group
    from parltopics.db import connect

    settings = get_settings()
    with connect(settings.database_url, autocommit=True) as conn:
        result = asyncio.run(group(conn, settings, use_model=model))
    typer.echo(
        f"{result.created} neue Vorschläge ({result.checked} mit Empfehlung von 70B),"
        f" {result.attached} Rohvorschläge zu bestehenden"
    )


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
    name: Annotated[str, typer.Argument(help="Name des Themas (Deutsch)")],
    description_file: Annotated[Path, typer.Option(help="Beschreibung als Textdatei")],
    keywords_file: Annotated[
        Path | None,
        typer.Option(help='Stichwörter als JSON {"de": [], "fr": [], "it": []}; sonst von 70B'),
    ] = None,
    body: Annotated[list[str] | None, typer.Option(help="nur diese Parlamente")] = None,
    since: Annotated[datetime | None, typer.Option(formats=DATE, help="ab Datum")] = None,
    broader: Annotated[list[str] | None, typer.Option(help="APS-Tags für die Verlinkung")] = None,
    by: Annotated[str, typer.Option(help="wer das Thema anlegt")] = "cli",
    yes: Annotated[bool, typer.Option("--yes", help="ohne Rückfrage anlegen")] = False,
    wait: Annotated[bool, typer.Option(help="die Jobs gleich abarbeiten")] = False,
) -> None:
    """Ad-hoc-Thema anlegen und über Kandidaten und Stichprobe auswerten (F8)."""
    from parltopics.classify import adhoc as topics
    from parltopics.classify.queue import adhoc_task
    from parltopics.db import connect
    from parltopics.registry import RegistryError

    settings = get_settings()
    description = description_file.read_text(encoding="utf-8").strip()
    if keywords_file is not None:
        keywords = topics.Keywords.model_validate_json(keywords_file.read_text(encoding="utf-8"))
    else:
        keywords = asyncio.run(topics.suggest_keywords(settings, name, description))
    day = since.date() if since else None
    with connect(settings.database_url, autocommit=True) as conn:
        candidates, sample = topics.find_affairs(conn, keywords, bodies=body or None, since=day)
        typer.echo(f"Stichwörter: {keywords.model_dump_json()}")
        typer.echo(f"{len(candidates)} Kandidaten, {len(sample)} Geschäfte in der Stichprobe")
        if not yes:
            typer.confirm("Thema als proposed anlegen und die Jobs öffnen?", abort=True)
        try:
            created = topics.create(
                conn,
                settings,
                name_de=name,
                definition_de=description,
                keywords=keywords,
                by=by,
                broader=broader or None,
                bodies=body or None,
                since=day,
            )
        except RegistryError as error:
            typer.secho(str(error), fg=typer.colors.RED, err=True)
            raise typer.Exit(code=1) from error
    typer.echo(
        f"{created.tag_id} angelegt (registry_version {created.registry_version}),"
        f" Lauf {created.run.run_id} mit {created.run.total} Jobs"
    )
    if wait:
        _run_worker(settings, task=adhoc_task(created.tag_id), once=True)


@app.command()
def export(
    out: Annotated[Path, typer.Option(help="Zielverzeichnis")] = Path("dist/export"),
    dvs_topic: Annotated[
        str, typer.Option(help="Seite der DVS-Liste, mit allen Themen darunter")
    ] = "adhoc:digitalisierung-breit",
) -> None:
    """affair_topics.ndjson.gz mit index.json und die DVS-Liste dvs_liste.csv schreiben (F11, F12).

    Die DVS-Liste enthält die laufenden Geschäfte von Bund und Kantonen mit aktivem Label.
    """
    from parltopics.db import connect
    from parltopics.export import write_affair_topics, write_dvs_list
    from parltopics.registry import load_registry
    from parltopics.wiki.tree import build_tree, subtree_tag_ids

    settings = get_settings()
    tree = build_tree(load_registry(settings.registry_path))
    if dvs_topic not in tree:
        typer.secho(f"Seite {dvs_topic} gibt es nicht", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2)
    with connect(settings.database_url, autocommit=True) as conn:
        labels = write_affair_topics(conn, out)
        dvs = write_dvs_list(conn, out, subtree_tag_ids(tree, dvs_topic))
    typer.echo(
        f"{out}: affair_topics.ndjson.gz mit {labels} Labels, dvs_liste.csv mit {dvs} Zeilen"
    )


@app.command()
def pages() -> None:
    """Seitenlauf: offene Seiten von den Tag-Seiten bis Heart zusammenfassen (F23–F25).

    Alle Seiten mit 70B (ARCHITEKTUR 5.1); Kennzahlen für alle Seiten bei jedem Lauf. Bei gleichem
    Input keine neue Zusammenfassung.
    """
    from collections import Counter

    from parltopics.classify.queue import acquire_run_lock
    from parltopics.db import connect
    from parltopics.registry import load_registry
    from parltopics.registry.sync import synced_version
    from parltopics.wiki.run import run
    from parltopics.wiki.tree import build_tree

    settings = get_settings()
    registry = load_registry(settings.registry_path)
    tree = build_tree(registry)
    with connect(settings.database_url, autocommit=True) as conn:
        if synced_version(conn) != registry.registry_version:
            typer.secho(
                "Registry nicht synchronisiert: zuerst `parltopics registry sync`.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(code=1)
        if not acquire_run_lock(conn, "pages"):
            typer.secho("Ein Seitenlauf läuft bereits.", fg=typer.colors.RED, err=True)
            raise typer.Exit(code=1)
        page_run = asyncio.run(run(settings, conn, registry, tree))
    counts = Counter(page_run.outcomes.values())
    typer.echo(
        f"Seitenlauf {page_run.run_key}: {len(page_run.outcomes)} von {len(tree)} Seiten gebaut,"
        f" {counts['changed']} geändert, {counts['unchanged']} unverändert,"
        f" {counts['failed']} fehlgeschlagen"
    )
    for page_id, outcome in sorted(page_run.outcomes.items()):
        if outcome == "failed":
            error = page_run.result.states[page_id].last_error
            typer.secho(f"  {page_id}: {error}", fg=typer.colors.RED, err=True)


@app.command()
def wiki(
    out: Annotated[Path, typer.Option(help="Zielverzeichnis")] = Path("wiki"),
    affair: Annotated[int | None, typer.Option(help="nur dieses Geschäft exportieren")] = None,
) -> None:
    """Markdown-Export: Heart, Bereiche, Kapitel, Tag-Seiten, Querschnitt, Parlamente (F14)."""
    _planned("M3", "F14")


@app.command("eval")
def evaluate(
    gold: Annotated[
        Path,
        typer.Option(help="Gold-Verzeichnis mit politmonitor_ und dvs_digitalisierung.csv"),
    ] = Path("data/gold"),
    out: Annotated[Path, typer.Option(help="Markdown-Bericht")] = Path("data/eval/report.md"),
    curia: Annotated[
        Path | None,
        typer.Option(help="che_affairs_keywords.csv: aktive APS-Labels gegen Curia Vista prüfen"),
    ] = None,
    since: Annotated[
        datetime, typer.Option(formats=DATE, help="mit --curia: nur Bundesgeschäfte ab Datum")
    ] = datetime(2024, 1, 1),
    run: Annotated[
        list[int] | None, typer.Option(help="mit --curia: nur Labels dieser Läufe")
    ] = None,
) -> None:
    """Präzision, Recall, Baseline und Konfidenzbänder als Markdown-Bericht (F16).

    Mit --curia statt des Berichts: grobe Kontrolle der APS-Labels gegen die
    Curia-Vista-Sachbereiche (PRD 13). Liest die Datenbank nur.
    """
    from parltopics.db import connect
    from parltopics.registry import load_registry

    settings = get_settings()
    registry = load_registry(settings.registry_path)
    if curia is None:
        from parltopics.evaluation.report import GoldFileError, build, read_gold_dir

        try:
            files = read_gold_dir(gold)
        except GoldFileError as error:
            typer.secho(str(error), fg=typer.colors.RED, err=True)
            raise typer.Exit(code=1) from error
        with connect(settings.database_url) as conn:
            conn.read_only = True
            report = build(conn, registry, settings, gold, files)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(report + "\n", encoding="utf-8")
        typer.echo(f"Bericht geschrieben: {out}")
        return
    from parltopics.evaluation.curia import TARGET, load_curia, score, tag_areas

    with connect(settings.database_url) as conn:
        rows = conn.execute(
            "SELECT l.affair_id, l.tag_id, l.confidence::float FROM affair_tags l"
            " JOIN affairs a ON a.id = l.affair_id"
            " WHERE l.status = 'active' AND a.body_key = 'CHE' AND a.begin_date >= %s"
            " AND (%s::int[] IS NULL OR l.run_id = ANY(%s::int[]))",
            (since.date(), run, run),
        ).fetchall()
    predictions: dict[int, list[tuple[str, float]]] = {}
    for affair_id, tag_id, confidence in rows:
        predictions.setdefault(affair_id, []).append((tag_id, confidence))
    result = score(predictions, load_curia(curia), tag_areas(registry))
    typer.echo(
        f"Curia-Vista-Check, registry {registry.registry_version}, CHE ab {since.date()}:"
        f" {result.affairs} Geschäfte, {result.labels} APS-Labels\n"
        f"  mindestens ein Treffer  {result.any_hit:6.1%}   (Ziel PRD 13: {TARGET:.0%})\n"
        f"  Top-1-Label trifft      {result.top1:6.1%}\n"
        f"  Labels, die treffen     {result.precision:6.1%}"
    )
