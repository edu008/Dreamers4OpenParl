"""Evaluationsbericht als Markdown (PRD F16, 13).

Präzision und Recall gegen das Gold-Set je Hierarchiestufe, Sprache und Ebene, die Baseline
Stichwortsuche, Präzision je Konfidenzband, die Prompt-Varianten und die Ad-hoc-Themen. Das
Gold-Set sind die Entscheide der Menschen in affair_tags (api.queries.GOLD). Im Gold-Verzeichnis
liegen, falls vorhanden, zwei Dateien des Hack-Datensatzes: PolitMonitor (nur Positive zu
Digitalisierung) und die DVS-Liste. Der Bericht liest nur und schreibt nichts in die Datenbank.
"""

import csv
from collections import Counter, defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import psycopg

from parltopics.api import queries
from parltopics.classify.adhoc import SCOPE, Keywords, find_affairs, websearch
from parltopics.classify.queue import TASK_APS, adhoc_task, task_tag
from parltopics.classify.worker import SAMPLE_EVERY
from parltopics.config import Settings
from parltopics.evaluation.metrics import LEVELS, Gold, Labels, Share, bands, path_recall, score
from parltopics.registry import Registry, Tag

DIGITAL = "adhoc:digitalisierung-breit"  # Definition entlang PolitMonitor (PRD 12)
POLITMONITOR = "politmonitor_digitalisierung.csv"
DVS = "dvs_digitalisierung.csv"
ID_COLUMN = "openparldata_id"  # Annahme: wie in che_affairs_keywords.csv (evaluation.curia)
FULL_RUN_SINCE = date(2018, 1, 1)  # Recall Volllauf: PolitMonitor-Positive CHE ab 2018 (PRD 13)
FEW = 100  # Umfang des Gold-Sets nach PRD 15; darunter schwanken die Quoten stark
LANGUAGES = ("de", "fr", "it", "rm")
BODY_LEVELS = ("country", "canton", "city", "municipality")
METRICS = [
    "Geschäfte",
    "Präzision Modell",
    "Präzision Stichwörter",
    "Recall Modell",
    "Recall Stichwörter",
]

# Je Geschäft die Prompt-Versionen der Läufe von classify:aps, die es fertig bearbeitet haben;
# so zählen auch Geschäfte, bei denen eine Variante kein Thema fand.
CLASSIFIED = f"""
SELECT DISTINCT e.affair_id, r.prompt_version
FROM job_events e JOIN classification_runs r ON r.id = e.run_id
WHERE e.task = '{TASK_APS}' AND e.to_status = 'done' AND e.affair_id = ANY(%s::bigint[])
"""
APS_LABELS = f"""
SELECT affair_id, tag_id, prompt_version, status FROM affair_tags
WHERE task = '{TASK_APS}' AND stage <> 'human' AND scheme = 'aps'
  AND affair_id = ANY(%s::bigint[])
"""
FACTS = """
SELECT a.id, coalesce(i.language, 'unbekannt'), coalesce(b.level, 'unbekannt')
FROM affairs a
LEFT JOIN affair_inputs i ON i.affair_id = a.id
LEFT JOIN bodies b ON b.body_key = a.body_key
WHERE a.id = ANY(%s::bigint[])
"""
# Baseline: dieselbe Volltextsuche wie die Kandidatensuche der Ad-hoc-Themen, je APS-Thema mit
# seinen Bezeichnungen als Stichwörtern.
KEYWORD_HITS = """
WITH k AS MATERIALIZED (
    SELECT tag_id, websearch_to_tsquery('german', de) || websearch_to_tsquery('french', fr)
                   || websearch_to_tsquery('italian', it) AS query
    FROM unnest(%(tags)s::text[], %(de)s::text[], %(fr)s::text[], %(it)s::text[])
         AS t (tag_id, de, fr, it)
)
SELECT d.affair_id, k.tag_id FROM search_documents d JOIN k ON d.document @@ k.query
WHERE d.affair_id = ANY(%(ids)s::bigint[])
"""
ADHOC_RUNS = """
SELECT DISTINCT ON (task) id, task, params FROM classification_runs
WHERE kind = 'adhoc' ORDER BY task, id DESC
"""
# shortcut: zählt jedes Label des Kandidatenpfads, auch eines, das ein späterer Lauf nach einer
# Textänderung ersetzt hat; genauer über job_events, falls sich Ad-hoc-Läufe oft wiederholen.
ADHOC_LABELLED = "SELECT DISTINCT affair_id FROM affair_tags WHERE task = %s AND stage <> 'human'"
IN_SCOPE = f"""
SELECT a.id FROM affairs a JOIN affair_inputs i ON i.affair_id = a.id
WHERE a.id = ANY(%(ids)s::bigint[]) {SCOPE}
"""
KNOWN = "SELECT id FROM affairs WHERE id = ANY(%s::bigint[])"
FULL_RUN = f"""
SELECT a.id FROM affairs a
JOIN classification_jobs j ON j.affair_id = a.id AND j.task = '{TASK_APS}' AND j.status = 'done'
WHERE a.id = ANY(%s::bigint[]) AND a.body_key = 'CHE' AND a.begin_date >= %s
"""
FULL_RUN_LABELLED = f"""
SELECT DISTINCT affair_id FROM affair_tags
WHERE tag_id = %s AND task = '{TASK_APS}' AND stage <> 'human' AND status IN ('active', 'rejected')
"""
ACTIVE = "SELECT DISTINCT affair_id FROM affair_tags WHERE tag_id = %s AND status = 'active'"
MODEL_LABELS = """
SELECT count(*), count(DISTINCT affair_id) FROM affair_tags
WHERE status = 'active' AND stage <> 'human'
"""


