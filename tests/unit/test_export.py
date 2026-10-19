import json

import pytest
from pydantic import ValidationError

from parltopics import export
from parltopics.export import AffairTopic, affairs_csv, update_index


def test_csv_comes_in_blocks_with_bom_crlf_and_defused_formulas(monkeypatch):
    row = {
        "affair_id": 1,
        "number": "@x",
        "title": "a;b",
        "type_de": None,
        "type": "Motion",
        "body_name": None,
        "body_key": "ZH",
        "body_level": "canton",
        "begin_date": None,
        "name_de": "Digitalisierung",
        "confidence": 0.5,
        "evidence_verified": True,
        "evidence": "=1",
        "stage": "human",
    }
    whole = "".join(affairs_csv([row] * 3))
    monkeypatch.setattr(export, "CSV_BLOCK", 2)
    chunks = list(affairs_csv([row] * 3))
    assert (len(chunks), "".join(chunks)) == (2, whole)
    assert whole.startswith("﻿OpenParlData-ID;Nummer;")
    line = "1;'@x;\"a;b\";Motion;ZH;Kanton;;Digitalisierung;0.50;ja;'=1;Mensch"
    assert whole.split("\r\n")[1] == line


ROW = {
    "id": 7,
    "affair_id": 70435,
    "body_key": "CHE",
    "topic_external_id": "aps:6.1.9",
    "topic_de": "Digitalisierung",
    "topic_fr": "Numérisation",
    "topic_it": None,
    "topic_rm": None,
    "scheme": "aps",
    "confidence": 0.86,
    "model_version": "apertus-v1-5-70b",
    "updated_at": "2026-10-19T01:00:00Z",
}


@pytest.mark.parametrize(
    "broken", [{"scheme": "curia"}, {"confidence": 1.2}, {"topic_de": None}, {"extra": 1}]
)
def test_export_rows_are_checked_against_the_schema(broken):
    assert json.loads(AffairTopic(**ROW).model_dump_json())["topic_external_id"] == "aps:6.1.9"
    with pytest.raises(ValidationError):
        AffairTopic(**{**ROW, **broken})


def test_index_keeps_other_files_and_replaces_the_own_entry(tmp_path):
    (tmp_path / "index.json").write_text(
        json.dumps(
            {"files": [{"filename": "affairs.ndjson.gz"}, {"filename": "x.gz", "row_count": 1}]}
        ),
        encoding="utf-8",
    )
    update_index(tmp_path, {"filename": "x.gz", "row_count": 2})
    files = json.loads((tmp_path / "index.json").read_text("utf-8"))["files"]
    assert files == [{"filename": "affairs.ndjson.gz"}, {"filename": "x.gz", "row_count": 2}]
    fresh = tmp_path / "neu"
    fresh.mkdir()
    update_index(fresh, {"filename": "y.gz"})
    assert json.loads((fresh / "index.json").read_text("utf-8")) == {
        "files": [{"filename": "y.gz"}]
    }
