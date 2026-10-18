"""Ingest eines kleinen Import-Bündels gegen ein echtes PostgreSQL (PRD F2)."""

import gzip
import json

import pytest

from parltopics.db import migrate
from parltopics.ingest import ingest

pytestmark = pytest.mark.integration

BODY = {
    "id": 42,
    "body_key": "CHE",
    "name": "Schweiz",
    "name_de": "Schweiz",
    "type": "country",
    "languages": "DE,FR,IT",
}
AFFAIR = {
    "id": 1,
    "body_key": "CHE",
    "body_id": 42,
    "number": "24.001",
    "title_de": "Titel",
    "type_harmonized_en": "Motion",
    "begin_date": "2024-03-01T00:00:00",
    "updated_at": "2026-10-01T10:00:00",
}
TEXT = {
    "id": 10,
    "affair_id": 1,
    "text_de": "<p>Text\u0000</p>",
    "type_de": "Eingereichter Text",
    "text_format": "html",
    "updated_at": "2026-10-01T10:00:00",
}
DOC = {
    "id": 20,
    "parent_type": "affair",
    "affair_id": 1,
    "name": "a.pdf",
    "text": "PDF",
    "date": "2024-03-02T00:00:00",
    "language": "de",
}


def write_bundle(path, affairs, row_count=None):
    files = {
        "bodies.ndjson.gz": [BODY],
        "affairs.ndjson.gz": affairs,
        "texts/texts_CHE.ndjson.gz": [TEXT],
        "docs/docs_CHE.ndjson.gz": [DOC],
    }
    entries = {}
    for name, rows in files.items():
        (path / name).parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(path / name, "wt", encoding="utf-8") as out:
            out.writelines(json.dumps(row) + "\n" for row in rows)
        entries[name] = {
            "filename": name.split("/")[-1],
            "url": "",
            "size": 0,
            "created": "",
            "row_count": len(rows) if row_count is None else row_count,
        }
    index = {
        "files": [
            {"entity": "bodies", "type": "single", **entries["bodies.ndjson.gz"]},
            {"entity": "affairs", "type": "single", **entries["affairs.ndjson.gz"]},
            {
                "entity": "texts",
                "type": "split",
                "directory": "texts/",
                "files": [entries["texts/texts_CHE.ndjson.gz"]],
            },
            {
                "entity": "docs",
                "type": "split",
                "directory": "docs/",
                "files": [entries["docs/docs_CHE.ndjson.gz"]],
            },
        ]
    }
    (path / "index.json").write_text(json.dumps(index))


def changed(output):
    return [int(line.split(",")[1].split()[0]) for line in output]


def test_ingest_loads_and_is_idempotent(conn, repo_root, tmp_path):
    migrate(conn, repo_root / "migrations")
    write_bundle(tmp_path, [AFFAIR])

    out: list[str] = []
    assert ingest(conn, tmp_path, echo=out.append) == []
    assert changed(out) == [1, 1, 1, 1]
    row = conn.execute("SELECT begin_date::text, raw->>'number' FROM affairs").fetchone()
    assert row == ("2024-03-01", "24.001")
    assert conn.execute("SELECT text, language FROM affair_texts").fetchone() == (
        "<p>Text</p>",
        "de",
    )
    assert conn.execute("SELECT parent_id, raw ? 'text' FROM affair_docs").fetchone() == (1, False)
    assert conn.execute("SELECT languages FROM bodies").fetchone() == (["de", "fr", "it"],)

    out.clear()
    ingest(conn, tmp_path, echo=out.append)
    assert changed(out) == [0, 0, 0, 0]

    write_bundle(tmp_path, [{**AFFAIR, "title_de": "Neu"}, {**AFFAIR, "id": 2}])
    out.clear()
    ingest(conn, tmp_path, echo=out.append)
    assert changed(out) == [0, 2, 0, 0]
    assert conn.execute("SELECT count(*) FROM affairs").fetchone() == (2,)


def test_ingest_reports_row_count_mismatch(conn, repo_root, tmp_path):
    migrate(conn, repo_root / "migrations")
    write_bundle(tmp_path, [AFFAIR], row_count=5)
    mismatches = ingest(conn, tmp_path, echo=lambda _: None)
    assert len(mismatches) == 4
    assert "index.json nennt 5" in mismatches[1]
