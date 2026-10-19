"""Evaluationsbericht gegen ein echtes PostgreSQL (PRD F16, 13), mit fiktiven Daten."""

from pathlib import Path

import pytest
from psycopg.types.json import Jsonb
from typer.testing import CliRunner

from parltopics.cli import app
from parltopics.db import migrate
from parltopics.evaluation.report import build, read_gold_dir
from parltopics.inputs import SEARCH as INDEX
from parltopics.registry import file_hash, load_registry
from parltopics.registry.sync import sync_registry

pytestmark = pytest.mark.integration

GOLD = Path(__file__).resolve().parents[1] / "fixtures" / "gold"
SINGLE = "classify_single_v1+aaaa"
TWO_STAGE = "classify_chapters_v2+bbbb classify_topics_v2+cccc"
DIGITAL = "adhoc:digitalisierung-breit"
DIGITAL_TASK = "classify:adhoc:digitalisierung-breit"
BODIES = [(1, "CHE", "country"), (2, "GE", "canton"), (3, "261", "city")]
AFFAIRS = [
    (
        200,
        "CHE",
        "de",
        "2024-03-01",
        "Digitalisierung der Verwaltung\nDer Bund fördert E-Government.",
    ),
    (201, "GE", "fr", "2024-03-01", "Numérisation des services\nLe canton numérise ses guichets."),
    (202, "261", "de", "2024-03-01", "Arbeitsmarkt in der Stadt\nDie Stadt fördert Stellen."),
    (203, "CHE", "de", "2017-05-01", "Breitband auf dem Land\nGlasfaser für alle."),
    (250, "CHE", "de", "2024-03-01", "Steuern\nDie Steuern sinken."),  # Stichprobe: 250 % 50
]
# Geschäft, Tag, Konfidenz, Aufgabe, Stufe, Prompt-Version, Lauf, Status, Entscheid
LABELS = [
    (200, "aps:6.1.9", 0.92, "classify:aps", "70b", SINGLE, 1, "active", "confirmed"),
    (200, "aps:2.4.1", 0.65, "classify:aps", "70b", SINGLE, 1, "rejected", "rejected"),
    (201, "aps:2.4.1", 0.75, "classify:aps", "70b", SINGLE, 1, "rejected", "changed"),
    (201, "aps:6.1.9", 1, "review", "human", "human", None, "active", "confirmed"),
    (202, "aps:2.4.1", 0.85, "classify:aps", "70b", SINGLE, 1, "active", "confirmed"),
    (200, "aps:6.1.9", 0.8, "classify:aps", "8b", TWO_STAGE, 2, "superseded", None),
    (201, "aps:6.1.9", 0.7, "classify:aps", "8b", TWO_STAGE, 2, "superseded", None),
    (200, DIGITAL, 0.9, "classify:aps", "70b", SINGLE, 1, "active", None),
    (200, DIGITAL, 0.8, DIGITAL_TASK, "8b", "p", 3, "superseded", None),
    (201, DIGITAL, 0.7, DIGITAL_TASK, "8b", "p", 3, "active", "confirmed"),
    (250, DIGITAL, 0.6, DIGITAL_TASK, "8b", "p", 3, "active", None),
]
KEYWORDS = {"de": ["Digitalisierung", "E-Government"], "fr": ["numérisation"]}
RUNS = [
    (1, "full", "classify:aps", SINGLE, {}),
    (2, "full", "classify:aps", TWO_STAGE, {}),
    (3, "adhoc", DIGITAL_TASK, "p", {"keywords": KEYWORDS, "bodies": None, "since": None}),
]
INSERT_LABEL = """
INSERT INTO affair_tags (affair_id, tag_id, scheme, confidence, task, stage, model_version,
                         prompt_version, registry_version, input_hash, run_id, status,
                         review_status, reviewed_by, reviewed_at)
VALUES (%(affair_id)s, %(tag_id)s, split_part(%(tag_id)s, ':', 1), %(confidence)s, %(task)s,
        %(stage)s, 'm', %(version)s, 'v', 'h', %(run_id)s, %(status)s, %(review)s,
        CASE WHEN %(review)s::text IS NOT NULL THEN 'Mia' END,
        CASE WHEN %(review)s::text IS NOT NULL THEN clock_timestamp() END)
"""


