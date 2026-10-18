"""Lesende Abfragen der Sidecar-API (PRD F10) auf einer Verbindung im Autocommit."""

from datetime import date

import psycopg
from psycopg.rows import dict_row

from parltopics.classify.worker import SAMPLE_EVERY
from parltopics.wiki.tree import sort_key

# Kopf eines Geschäfts (schemas.AffairHead), mit bodies b
AFFAIR_HEAD = """
       a.id AS affair_id, a.body_key, b.name AS body_name, b.level AS body_level, a.number,
       coalesce(a.title_de, a.title_fr, a.title_it, a.title_rm) AS title,
       a.type_harmonized_en AS type, a.begin_date"""
# Ein Label (schemas.LabelOut), mit tags t
LABEL_COLUMNS = """
       l.id, l.tag_id, t.name_de, l.scheme, l.confidence, l.evidence, l.evidence_verified, l.status,
       l.review_status, l.reviewed_by, l.reviewed_at, l.task, l.stage, l.model_version,
       l.prompt_version, l.registry_version, l.input_hash, l.run_id, l.created_at"""

AFFAIR = f"""
SELECT {AFFAIR_HEAD}, a.url_external, i.text, i.language, s.summary AS summary_de
FROM affairs a
LEFT JOIN bodies b ON b.body_key = a.body_key
LEFT JOIN affair_inputs i ON i.affair_id = a.id
LEFT JOIN affair_summaries s ON s.affair_id = a.id AND s.language = 'de' AND s.status = 'active'
WHERE a.id = %s
"""
LABELS = f"""
SELECT {LABEL_COLUMNS}
FROM affair_tags l JOIN tags t ON t.tag_id = l.tag_id
WHERE l.affair_id = %s
ORDER BY l.status = 'active' DESC, l.confidence DESC, l.id DESC
"""
TOPICS = """
SELECT t.tag_id, t.scheme, t.status, t.parent_id, t.name_de, t.name_fr, t.name_it,
       count(l.id) AS n_affairs
FROM tags t LEFT JOIN affair_tags l ON l.tag_id = t.tag_id AND l.status = 'active'
WHERE %(scheme)s::text IS NULL OR t.scheme = %(scheme)s::text
GROUP BY t.tag_id
"""
TOPIC_FILTER = """
FROM affair_tags l JOIN affairs a ON a.id = l.affair_id JOIN tags t ON t.tag_id = l.tag_id
LEFT JOIN bodies b ON b.body_key = a.body_key
WHERE l.tag_id = ANY(%(tag_ids)s) AND l.status = 'active' AND l.confidence >= %(min_confidence)s
  AND (%(body_key)s::text IS NULL OR a.body_key = %(body_key)s::text)
  AND (%(level)s::text IS NULL OR b.level = %(level)s::text)
  AND (%(type)s::text IS NULL OR a.type_harmonized_en = %(type)s::text)
  AND (%(date_from)s::date IS NULL OR a.begin_date >= %(date_from)s::date)
  AND (%(date_to)s::date IS NULL OR a.begin_date <= %(date_to)s::date)
"""
TOPIC_AFFAIRS = f"""
SELECT {AFFAIR_HEAD}, l.tag_id, t.name_de, l.confidence, l.evidence, l.evidence_verified,
       l.stage
{TOPIC_FILTER}
ORDER BY l.confidence DESC, a.begin_date DESC NULLS LAST, a.id DESC, l.id DESC
LIMIT %(limit)s OFFSET %(offset)s
"""
# Warteschlange: dieselben Gründe wie in der Web-App (web/src/lib/label-state.ts) und die
# Stichprobe des Workers. Ohne Beleg ist ein Label nie belegt (evidence_verified = false).
REASONS = f"""array_remove(ARRAY[
           CASE WHEN l.confidence < %(threshold)s THEN 'low_confidence' END,
           CASE WHEN l.evidence IS NULL THEN 'no_evidence'
                WHEN NOT l.evidence_verified THEN 'evidence_unverified' END,
           CASE WHEN l.affair_id %% {SAMPLE_EVERY} = 0 THEN 'sample' END
       ], NULL) AS reasons"""
