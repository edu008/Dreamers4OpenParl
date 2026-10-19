"""Import-Bündel nach PostgreSQL laden, inkrementell, mit Zeilenzahl-Prüfung (PRD F2).

Jede Exportdatei kommt per COPY in eine temporäre Tabelle und von dort per Upsert in die
Quelltabelle. Geschrieben werden nur neue oder geänderte Zeilen, ein zweiter Lauf ändert nichts.
`raw` enthält den Originaldatensatz ohne das Feld, das schon in `text` steht. Die Beteiligten
(contributors) haben kein `raw`, gespeichert sind nur Rolle und Partei (Migration 0007).
"""

import gzip
import itertools
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from parltopics.download import ENTITIES, select_files

LANGS = ("de", "fr", "it", "rm")
Record = dict[str, Any]


def _date(value: str | None) -> str | None:
    return value[:10] if value else None


def _first(record: Record, prefix: str) -> Any:
    return next(
        (record[f"{prefix}_{lang}"] for lang in LANGS if record.get(f"{prefix}_{lang}")), None
    )


def body_row(r: Record) -> Record:
    languages = [lang.strip().lower() for lang in (r.get("languages") or "").split(",")]
    return {
        "id": r["id"],
        "body_key": r["body_key"],
        "name": r.get("name_de") or r.get("name"),
        "level": r.get("type"),
        "languages": [lang for lang in languages if lang],
        "raw": Jsonb(r),
        "updated_at": r.get("updated_at"),
    }


def affair_row(r: Record) -> Record:
    return {
        "id": r["id"],
        "body_key": r["body_key"],
        "body_id": r.get("body_id"),
        "number": r.get("number"),
        "external_id": r.get("external_id"),
        **{f"title_{lang}": r.get(f"title_{lang}") for lang in LANGS},
        "type_harmonized_en": r.get("type_harmonized_en"),
        "begin_date": _date(r.get("begin_date")),
        "url_external": _first(r, "url_external"),
        "raw": Jsonb(r),
        "updated_at": r.get("updated_at"),
    }


def text_row(r: Record) -> Record:
    # Ein Datensatz trägt alle Sprachen: `text` bekommt die erste, die übrigen bleiben in raw.
    lang = next((lang for lang in LANGS if r.get(f"text_{lang}")), None)
    return {
        "id": r["id"],
        "affair_id": r["affair_id"],
        "text_type": _first(r, "type"),
        "language": lang,
        "format": r.get("text_format"),
        "text": r.get(f"text_{lang}") if lang else None,
        "raw": Jsonb({k: v for k, v in r.items() if k != f"text_{lang}"}),
        "updated_at": r.get("updated_at"),
    }


def doc_row(r: Record) -> Record:
    parent = r.get("parent_type")
    return {
        "id": r["id"],
        "parent_type": parent,
        # affair_id, meeting_id, news_id, agenda_id; bei manchen Bundes-Docs leer (Quelle).
        "parent_id": r.get(f"{parent}_id") if parent else None,
        "name": r.get("name"),
        "category": r.get("category_harmonized"),
        "doc_date": _date(r.get("date")),
        "language": r.get("language"),
        "text": r.get("text"),
        "raw": Jsonb({k: v for k, v in r.items() if k != "text"}),
        "updated_at": r.get("updated_at"),
    }


def contributor_row(r: Record) -> Record:
    return {
        "id": r["id"],
        "affair_id": r.get("affair_id"),  # leer bei Beteiligten an News und Sitzungen
        "type": r.get("type"),
        "role": r.get("role_harmonized"),
        "role_external_id": r.get("role_external_id"),
        "name": r.get("fullname"),
        "party": r.get("party_harmonized_de"),
        "position": r.get("position"),
        "updated_at": r.get("updated_at"),
    }


TABLES: dict[str, tuple[str, Callable[[Record], Record]]] = {
    "bodies": ("bodies", body_row),
    "affairs": ("affairs", affair_row),
    "texts": ("affair_texts", text_row),
    "docs": ("affair_docs", doc_row),
    "contributors": ("affair_contributors", contributor_row),
}


def parse_line(line: bytes) -> Record:
    # PostgreSQL lehnt NUL in text und jsonb ab; PDF-Texte enthalten es gelegentlich.
    return json.loads(line.replace(b"\\u0000", b""))


def load_file(
    conn: psycopg.Connection, table: str, mapper: Callable[[Record], Record], path: Path
) -> tuple[int, int]:
    """Lädt eine Exportdatei. Gibt (gelesene Zeilen, neu oder geändert) zurück."""
    with gzip.open(path) as lines:
        first = next(lines, None)
        if first is None:
            return 0, 0
        columns = list(mapper(parse_line(first)))
        cols = ", ".join(columns)
        updates = ", ".join(f"{c} = EXCLUDED.{c}" for c in columns if c != "id")
        old = ", ".join(f"t.{c}" for c in columns)
        new = ", ".join(f"EXCLUDED.{c}" for c in columns)
        read = 0
        with conn.transaction():
            conn.execute("SET LOCAL TimeZone = 'UTC'")
            conn.execute(f"CREATE TEMP TABLE stage (LIKE {table}) ON COMMIT DROP")
            with conn.cursor().copy(f"COPY stage ({cols}) FROM STDIN") as copy:
                for line in itertools.chain([first], lines):
                    record = mapper(parse_line(line))
                    copy.write_row([record[c] for c in columns])
                    read += 1
            changed = conn.execute(
                f"INSERT INTO {table} AS t ({cols})"
                f" SELECT DISTINCT ON (id) {cols} FROM stage ORDER BY id"
                f" ON CONFLICT (id) DO UPDATE SET {updates}"
                f" WHERE ROW({old}) IS DISTINCT FROM ROW({new})"
            ).rowcount
    return read, changed


def ingest(
    conn: psycopg.Connection, bundle: Path, *, echo: Callable[[str], Any] = print
) -> list[str]:
    """Lädt alle vorhandenen Dateien des Bündels. Gibt Abweichungen zu index.json zurück."""
    index = json.loads((bundle / "index.json").read_text("utf-8"))
    entries = sorted(select_files(index), key=lambda e: ENTITIES.index(e["entity"]))
    mismatches = []
    for entry in entries:
        path = bundle / entry["path"]
        if not path.exists():
            continue  # nicht heruntergeladen, z. B. andere body_keys
        table, mapper = TABLES[entry["entity"]]
        read, changed = load_file(conn, table, mapper, path)
        echo(f"  {entry['path']:<32} {read:>8} Zeilen, {changed:>8} neu oder geändert")
        if read != entry["row_count"]:
            mismatches.append(
                f"{entry['path']}: {read} Zeilen, index.json nennt {entry['row_count']}"
            )
    return mismatches
