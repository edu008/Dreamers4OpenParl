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
BODIES = [
    (1, "CHE", "country", {}),
    (2, "GE", "canton", {"canton_key": "GE"}),
    (3, "261", "city", {"canton_key": "ZH"}),  # Stadt Zürich: Region ist der Kanton
]
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
# Geschäft, Typ, Rolle, Rolle der Quelle, Partei, Position
CONTRIBUTORS = [
    # 200: Vor dem Urheber stehen die Berichterstattung, die nicht eingereicht hat,
    # Mitunterzeichnende und eine Kommission. Partei ist die des Urhebers.
    (200, "person", "author", "correspondent", "Schweizerische Volkspartei", 1),
    (200, "person", "cosign", "cosign", "FDP.Die Liberalen", 2),
    (200, "group", "author", "author", None, 3),
    (200, "person", "author", "author", "Sozialdemokratische Partei", 7),
    # 201: zwei Erstgenannte aus verschiedenen Parteien, die dritte Person zählt nicht
    (201, "person", "author", None, "Die Mitte", 1),
    (201, "person", "author", None, "Sozialdemokratische Partei", 1),
    (201, "person", "author", None, "Grünliberale Partei", 2),
    # 202: Eine Kommission ist keine Person; die erstgenannte Person hat keine Partei.
    (202, "group", "author", None, None, 1),
    (202, "person", "author", None, None, 2),
    (202, "person", "author", None, "Die Grünen", 3),
]
KEYWORDS = {"de": ["Digitalisierung", "E-Government"], "fr": ["numérisation"]}
RUNS = [
    (1, "full", "classify:aps", SINGLE, {}),
    (2, "full", "classify:aps", TWO_STAGE, {}),
    (3, "adhoc", DIGITAL_TASK, "p", {"keywords": KEYWORDS, "bodies": None, "since": None}),
    # aus angenommenen Vorschlägen, ohne Stichwortsuche (classify.proposals)
    (4, "adhoc", "classify:adhoc:ki-verwaltung", "p", {"proposal_id": 7, "by": "Mia"}),
    (5, "adhoc", DIGITAL_TASK, "p", {"proposal_id": 8, "by": "Mia"}),
]
# Geschäft, Aufgabe, Lauf, Stufe des letzten Durchlaufs
DONE = [
    *((affair_id, "classify:aps", 1, "70b") for affair_id in (200, 201, 202)),
    *((affair_id, "classify:aps", 2, "8b") for affair_id in (200, 201)),
    *((affair_id, DIGITAL_TASK, 3, "8b") for affair_id in (200, 201, 250)),
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
    (202, DIGITAL, 1, "review", "human", "human", None, "active", "confirmed"),  # von Hand
]
INSERT_LABEL = """
INSERT INTO affair_tags (affair_id, tag_id, scheme, confidence, task, stage, model_version,
                         prompt_version, registry_version, input_hash, run_id, status,
                         review_status, reviewed_by, reviewed_at)
VALUES (%s, %s, split_part(%s, ':', 1), %s, %s, %s, 'm', %s, 'v', 'h', %s, %s, %s,
        CASE WHEN %s::text IS NOT NULL THEN 'Mia' END,
        CASE WHEN %s::text IS NOT NULL THEN clock_timestamp() END)
"""


def add_affairs(conn, affairs):
    for affair_id, body_key, language, begin, text in affairs:
        conn.execute(
            "INSERT INTO affairs (id, body_key, begin_date, raw) VALUES (%s, %s, %s, '{}')",
            (affair_id, body_key, begin),
        )
        conn.execute(
            "INSERT INTO affair_inputs (affair_id, text, language, source, input_hash)"
            " VALUES (%s, %s, %s, 'texts', 'h')",
            (affair_id, text, language),
        )
    conn.execute(INDEX, ([affair[0] for affair in affairs],))


def add_run(conn, run_id, kind, task, version, params):
    conn.execute(
        "INSERT INTO classification_runs (id, kind, task, params, registry_version, scheme_hash,"
        " prompt_version) VALUES (%s, %s, %s, %s, 'v', 's', %s)",
        (run_id, kind, task, Jsonb(params), version),
    )


def add_done(conn, affair_id, task, run_id, stage):
    """Wie classify.queue: Das done-Ereignis trägt die Stufe des letzten Durchlaufs als Grund."""
    conn.execute(
        "INSERT INTO job_events (affair_id, task, from_status, to_status, reason, run_id)"
        " VALUES (%s, %s, 'pending', 'done', %s, %s)",
        (affair_id, task, stage, run_id),
    )


def add_label(conn, affair_id, tag_id, confidence, task, stage, version, run_id, status, review):
    values = (affair_id, tag_id, tag_id, confidence, task, stage, version, run_id, status)
    conn.execute(INSERT_LABEL, (*values, review, review, review))


def report(conn, settings, gold_dir=GOLD):
    registry = load_registry(settings.registry_path)
    return build(conn, registry, settings, gold_dir, read_gold_dir(gold_dir))


