"""Dateien des Hack-Datensatzes im Gold-Verzeichnis und Stichwörter der Baseline (PRD F16)."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from parltopics.cli import app
from parltopics.evaluation.report import (
    DVS,
    POLITMONITOR,
    GoldFileError,
    keywords,
    load_ids,
    read_gold_dir,
)
from parltopics.registry import load_registry

GOLD = Path(__file__).resolve().parents[1] / "fixtures" / "gold"
REGISTRY = Path(__file__).resolve().parents[1] / "fixtures" / "tags_example.yaml"


def test_the_gold_directory_yields_ids_per_file():
    assert read_gold_dir(GOLD) == {POLITMONITOR: {200, 201, 203, 999}, DVS: {200, 201, 202, 998}}


def test_missing_files_are_reported_as_none(tmp_path: Path):
    assert read_gold_dir(tmp_path) == {POLITMONITOR: None, DVS: None}


def test_ids_survive_a_byte_order_mark_and_empty_cells(tmp_path: Path):
    path = tmp_path / "x.csv"
    path.write_text("﻿openparldata_id;title\n", encoding="utf-8")  # Semikolon: eine Spalte
    with pytest.raises(GoldFileError, match="Gefundene Spalten: openparldata_id;title"):
        load_ids(path)
    path.write_text("﻿openparldata_id,title\n7,a\n,b\n 8 ,c\n", encoding="utf-8")
    assert load_ids(path) == {7, 8}


def test_a_value_that_is_no_id_names_its_line(tmp_path: Path):
    path = tmp_path / "x.csv"
    path.write_text("openparldata_id\n7\n12a\n", encoding="utf-8")
    with pytest.raises(GoldFileError, match="Zeile 3"):
        load_ids(path)


def test_eval_stops_with_the_found_columns_before_touching_the_database(tmp_path: Path):
    (tmp_path / POLITMONITOR).write_text("affair_id,title\n1,a\n", encoding="utf-8")
    result = CliRunner().invoke(app, ["eval", "--gold", str(tmp_path)])
    assert result.exit_code == 1
    assert "Spalte openparldata_id fehlt" in result.output
    assert "affair_id, title" in result.output


def test_baseline_keywords_are_the_labels_of_a_topic():
    tag = load_registry(REGISTRY).get("aps:6.1.9")
    terms = keywords(tag)
    assert terms.de == [
        "Digitalisierung",
        "E-Government",
        "Digitale Transformation",
        "Digitalisirung",
    ]
    assert (terms.fr, terms.it) == (["Numérisation"], ["Digitalizzazione"])