class GoldFileError(ValueError):
    """Eine Datei im Gold-Verzeichnis passt nicht zur erwarteten Form."""


def load_ids(path: Path) -> set[int]:
    """OpenParlData-IDs aus einer CSV-Datei des Hack-Datensatzes (Spalte openparldata_id)."""
    with path.open(encoding="utf-8-sig", newline="") as rows:
        reader = csv.DictReader(rows)
        columns = reader.fieldnames or []
        if ID_COLUMN not in columns:
            found = ", ".join(columns) or "keine"
            raise GoldFileError(f"{path}: Spalte {ID_COLUMN} fehlt. Gefundene Spalten: {found}")
        ids = set()
        for row in reader:
            value = (row[ID_COLUMN] or "").strip()
            if not value:
                continue
            if not value.isdecimal():
                raise GoldFileError(
                    f"{path}, Zeile {reader.line_num}: {ID_COLUMN} {value!r} ist keine ID"
                )
            ids.add(int(value))
    return ids


def read_gold_dir(gold_dir: Path) -> dict[str, set[int] | None]:
    """IDs je Datei im Gold-Verzeichnis; None, wenn die Datei fehlt."""
    return {
        name: load_ids(gold_dir / name) if (gold_dir / name).is_file() else None
        for name in (POLITMONITOR, DVS)
    }


def keywords(tag: Tag) -> Keywords:
    """Stichwörter der Baseline: Bezeichnung und alternative Bezeichnungen je Sprache."""
    labels, alt = tag.pref_label, tag.alt_labels
    return Keywords(
        de=[labels.de, *alt.de, *tag.hidden_labels],
        fr=[*filter(None, [labels.fr]), *alt.fr],
        it=[*filter(None, [labels.it]), *alt.it],
    )