@pytest.fixture
def settings(conn, repo_root, api_settings):
    migrate(conn, repo_root / "migrations")
    path = api_settings.registry_path
    sync_registry(conn, load_registry(path), file_hash(path))
    return api_settings


@pytest.fixture
def data(conn, settings):
    for body_id, body_key, level, raw in BODIES:
        conn.execute(
            "INSERT INTO bodies (id, body_key, level, raw) VALUES (%s, %s, %s, %s)",
            (body_id, body_key, level, Jsonb(raw)),
        )
    add_affairs(conn, AFFAIRS)
    for contributor_id, contributor in enumerate(CONTRIBUTORS):
        conn.execute(
            "INSERT INTO affair_contributors (id, affair_id, type, role, role_external_id, party,"
            " position) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (contributor_id, *contributor),
        )
    for run in RUNS:
        add_run(conn, *run)
    for done in DONE:  # vor den Entscheiden: Die Läufe kamen vor dem Review
        add_done(conn, *done)
    for affair_id in (200, 201, 202):
        conn.execute(
            "INSERT INTO classification_jobs (affair_id, task, status, run_id)"
            " VALUES (%s, 'classify:aps', 'done', 1)",
            (affair_id,),
        )
    for label in LABELS:
        add_label(conn, *label)


def test_report_shows_every_table_with_counts(conn, settings, data):
    text = report(conn, settings)
    expected = [
        "- Aktive Labels des Modells: 5, zu Geschäften: 4.",
        "Entscheide von Menschen: 7, zu Geschäften: 3. Bestätigt 3, verworfen 1, ersetzt 1,"
        " von Hand gesetzt 2. In der Stichprobe (jedes 50. Geschäft): 2.",
        f"Gold-Verzeichnis {GOLD}: politmonitor_digitalisierung.csv mit 4 IDs,"
        " dvs_digitalisierung.csv mit 4 IDs.",
        "Von Hand gesetzt: 1 der 3 Themen, die dazugehören.",
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
        # Kantone: Bundesgeschäfte als Bund, die Stadt Zürich unter ihrem Kanton
        "### Je Kanton (Thema-Stufe)",
        "| Bund | 1 | 1/2 (50 %) | 1/1 (100 %) | 1/1 (100 %) | 1/1 (100 %) |",
        "| GE | 1 | 0/1 (0 %) | 1/1 (100 %) | 0/1 (0 %) | 1/1 (100 %) |",
        "| ZH | 1 | 1/1 (100 %) | 1/1 (100 %) | 1/1 (100 %) | 1/1 (100 %) |",
        # Parteien: 200 nach dem Urheber, 201 mit zwei Erstgenannten, 202 ohne Partei
        "### Je Partei (Thema-Stufe)",
        "| Sozialdemokratische Partei | 1 | 1/2 (50 %) | 1/1 (100 %) | 1/1 (100 %) | 1/1 (100 %) |",
        "| mehrere Parteien | 1 | 0/1 (0 %) | 1/1 (100 %) | 0/1 (0 %) | 1/1 (100 %) |",
        "| ohne Partei | 1 | 1/1 (100 %) | 1/1 (100 %) | 1/1 (100 %) | 1/1 (100 %) |",
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
        # Ad-hoc: der Lauf mit Stichwörtern, nicht der spätere aus einem Vorschlag
        "### adhoc:digitalisierung-breit (Lauf 3)",
        "- Stichwortsuche: Kandidaten 2, davon mit Label 2.",
        "Geschäfte 1, davon mit Label 1. Hochgerechnet (× 50) Kandidaten-Recall 2/52 (4 %)",
        # 202 von Hand gesetzt, ohne Stichworttreffer
        "| Review-Entscheide | 2 | 0 | 1 | 1/2 (50 %) | 1/1 (100 %) | 1/2 (50 %) |",
        # PolitMonitor: 999 fehlt in der Datenbank, 201 ist kantonal, 203 von 2017
        "in der Datei 4, in der Datenbank 3, davon CHE ab 2018 und von classify:aps bearbeitet 1.",
        "| Recall Volllauf, CHE ab 2018 | 1/1 (100 %) | ≥ 85 % |",
        "| Recall Kandidatenpfad gesamt (Lauf 3) | 2/3 (67 %) | ≥ 80 % |",
        "| Kandidaten-Recall der Stichwortsuche | 2/3 (67 %) | ≥ 95 % |",
        "| Recall des Klassifikators in den Kandidaten | 2/2 (100 %) | ≥ 85 % |",
        # DVS: das von Hand gesetzte Label an 202 zählt nicht
        "| DVS-Abgleich: Geschäfte mit aktivem Modell-Label | 2/4 (50 %) | ≥ 29/30 |",
        "- DVS-Liste: ohne aktives Modell-Label 202, nicht in der Datenbank 998.",
    ]
    missing = [line for line in expected if line not in text]
    assert not missing, text
    assert "adhoc:ki-verwaltung" not in text  # Vorschlagslauf ohne Stichwortsuche
    # Berichterstattung, Mitunterzeichnende, später Genannte
    for party in ("Volkspartei", "FDP", "Die Mitte", "Grünliberale", "Die Grünen"):
        assert party not in text


