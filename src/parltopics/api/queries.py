"""Lesende Abfragen der Sidecar-API (PRD F10) auf einer Verbindung im Autocommit."""

from datetime import date

import psycopg
from psycopg.rows import dict_row

from parltopics.wiki.tree import sort_key

AFFAIR = """
SELECT a.id AS affair_id, a.body_key, a.number,
       coalesce(a.title_de, a.title_fr, a.title_it, a.title_rm) AS title,
       a.type_harmonized_en AS type, a.begin_date, a.url_external, i.text, i.language,
       s.summary AS summary_de
FROM affairs a
LEFT JOIN affair_inputs i ON i.affair_id = a.id
LEFT JOIN affair_summaries s ON s.affair_id = a.id AND s.language = 'de' AND s.status = 'active'
WHERE a.id = %s
"""
LABELS = """
SELECT l.id, l.tag_id, t.name_de, l.scheme, l.confidence, l.evidence, l.evidence_verified,
       l.status, l.review_status, l.task, l.stage, l.model_version, l.prompt_version,
       l.registry_version, l.input_hash, l.run_id, l.created_at
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
FROM affair_tags l JOIN affairs a ON a.id = l.affair_id
WHERE l.tag_id = %(tag_id)s AND l.status = 'active' AND l.confidence >= %(min_confidence)s
  AND (%(body_key)s::text IS NULL OR a.body_key = %(body_key)s::text)
  AND (%(date_from)s::date IS NULL OR a.begin_date >= %(date_from)s::date)
  AND (%(date_to)s::date IS NULL OR a.begin_date <= %(date_to)s::date)
"""
TOPIC_AFFAIRS = f"""
SELECT a.id AS affair_id, a.body_key, a.number,
       coalesce(a.title_de, a.title_fr, a.title_it, a.title_rm) AS title,
       a.type_harmonized_en AS type, a.begin_date, l.confidence, l.evidence,
       l.evidence_verified, l.stage
{TOPIC_FILTER}
ORDER BY l.confidence DESC, a.begin_date DESC NULLS LAST, a.id DESC
LIMIT %(limit)s OFFSET %(offset)s
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


def topic_affairs(
    conn: psycopg.Connection,
    tag_id: str,
    *,
    body_key: str | None,
    date_from: date | None,
    date_to: date | None,
    min_confidence: float,
    limit: int,
    offset: int,
) -> tuple[int, list[dict]] | None:
    """Geschäfte mit aktivem Label: (Treffer insgesamt, eine Seite); None bei unbekanntem Tag."""
    cursor = conn.cursor(row_factory=dict_row)
    if cursor.execute("SELECT 1 FROM tags WHERE tag_id = %s", (tag_id,)).fetchone() is None:
        return None
    params = {
        "tag_id": tag_id,
        "body_key": body_key,
        "date_from": date_from,
        "date_to": date_to,
        "min_confidence": min_confidence,
        "limit": limit,
        "offset": offset,
    }
    total = cursor.execute(f"SELECT count(*) AS n {TOPIC_FILTER}", params).fetchone()["n"]
    return total, cursor.execute(TOPIC_AFFAIRS, params).fetchall()
