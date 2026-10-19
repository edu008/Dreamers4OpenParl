"""Download der OpenParlData-Exporte in ein Import-Bündel (PRD F1).

Online-Schritt. Das Bündel ist ein Verzeichnis mit `index.json` und den Exportdateien in
derselben Struktur wie auf files.openparldata.ch. Ein zweiter Lauf lädt nur geänderte Dateien.
"""

import json
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import httpx

BASE_URL = "https://files.openparldata.ch/exports"
ENTITIES = ("bodies", "affairs", "texts", "docs", "contributors")


def select_files(
    index: dict[str, Any], bodies: list[str] | None = None
) -> Iterator[dict[str, Any]]:
    """Dateien der Entitäten aus ENTITIES; aufgeteilte Exporte nur für die gewählten body_keys."""
    for entry in index["files"]:
        entity = entry.get("entity")
        if entity not in ENTITIES:
            continue
        if entry["type"] == "single":
            yield {**entry, "path": entry["filename"]}
            continue
        for part in entry["files"]:
            body_key = part["filename"].removeprefix(f"{entity}_").removesuffix(".ndjson.gz")
            if bodies is None or body_key in bodies:
                yield {**part, "entity": entity, "path": entry["directory"] + part["filename"]}


def download(
    bundle: Path,
    bodies: list[str] | None = None,
    *,
    client: httpx.Client | None = None,
    echo: Callable[[str], Any] = print,
) -> tuple[int, int]:
    """Lädt index.json und alle gewählten Dateien. Gibt (geladen, unverändert) zurück.

    Eine Datei gilt als unverändert, wenn sie mit gleicher Grösse vorliegt und `created` im
    bisherigen index.json gleich ist. index.json wird erst am Ende geschrieben, damit ein
    abgebrochener Lauf beim nächsten Mal alles Fehlende nachholt.
    """
    client = client or httpx.Client(timeout=httpx.Timeout(60.0, read=300.0), follow_redirects=True)
    bundle.mkdir(parents=True, exist_ok=True)
    index_path = bundle / "index.json"
    previous = json.loads(index_path.read_text("utf-8")) if index_path.exists() else None
    old = {f["path"]: f for f in select_files(previous)} if previous else {}

    response = client.get(f"{BASE_URL}/index.json")
    response.raise_for_status()
    index = response.json()

    loaded = unchanged = 0
    for entry in select_files(index, bodies):
        target = bundle / entry["path"]
        if (
            target.exists()
            and target.stat().st_size == entry["size"]
            and old.get(entry["path"], {}).get("created") == entry["created"]
        ):
            unchanged += 1
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        partial = target.with_name(target.name + ".part")
        with client.stream("GET", entry["url"]) as stream, partial.open("wb") as out:
            stream.raise_for_status()
            for chunk in stream.iter_bytes(1 << 20):
                out.write(chunk)
        if partial.stat().st_size != entry["size"]:
            raise RuntimeError(
                f"{entry['path']}: {partial.stat().st_size} statt {entry['size']} Bytes"
            )
        partial.replace(target)
        loaded += 1
        echo(f"  geladen {entry['path']} ({entry.get('size_human', entry['size'])})")

    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=1), "utf-8")
    return loaded, unchanged