@dataclass(frozen=True)
class AdhocRun:
    """Der letzte Ad-hoc-Lauf eines Tags: Kandidaten und Stichprobe, wie find_affairs sie heute
    liefert, und die Geschäfte mit einem Label aus dem Kandidatenpfad."""

    run_id: int
    tag_id: str
    params: dict
    candidates: set[int]
    sample: set[int]
    labelled: set[int]

    def in_scope(self, conn: psycopg.Connection, ids: set[int]) -> set[int]:
        """Die Geschäfte aus ids im Bereich des Laufs (Parlamente, Datum) mit Text."""
        scope = {"bodies": self.params.get("bodies"), "since": _since(self.params)}
        return {row[0] for row in conn.execute(IN_SCOPE, {"ids": list(ids), **scope})}


def _since(params: dict) -> date | None:
    """since aus den Parametern eines Laufs (ISO-Datum oder null, classify.queue.open_jobs)."""
    return date.fromisoformat(params["since"]) if params.get("since") else None


def adhoc_runs(conn: psycopg.Connection) -> list[AdhocRun]:
    runs = []
    for run_id, task, params in conn.execute(ADHOC_RUNS).fetchall():
        candidates, sample = find_affairs(
            conn,
            Keywords.model_validate(params.get("keywords") or {}),
            bodies=params.get("bodies"),
            since=_since(params),
        )
        labelled = {row[0] for row in conn.execute(ADHOC_LABELLED, (task,))}
        runs.append(
            AdhocRun(run_id, task_tag(task), params, set(candidates), set(sample), labelled)
        )
    return runs


def build(
    conn: psycopg.Connection,
    registry: Registry,
    settings: Settings,
    gold_dir: Path,
    files: dict[str, set[int] | None],
) -> str:
    """Der ganze Bericht; files aus read_gold_dir."""
    rows = queries.gold(conn)
    gold: Gold = {}
    for row in rows:  # ältester Entscheid zuerst: der jüngste je Geschäft und Thema gilt
        gold.setdefault(row["affair_id"], {})[row["tag_id"]] = row["belongs"]
    runs = adhoc_runs(conn)
    lines = [
        "# Evaluationsbericht ParlTopics",
        "",
        f"Erzeugt {datetime.now():%Y-%m-%d %H:%M} mit Registry {registry.registry_version},"
        f" CLASSIFY_MODE {settings.classify_mode}, Schwelle {settings.confidence_threshold}."
        " Werte als Treffer/Nenner (Anteil); „–“ heisst: kein Nenner.",
        "",
        *_summary(conn, rows, gold_dir, files),
        *_aps(conn, registry, gold),
        *_calibration(rows, settings.confidence_threshold),
        *_adhoc(conn, runs, gold),
        *_digital(conn, runs, gold_dir, files),
    ]
    return "\n".join(lines)


def _table(header: list[str], rows: list[list[object]]) -> list[str]:
    return [
        "| " + " | ".join(header) + " |",
        "|" + "---|" * len(header),
        *("| " + " | ".join(str(cell) for cell in row) + " |" for row in rows),
        "",
    ]


def _summary(
    conn: psycopg.Connection, rows: list[dict], gold_dir: Path, files: dict[str, set[int] | None]
) -> list[str]:
    decisions = Counter(row["decision"] for row in rows)
    affairs = {row["affair_id"] for row in rows}
    labels, labelled = conn.execute(MODEL_LABELS).fetchone()
    read = (
        f"{name} fehlt" if ids is None else f"{name} mit {len(ids)} IDs"
        for name, ids in files.items()
    )
    return [
        "## Gold-Set",
        "",
        f"- Aktive Labels des Modells: {labels}, zu Geschäften: {labelled}.",
        f"- Entscheide von Menschen: {len(rows)}, zu Geschäften: {len(affairs)}. Bestätigt"
        f" {decisions['confirmed']}, verworfen {decisions['rejected']}, ersetzt"
        f" {decisions['changed']}, von Hand gesetzt {decisions['added']}. In der Stichprobe"
        f" (jedes {SAMPLE_EVERY}. Geschäft): {sum(row['sample'] for row in rows)}.",
        "- Die Review-Warteschlange zeigt vor allem unsichere Labels; unverzerrt ist nur die"
        " Stichprobe. Gezählt werden nur entschiedene Paare aus Geschäft und Thema.",
        f"- Gold-Verzeichnis {gold_dir}: {', '.join(read)}.",
        "",
    ]


