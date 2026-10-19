"""Exportdateien (PRD F11, F12): affair_topics.ndjson.gz im OpenParlData-Stil mit Eintrag in
index.json, die DVS-Liste und das CSV-Format, das auch die API für Seiten ausliefert.

Die Exportdatei enthält die aktiven Labels freigegebener Themen; Labels vorläufiger Ad-hoc-Themen
(Status proposed) gehen nicht nach aussen.
"""

import csv
import gzip
import io
import json
from collections.abc import Iterable, Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import psycopg
from psycopg.rows import dict_row
from pydantic import BaseModel, ConfigDict, Field

from parltopics.api import queries

AFFAIR_TOPICS = "affair_topics.ndjson.gz"
DVS_LIST = "dvs_liste.csv"
DVS_LEVELS = ["country", "canton"]  # «Bund + Kantone» (F12)
ROWS = """
SELECT l.id, l.affair_id, a.body_key, l.tag_id AS topic_external_id,
       t.name_de AS topic_de, t.name_fr AS topic_fr, t.name_it AS topic_it, t.name_rm AS topic_rm,
       l.scheme, l.confidence::float AS confidence, l.model_version,
       greatest(l.created_at, l.reviewed_at) AS updated_at
FROM affair_tags l JOIN affairs a ON a.id = l.affair_id JOIN tags t ON t.tag_id = l.tag_id
WHERE l.status = 'active' AND t.status = 'active'
ORDER BY l.id
"""

# CSV wie der Export der Web-App (web/src/lib/export.ts): Spalten, Ebenen, Formelzeichen.
CSV_HEADER = [
    "OpenParlData-ID",
    "Nummer",
    "Titel",
    "Typ",
    "Parlament",
    "Ebene",
    "Datum",
    "Thema",
    "Konfidenz",
    "Beleg im Text gefunden",
    "Beleg",
    "Prüfstufe",
]
LEVEL_LABEL = {"country": "Bund", "canton": "Kanton", "city": "Stadt", "municipality": "Gemeinde"}
CSV_BLOCK = 1000


class AffairTopic(BaseModel):
    """Eine Zeile von affair_topics.ndjson.gz, snake_case wie die OpenParlData-Exporte."""

    model_config = ConfigDict(extra="forbid")

    id: int
    affair_id: int
    body_key: str
    topic_external_id: str
    topic_de: str
    topic_fr: str | None
    topic_it: str | None
    topic_rm: str | None
    scheme: Literal["aps", "adhoc"]
    confidence: float = Field(ge=0, le=1)
    model_version: str
    updated_at: datetime


def csv_cell(value: object) -> str:
    """Leer für None; ein Formelzeichen am Anfang wird mit ' entschärft (Tabellenkalkulation)."""
    text = "" if value is None else str(value)
    return f"'{text}" if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


def affairs_csv(rows: Iterable[dict]) -> Iterator[str]:
    """Semikolon, UTF-8 mit BOM, CRLF; gibt die Zeilen in Blöcken zu CSV_BLOCK aus."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";", lineterminator="\r\n")
    buffer.write("﻿")
    writer.writerow(CSV_HEADER)
    for count, row in enumerate(rows, start=1):
        level = row["body_level"]
        values = [
            row["affair_id"],
            row["number"],
            row["title"],
            row["type_de"] or row["type"],
            row["body_name"] or row["body_key"],
            LEVEL_LABEL.get(level, level) if level else None,
            row["begin_date"],
            row["name_de"],
            f"{row['confidence']:.2f}",
            "ja" if row["evidence_verified"] else "nein",
            row["evidence"],
            "Mensch" if row["stage"] == "human" else row["stage"],
        ]
        writer.writerow([csv_cell(value) for value in values])
        if count % CSV_BLOCK == 0:
            yield buffer.getvalue()
            buffer.seek(0)
            buffer.truncate()
    yield buffer.getvalue()


def update_index(out: Path, entry: dict) -> None:
    """index.json wie auf files.openparldata.ch: eine Liste files, je Dateiname ein Eintrag."""
    path = out / "index.json"
    index = json.loads(path.read_text("utf-8")) if path.exists() else {"files": []}
    others = [file for file in index["files"] if file.get("filename") != entry["filename"]]
    index["files"] = [*others, entry]
    path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")


def write_affair_topics(conn: psycopg.Connection, out: Path) -> int:
    """Schreibt die aktiven Labels Zeile für Zeile, geprüft gegen AffairTopic, und trägt die Datei
    in index.json ein (Felder wie bei OpenParlData). Gibt die Zahl der Zeilen zurück."""
    out.mkdir(parents=True, exist_ok=True)
    path = out / AFFAIR_TOPICS
    count = 0
    with gzip.open(path, "wt", encoding="utf-8", newline="\n") as file:
        for row in conn.cursor(row_factory=dict_row).stream(ROWS):
            file.write(AffairTopic(**row).model_dump_json() + "\n")
            count += 1
    created = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    entry = {"entity": "affair_topics", "type": "single", "filename": AFFAIR_TOPICS}
    update_index(
        out, {**entry, "size": path.stat().st_size, "row_count": count, "created": created}
    )
    return count


def write_dvs_list(conn: psycopg.Connection, out: Path, tag_ids: list[str]) -> int:
    """DVS-Liste (F12): Geschäfte dieser Themen von Bund und Kantonen, nur laufende, als CSV wie
    GET /v1/pages/{page_id}/affairs.csv?level=country&level=canton&running=true."""
    out.mkdir(parents=True, exist_ok=True)
    rows = list(queries.stream_topic_affairs(conn, tag_ids, level=DVS_LEVELS, running=True))
    with (out / DVS_LIST).open("w", encoding="utf-8", newline="") as file:
        file.writelines(affairs_csv(rows))
    return len(rows)