@pytest.fixture
def settings(conn, repo_root, api_settings):
    migrate(conn, repo_root / "migrations")
    sync_registry(
        conn, load_registry(api_settings.registry_path), file_hash(api_settings.registry_path)
    )
    return api_settings


@pytest.fixture
def data(conn, settings):
    for body_id, body_key, level in BODIES:
        conn.execute(
            "INSERT INTO bodies (id, body_key, level, raw) VALUES (%s, %s, %s, '{}')",
            (body_id, body_key, level),
        )
    for affair_id, body_key, language, begin, text in AFFAIRS:
        conn.execute(
            "INSERT INTO affairs (id, body_key, begin_date, raw) VALUES (%s, %s, %s, '{}')",
            (affair_id, body_key, begin),
        )
        conn.execute(
            "INSERT INTO affair_inputs (affair_id, text, language, source, input_hash)"
            " VALUES (%s, %s, %s, 'texts', 'h')",
            (affair_id, text, language),
        )
    conn.execute(INDEX, ([affair[0] for affair in AFFAIRS],))
    for run_id, kind, task, version, params in RUNS:
        conn.execute(
            "INSERT INTO classification_runs (id, kind, task, params, registry_version,"
            " scheme_hash, prompt_version) VALUES (%s, %s, %s, %s, 'v', 's', %s)",
            (run_id, kind, task, Jsonb(params), version),
        )
    for run_id, affair_ids in ((1, [200, 201, 202]), (2, [200, 201])):
        for affair_id in affair_ids:
            conn.execute(
                "INSERT INTO job_events (affair_id, task, from_status, to_status, run_id)"
                " VALUES (%s, 'classify:aps', 'pending', 'done', %s)",
                (affair_id, run_id),
            )
    for affair_id in (200, 201, 202):
        conn.execute(
            "INSERT INTO classification_jobs (affair_id, task, status, run_id)"
            " VALUES (%s, 'classify:aps', 'done', 1)",
            (affair_id,),
        )
    columns = ("affair_id", "tag_id", "confidence", "task", "stage", "version", "run_id")
    for label in LABELS:
        conn.execute(INSERT_LABEL, dict(zip((*columns, "status", "review"), label, strict=True)))