def _compare(name: str, gold: Gold, model: Labels, keyword: Labels, level: str) -> list[object]:
    """Eine Zeile Modell gegen Stichwortsuche."""
    ours, theirs = score(model, gold, level), score(keyword, gold, level)
    return [name, len(gold), ours.precision, theirs.precision, ours.recall, theirs.recall]


def _by(gold: Gold, key: Callable[[int], str], order: tuple[str, ...]) -> list[tuple[str, Gold]]:
    """gold je Wert von key: zuerst die Werte aus order, dann die übrigen."""
    values = [*order, *sorted({key(a) for a in gold} - set(order))]
    return [(value, {a: d for a, d in gold.items() if key(a) == value}) for value in values]


def _aps(conn: psycopg.Connection, registry: Registry, gold: Gold) -> list[str]:
    aps = {a: {t: b for t, b in d.items() if t.startswith("aps:")} for a, d in gold.items()}
    aps = {a: d for a, d in aps.items() if d}
    ids = list(aps)
    classified: dict[int, set[str]] = defaultdict(set)
    for affair_id, version in conn.execute(CLASSIFIED, (ids,)):
        classified[affair_id].add(version)
    evaluated = {a: d for a, d in aps.items() if a in classified}
    current: Labels = defaultdict(set)  # was heute gilt: aktiv oder von Menschen verworfen
    by_version: dict[str, Labels] = defaultdict(lambda: defaultdict(set))
    for affair_id, tag_id, version, status in conn.execute(APS_LABELS, (ids,)):
        by_version[version][affair_id].add(tag_id)
        if status != "superseded":
            current[affair_id].add(tag_id)
    facts = {a: (language, level) for a, language, level in conn.execute(FACTS, (ids,))}
    baseline = _keyword_labels(conn, registry, list(evaluated))

    lines = [
        "## APS gegen das Gold-Set",
        "",
        f"Ausgewertet: {len(evaluated)} Geschäfte mit Entscheid zu einem APS-Thema, die"
        " classify:aps fertig bearbeitet hat. Modell: Labels mit Status active oder rejected."
        " Stichwörter: die"
        " Volltextsuche (search_documents) mit Bezeichnung, alternativen und versteckten"
        " Bezeichnungen jedes APS-Themas in DE/FR/IT, wie die Kandidatensuche der Ad-hoc-Themen.",
        "",
    ]
    if len(evaluated) < FEW:
        lines += [
            f"Achtung: weniger als {FEW} Geschäfte. Die Quoten schwanken stark, massgebend sind"
            " die Zählungen.",
            "",
        ]
    lines += [
        "### Je Hierarchiestufe",
        "",
        "Ein falsches Thema im richtigen Kapitel zählt auf Kapitel- und Bereichsstufe als Treffer.",
        "",
        *_table(
            ["Stufe", *METRICS],
            [_compare(level.capitalize(), evaluated, current, baseline, level) for level in LEVELS],
        ),
    ]
    for title, key, order in (
        ("Sprache", lambda a: facts[a][0], LANGUAGES),
        ("Ebene", lambda a: facts[a][1], BODY_LEVELS),
    ):
        table = [_compare(n, g, current, baseline, "thema") for n, g in _by(evaluated, key, order)]
        table.append(_compare("gesamt", evaluated, current, baseline, "thema"))
        lines += [f"### Je {title} (Thema-Stufe)", "", *_table([title, *METRICS], table)]
    return lines + _variants(aps, classified, by_version)