def test_only_the_final_pass_of_an_escalated_job_counts(conn, settings):
    add_affairs(
        conn,
        [
            (300, "CHE", "de", "2024-03-01", "Digitalisierung im Bund\nDer Bund digitalisiert."),
            (350, "CHE", "de", "2024-03-01", "Steuern\nDie Steuern sinken."),  # Stichprobe
        ],
    )
    add_run(conn, 6, "full", "classify:aps", TWO_STAGE, {})
    params = {"keywords": {"de": ["Digitalisierung"]}, "bodies": None, "since": None}
    add_run(conn, 7, "adhoc", DIGITAL_TASK, "p", params)
    for affair_id, task, run_id in ((300, "classify:aps", 6), (300, DIGITAL_TASK, 7)):
        add_done(conn, affair_id, task, run_id, "70b")
    add_done(conn, 350, DIGITAL_TASK, 7, "70b")
    # 8B fand aps:2.4.1 und auf der Stichprobe das Ad-hoc-Thema, 70B nicht; die Queue speichert
    # den 8B-Durchlauf als superseded unter demselben Lauf und derselben Prompt-Version.
    for label in [
        (300, "aps:2.4.1", 0.5, "classify:aps", "8b", TWO_STAGE, 6, "superseded", None),
        (300, "aps:6.1.9", 0.9, "classify:aps", "70b", TWO_STAGE, 6, "active", "confirmed"),
        (300, "aps:2.4.1", 1, "review", "human", "human", None, "active", "confirmed"),
        (300, DIGITAL, 0.5, DIGITAL_TASK, "8b", "p", 7, "superseded", None),
        (300, DIGITAL, 0.9, DIGITAL_TASK, "70b", "p", 7, "active", None),
        (350, DIGITAL, 0.5, DIGITAL_TASK, "8b", "p", 7, "superseded", None),
    ]:
        add_label(conn, *label)
    text = report(conn, settings)
    row = f"| zweistufig | `{TWO_STAGE}` | 1 | 1 | 1/1 (100 %) | 1/2 (50 %) | 1/1 (100 %)"
    row += " | 1/2 (50 %) |"
    assert row in text, text
    sample = "Geschäfte 1, davon mit Label 0. Hochgerechnet (× 50) Kandidaten-Recall 1/1 (100 %)"
    assert sample in text, text


def test_a_variant_that_ran_after_a_confirmation_is_left_out(conn, settings):
    add_affairs(conn, [(400, "CHE", "de", "2024-03-01", "Digitalisierung\nDer Bund.")])
    add_run(conn, 8, "full", "classify:aps", TWO_STAGE, {})
    add_run(conn, 9, "full", "classify:aps", SINGLE, {})
    add_done(conn, 400, "classify:aps", 8, "8b")
    add_label(
        conn, 400, "aps:6.1.9", 0.8, "classify:aps", "8b", TWO_STAGE, 8, "active", "confirmed"
    )
    add_label(
        conn, 400, "aps:2.4.1", 0.7, "classify:aps", "8b", TWO_STAGE, 8, "rejected", "rejected"
    )
    # Der einstufige Lauf danach liefert beide Themen wieder. Die Queue übernimmt das bestätigte
    # nicht und speichert das verworfene als rejected (classify.queue.HUMAN).
    add_done(conn, 400, "classify:aps", 9, "70b")
    add_label(conn, 400, "aps:2.4.1", 0.9, "classify:aps", "70b", SINGLE, 9, "rejected", None)
    text = report(conn, settings)
    for line in [
        "Jede Variante auf ihren eigenen Geschäften; gemeinsame gibt es keine.",
        f"| einstufig | `{SINGLE}` | 0 | 0 | – | – | – | – |",
        f"| zweistufig | `{TWO_STAGE}` | 1 | 2 | 1/2 (50 %) | 1/1 (100 %) | 1/2 (50 %)"
        " | 1/1 (100 %) |",
    ]:
        assert line in text, text


def test_an_empty_database_gives_counts_without_invented_rates(conn, settings, tmp_path):
    text = report(conn, settings, tmp_path)
    for line in [
        "- Aktive Labels des Modells: 0, zu Geschäften: 0.",
        "Entscheide von Menschen: 0, zu Geschäften: 0.",
        "Achtung: weniger als 100 Geschäfte.",
        "| Thema | 0 | – | – | – | – |",
        "| einstufig | kein Lauf auf Geschäften mit Entscheid | 0 | 0 | – | – | – | – |",
        "| zweistufig | kein Lauf auf Geschäften mit Entscheid | 0 | 0 | – | – | – | – |",
        "| ab 0.9 | – | – | – |",
        "Noch kein Ad-hoc-Lauf mit Stichwortsuche.",
        f"{tmp_path / 'politmonitor_digitalisierung.csv'} fehlt: kein Recall gegen PolitMonitor.",
        "| DVS-Abgleich: Geschäfte mit aktivem Modell-Label | – | ≥ 29/30 |",
    ]:
        assert line in text, text
    assert "%)" not in text


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
