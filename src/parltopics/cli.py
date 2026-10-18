"""Kommandozeile `parltopics` (PRD 10.4).

Funktionsfähig: version, db migrate, registry validate, llm check.
Die übrigen Kommandos zeigen ihre geplante Schnittstelle und nennen ihren Meilenstein.
"""

import asyncio
from pathlib import Path
from typing import Annotated

import typer

from parltopics import __version__
from parltopics.config import get_settings

NOT_IMPLEMENTED_EXIT = 3

app = typer.Typer(
    help="ParlTopics: Themen-Klassifikation für OpenParlData mit Apertus.", no_args_is_help=True
)
db_app = typer.Typer(help="Datenbank und Migrationen.", no_args_is_help=True)
registry_app = typer.Typer(help="Tag-Registry registry/tags.yaml.", no_args_is_help=True)
llm_app = typer.Typer(help="LLM-Endpunkt (LLM_BASE_URL).", no_args_is_help=True)
app.add_typer(db_app, name="db")
app.add_typer(registry_app, name="registry")
app.add_typer(llm_app, name="llm")


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
    """Registry in die Tabelle tags spiegeln; geänderte Datei ohne neue Version ablehnen."""
    _planned("M0", "F4")


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
    from parltopics.llm import LLMClient

    settings = get_settings()

    async def run() -> list[tuple[str, bool, str]]:
        results = []
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
                else:
                    detail = (
                        f"{reply.duration_ms} ms, Modell {reply.model}, Antwort {reply.content!r}"
                    )
                    results.append((name, True, detail))
        return results

    typer.echo(f"Endpunkt: {settings.llm_base_url}")
    failed = False
    for name, ok, detail in asyncio.run(run()):
        failed |= not ok
        mark = (
            typer.style("ok    ", fg=typer.colors.GREEN) if ok else typer.style("FEHLER", fg="red")
        )
        typer.echo(f"  {mark} {name}: {detail}")
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
    _planned("M0", "F1")


@app.command()
def ingest(
    bundle: Annotated[Path, typer.Option(help="Import-Bündel")] = Path("data/import"),
) -> None:
    """Import-Bündel in PostgreSQL laden, Zeilenzahlen prüfen (F2)."""
    _planned("M0", "F2")


@app.command()
def inputs() -> None:
    """Klassifikationstexte bauen: HTML weg, Sprache, Längenlimit, input_hash (F3)."""
    _planned("M0", "F3")


@app.command()
def classify(
    task: Annotated[str, typer.Option(help="classify:aps, classify:adhoc:<tag>, reclassify:<tag>")],
    body: Annotated[list[str] | None, typer.Option(help="body_keys")] = None,
    since: Annotated[str | None, typer.Option(help="Geschäfte ab Datum, JJJJ-MM-TT")] = None,
    wait: Annotated[bool, typer.Option(help="Jobs im selben Prozess abarbeiten")] = True,
) -> None:
    """Jobs öffnen und einen Lauf starten (F5, F18)."""
    _planned("M1", "F5, F18")


@app.command()
def worker() -> None:
    """Dauerhafter Worker: übernimmt offene Jobs aller Aufgaben nach Priorität (F19)."""
    _planned("M1", "F19")


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
def wiki(
    out: Annotated[Path, typer.Option(help="Zielverzeichnis")] = Path("wiki"),
    affair: Annotated[int | None, typer.Option(help="nur dieses Geschäft exportieren")] = None,
) -> None:
    """Markdown-Export für Themen- und Parlamentsseiten (F14)."""
    _planned("M3", "F14")


@app.command("eval")
def evaluate(
    gold: Annotated[Path, typer.Option(help="Gold-Set-Verzeichnis")] = Path("data/gold"),
) -> None:
    """Präzision, Recall, Baseline und Konfidenzbänder als Markdown-Bericht (F16)."""
    _planned("M2", "F16")