def _keyword_labels(conn: psycopg.Connection, registry: Registry, ids: list[int]) -> Labels:
    tags = [tag for tag in registry.active("aps") if tag.aps_level == "thema"]
    terms = [keywords(tag) for tag in tags]
    params = {
        "tags": [tag.tag_id for tag in tags],
        "de": [websearch(k.de) for k in terms],
        "fr": [websearch(k.fr) for k in terms],
        "it": [websearch(k.it) for k in terms],
        "ids": ids,
    }
    labels: Labels = defaultdict(set)
    for affair_id, tag_id in conn.execute(KEYWORD_HITS, params):
        labels[affair_id].add(tag_id)
    return labels


def _variant(version: str) -> str:
    """Zweistufig trägt zwei Prompts, getrennt durch ein Leerzeichen (classify.worker)."""
    return "zweistufig" if " " in version else "einstufig"


def _variants(
    aps: Gold, classified: dict[int, set[str]], by_version: dict[str, Labels]
) -> list[str]:
    versions = sorted({v for vs in classified.values() for v in vs}, key=lambda v: (_variant(v), v))
    affairs = {v: {a for a, vs in classified.items() if v in vs} for v in versions}
    common = set.intersection(*affairs.values()) if len(versions) > 1 else set()
    if len(versions) < 2:
        basis = "Jede Variante auf den Geschäften, die sie bearbeitet hat."
    elif common:
        basis = f"Verglichen auf den {len(common)} Geschäften, die alle Varianten bearbeitet haben."
    else:
        basis = "Jede Variante auf ihren eigenen Geschäften; gemeinsame gibt es keine."
    rows = []
    for version in versions:
        gold = {a: aps[a] for a in common or affairs[version]}
        labels = by_version[version]
        thema, kapitel = score(labels, gold, "thema"), score(labels, gold, "kapitel")
        count = sum(len(labels.get(a, ())) for a in gold)
        rows.append(
            [
                *(_variant(version), f"`{version}`", len(gold), count),
                *(thema.precision, thema.recall, kapitel.precision, kapitel.recall),
            ]
        )
    for missing in sorted({"einstufig", "zweistufig"} - {_variant(v) for v in versions}):
        rows.append([missing, "kein Lauf auf Geschäften mit Entscheid", 0, 0, *[Share(0, 0)] * 4])
    header = ["Variante", "Prompt-Version", "Geschäfte", "Labels"]
    header += ["Präzision Thema", "Recall Thema", "Präzision Kapitel", "Recall Kapitel"]
    return [
        "### Prompt-Varianten (einstufig und zweistufig)",
        "",
        "Labels jeder Prompt-Version, auch später ersetzte, gegen dieselben Entscheide. " + basis,
        "",
        *_table(header, rows),
    ]


def _calibration(rows: list[dict], threshold: float) -> list[str]:
    decisions = [
        (float(row["confidence"]), row["belongs"], row["sample"])
        for row in rows
        if row["stage"] != "human"
    ]
    table = []
    for band in bands(decisions):
        name = f"{band.low:.1f}–{band.high:.1f}" if band.high is not None else f"ab {band.low:.1f}"
        table.append([name, band.labels, band.sample, band.from_low])
    return [
        "## Präzision je Konfidenzband",
        "",
        f"Alle geprüften Modell-Labels (APS und Ad-hoc), {len(decisions)} Entscheide. Ziel PRD 13:"
        f" ab der Schwelle (heute {threshold}) mindestens 80 % bestätigt.",
        "",
        *_table(["Konfidenz", "bestätigt", "nur Stichprobe", "ab Untergrenze"], table),
    ]