QUEUE_STATE = {
    "open": "l.status = 'active' AND l.review_status IS NULL AND (l.confidence < %(threshold)s"
    f" OR NOT l.evidence_verified OR l.affair_id %% {SAMPLE_EVERY} = 0)",
    "done": "l.review_status IS NOT NULL AND l.status IN ('active', 'rejected')",
}
QUEUE_ORDER = {
    "open": "l.confidence, l.affair_id, l.id",
    "done": "l.reviewed_at DESC NULLS LAST, l.id DESC",
}
QUEUE_FROM = """
FROM affair_tags l JOIN tags t ON t.tag_id = l.tag_id JOIN affairs a ON a.id = l.affair_id
LEFT JOIN bodies b ON b.body_key = a.body_key
"""
QUEUE_FILTER = """
  AND (%(tag_id)s::text IS NULL OR l.tag_id = %(tag_id)s::text)
  AND (%(body_key)s::text IS NULL OR a.body_key = %(body_key)s::text)
"""


def affair_topics(conn: psycopg.Connection, affair_id: int) -> dict | None:
    """Ein Geschäft mit Text, Kurzzusammenfassung und allen Labels; None, wenn es fehlt."""
    cursor = conn.cursor(row_factory=dict_row)
    affair = cursor.execute(AFFAIR, (affair_id,)).fetchone()
    if affair is not None:
        affair["labels"] = cursor.execute(LABELS, (affair_id,)).fetchall()
    return affair


def topics(conn: psycopg.Connection, scheme: str | None) -> list[dict]:
    """Tags mit der Zahl ihrer aktiven Labels, sortiert wie der Seitenbaum."""
    rows = conn.cursor(row_factory=dict_row).execute(TOPICS, {"scheme": scheme}).fetchall()
    return sorted(rows, key=lambda row: sort_key(row["tag_id"]))


def tag_exists(conn: psycopg.Connection, tag_id: str) -> bool:
    return conn.execute("SELECT 1 FROM tags WHERE tag_id = %s", (tag_id,)).fetchone() is not None


def topic_affairs(
    conn: psycopg.Connection,
    tag_ids: list[str],
    *,
    body_key: str | None,
    date_from: date | None,
    date_to: date | None,
    min_confidence: float,
    limit: int,
    offset: int,
    level: str | None = None,
    affair_type: str | None = None,
) -> tuple[int, list[dict]]:
    """Geschäfte mit aktivem Label eines der Tags, eine Zeile je Geschäft und Tag:
    (Treffer insgesamt, eine Seite)."""
    cursor = conn.cursor(row_factory=dict_row)
    params = {
        "tag_ids": tag_ids,
        "body_key": body_key,
        "level": level,
        "type": affair_type,
        "date_from": date_from,
        "date_to": date_to,
        "min_confidence": min_confidence,
        "limit": limit,
        "offset": offset,
    }
    total = cursor.execute(f"SELECT count(*) AS n {TOPIC_FILTER}", params).fetchone()["n"]
    return total, cursor.execute(TOPIC_AFFAIRS, params).fetchall()


def review_queue(
    conn: psycopg.Connection,
    *,
    state: str,
    tag_id: str | None,
    body_key: str | None,
    threshold: float,
    limit: int,
    offset: int,
) -> tuple[int, list[dict]]:
    """Labels mit Prüfbedarf (open) oder mit Entscheid (done): (Treffer insgesamt, eine Seite).

    shortcut: liest alle aktiven Labels ohne Entscheid; ab einigen 100'000 Labels braucht es einen
    partiellen Index auf confidence (Migration).
    """
    where = f"{QUEUE_FROM} WHERE {QUEUE_STATE[state]} {QUEUE_FILTER}"
    params = {
        "threshold": threshold,
        "tag_id": tag_id,
        "body_key": body_key,
        "limit": limit,
        "offset": offset,
    }
    cursor = conn.cursor(row_factory=dict_row)
    total = cursor.execute(f"SELECT count(*) AS n {where}", params).fetchone()["n"]
    rows = cursor.execute(
        f"SELECT {AFFAIR_HEAD}, {LABEL_COLUMNS}, {REASONS} {where}"
        f" ORDER BY {QUEUE_ORDER[state]} LIMIT %(limit)s OFFSET %(offset)s",
        params,
    ).fetchall()
    return total, rows