def test_report_shows_every_table_with_counts(conn, settings, data):
    report = build(conn, load_registry(settings.registry_path), settings, GOLD, read_gold_dir(GOLD))
    expected = [
        "- Aktive Labels des Modells: 5, zu Geschäften: 4.",
        "Entscheide von Menschen: 6, zu Geschäften: 3. Bestätigt 3, verworfen 1, ersetzt 1,"
        " von Hand gesetzt 1. In der Stichprobe (jedes 50. Geschäft): 2.",
        f"Gold-Verzeichnis {GOLD}: politmonitor_digitalisierung.csv mit 4 IDs,"
        " dvs_digitalisierung.csv mit 4 IDs.",
        # Hierarchiestufen: Modell gegen Stichwörter
        "| Thema | 3 | 2/4 (50 %) | 3/3 (100 %) | 2/3 (67 %) | 3/3 (100 %) |",
        "| Bereich | 3 | 2/4 (50 %) | 3/3 (100 %) | 2/3 (67 %) | 3/3 (100 %) |",
        # Sprachen und Ebenen
        "| de | 2 | 2/3 (67 %) | 2/2 (100 %) | 2/2 (100 %) | 2/2 (100 %) |",
        "| fr | 1 | 0/1 (0 %) | 1/1 (100 %) | 0/1 (0 %) | 1/1 (100 %) |",
        "| it | 0 | – | – | – | – |",
        "| country | 1 | 1/2 (50 %) | 1/1 (100 %) | 1/1 (100 %) | 1/1 (100 %) |",
        "| city | 1 | 1/1 (100 %) | 1/1 (100 %) | 1/1 (100 %) | 1/1 (100 %) |",
        "| municipality | 0 | – | – | – | – |",
        # Prompt-Varianten auf den gemeinsamen Geschäften 200 und 201
        "Verglichen auf den 2 Geschäften, die alle Varianten bearbeitet haben.",
        f"| einstufig | `{SINGLE}` | 2 | 3 | 1/3 (33 %) | 1/2 (50 %) | 1/3 (33 %) | 1/2 (50 %) |",
        f"| zweistufig | `{TWO_STAGE}` | 2 | 2 | 2/2 (100 %) | 2/2 (100 %) | 2/2 (100 %)"
        " | 2/2 (100 %) |",
        # Konfidenzbänder
        "Alle geprüften Modell-Labels (APS und Ad-hoc), 5 Entscheide.",
        "| 0.0–0.6 | – | – | 3/5 (60 %) |",
        "| 0.7–0.8 | 1/2 (50 %) | – | 3/4 (75 %) |",
        "| ab 0.9 | 1/1 (100 %) | 1/1 (100 %) | 1/1 (100 %) |",
        # Ad-hoc: Stichprobe 250 hat ein Label ohne Stichworttreffer
        "### adhoc:digitalisierung-breit (Lauf 3)",
        "- Stichwortsuche: Kandidaten 2, davon mit Label 2.",
        "Geschäfte 1, davon mit Label 1. Hochgerechnet (× 50) Kandidaten-Recall 2/52 (4 %)",
        "| Review-Entscheide | 1 | 1/1 (100 %) | 1/1 (100 %) | 1/1 (100 %) |",
        # PolitMonitor: 999 fehlt in der Datenbank, 201 ist kantonal, 203 von 2017
        "in der Datei 4, in der Datenbank 3, davon CHE ab 2018 und von classify:aps bearbeitet 1.",
        "| Recall Volllauf, CHE ab 2018 | 1/1 (100 %) | ≥ 85 % |",
        "| Recall Kandidatenpfad gesamt (Lauf 3) | 2/3 (67 %) | ≥ 80 % |",
        "| Kandidaten-Recall der Stichwortsuche | 2/3 (67 %) | ≥ 95 % |",
        "| Recall des Klassifikators in den Kandidaten | 2/2 (100 %) | ≥ 85 % |",
        "| DVS-Abgleich: Geschäfte mit aktivem Label | 2/4 (50 %) | ≥ 29/30 |",
        "- DVS-Liste: ohne aktives Label 202, nicht in der Datenbank 998.",
    ]
    missing = [line for line in expected if line not in report]
    assert not missing, report


def test_an_empty_database_gives_counts_without_invented_rates(conn, settings, tmp_path):
    report = build(
        conn, load_registry(settings.registry_path), settings, tmp_path, read_gold_dir(tmp_path)
    )
    for line in [
        "- Aktive Labels des Modells: 0, zu Geschäften: 0.",
        "Entscheide von Menschen: 0, zu Geschäften: 0.",
        "Achtung: weniger als 100 Geschäfte.",
        "| Thema | 0 | – | – | – | – |",
        "| einstufig | kein Lauf auf Geschäften mit Entscheid | 0 | 0 | – | – | – | – |",
        "| zweistufig | kein Lauf auf Geschäften mit Entscheid | 0 | 0 | – | – | – | – |",
        "| ab 0.9 | – | – | – |",
        "Noch kein Ad-hoc-Lauf.",
        f"{tmp_path / 'politmonitor_digitalisierung.csv'} fehlt: kein Recall gegen PolitMonitor.",
        "| DVS-Abgleich: Geschäfte mit aktivem Label | – | ≥ 29/30 |",
    ]:
        assert line in report, report
    assert "%)" not in report


def test_eval_writes_the_report_without_writing_to_the_database(
    conn, settings, data, monkeypatch, tmp_path
):
    monkeypatch.setattr("parltopics.cli.get_settings", lambda: settings)
    count = "SELECT (SELECT count(*) FROM affair_tags) + (SELECT count(*) FROM classification_runs)"
    before = conn.execute(count).fetchone()
    out = tmp_path / "eval" / "report.md"
    result = CliRunner().invoke(app, ["eval", "--gold", str(GOLD), "--out", str(out)])
    assert result.exit_code == 0, result.output
    assert f"Bericht geschrieben: {out}" in result.output
    text = out.read_text(encoding="utf-8")
    assert text.startswith("# Evaluationsbericht ParlTopics")
    assert "| Recall Volllauf, CHE ab 2018 | 1/1 (100 %) | ≥ 85 % |" in text
    assert conn.execute(count).fetchone() == before