def _adhoc(conn: psycopg.Connection, runs: list[AdhocRun], gold: Gold) -> list[str]:
    lines = ["## Ad-hoc-Themen: Kandidaten-Recall und Klassifikator-Recall", ""]
    if not runs:
        return [*lines, "Noch kein Ad-hoc-Lauf.", ""]
    header = ["Wahrheit", "Positive im Bereich", "Kandidaten-Recall", "Klassifikator-Recall"]
    header.append("Recall gesamt")
    for run in runs:
        hits, missed = len(run.candidates & run.labelled), len(run.sample & run.labelled)
        estimate = Share(hits, hits + SAMPLE_EVERY * missed)
        positives = run.in_scope(conn, {a for a, d in gold.items() if d.get(run.tag_id)})
        recall = path_recall(positives, run.candidates, run.labelled)
        row = ["Review-Entscheide", len(positives), recall.candidates, recall.classifier]
        lines += [
            f"### {run.tag_id} (Lauf {run.run_id})",
            "",
            f"- Stichwortsuche: Kandidaten {len(run.candidates)}, davon mit Label {hits}.",
            f"- Stichprobe ohne Stichworttreffer: Geschäfte {len(run.sample)}, davon mit Label"
            f" {missed}. Hochgerechnet (× {SAMPLE_EVERY}) Kandidaten-Recall {estimate}, mit den"
            " Labels des Klassifikators als Wahrheit.",
            "",
            *_table(header, [[*row, recall.overall]]),
        ]
    return lines


def _digital(
    conn: psycopg.Connection,
    runs: list[AdhocRun],
    gold_dir: Path,
    files: dict[str, set[int] | None],
) -> list[str]:
    lines = [f"## Digitalisierung ({DIGITAL}) gegen PolitMonitor und DVS-Liste", ""]
    run = next((r for r in runs if r.tag_id == DIGITAL), None)
    full, path = Share(0, 0), path_recall(set(), set(), set())
    politmonitor, dvs = files[POLITMONITOR], files[DVS]
    if politmonitor is None:
        lines.append(f"- {gold_dir / POLITMONITOR} fehlt: kein Recall gegen PolitMonitor.")
    else:
        known = {row[0] for row in conn.execute(KNOWN, (list(politmonitor),))}
        scope = {row[0] for row in conn.execute(FULL_RUN, (list(known), FULL_RUN_SINCE))}
        labelled = {row[0] for row in conn.execute(FULL_RUN_LABELLED, (DIGITAL,))}
        full = Share(len(scope & labelled), len(scope))
        lines.append(
            f"- PolitMonitor-Positive: in der Datei {len(politmonitor)}, in der Datenbank"
            f" {len(known)}, davon CHE ab {FULL_RUN_SINCE.year} und von classify:aps bearbeitet"
            f" {len(scope)}. Das Tag läuft in classify:aps erst mit, wenn es aktiv ist."
        )
        if run is None:
            lines.append(f"- Kein Lauf {adhoc_task(DIGITAL)}: kein Recall im Kandidatenpfad.")
        else:
            path = path_recall(run.in_scope(conn, known), run.candidates, run.labelled)
    dvs_hits = Share(0, 0)
    if dvs is None:
        lines.append(f"- {gold_dir / DVS} fehlt: kein DVS-Abgleich.")
    else:
        active = {row[0] for row in conn.execute(ACTIVE, (DIGITAL,))}
        known = {row[0] for row in conn.execute(KNOWN, (list(dvs),))}
        dvs_hits = Share(len(dvs & active), len(dvs))
        lines.append(
            f"- DVS-Liste: ohne aktives Label {_ids((dvs & known) - active)},"
            f" nicht in der Datenbank {_ids(dvs - known)}."
        )
    run_name = f" (Lauf {run.run_id})" if run else ""
    rows = [
        [f"Recall Volllauf, CHE ab {FULL_RUN_SINCE.year}", full, "≥ 85 %"],
        [f"Recall Kandidatenpfad gesamt{run_name}", path.overall, "≥ 80 %"],
        ["Kandidaten-Recall der Stichwortsuche", path.candidates, "≥ 95 %"],
        ["Recall des Klassifikators in den Kandidaten", path.classifier, "≥ 85 %"],
        ["DVS-Abgleich: Geschäfte mit aktivem Label", dvs_hits, "≥ 29/30"],
    ]
    return [*lines, "", *_table(["Metrik", "Wert", "Ziel PRD 13"], rows)]


def _ids(ids: set[int]) -> str:
    return ", ".join(map(str, sorted(ids))) if ids else "keine"
