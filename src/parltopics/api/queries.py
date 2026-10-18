"""Lesende Abfragen der Sidecar-API (PRD F10) auf einer Verbindung im Autocommit."""

import html
import re
from datetime import date

import psycopg
from psycopg.rows import dict_row

from parltopics.classify.worker import SAMPLE_EVERY
from parltopics.wiki.tree import sort_key

# Kopf eines Geschäfts (schemas.AffairHead), mit bodies b
AFFAIR_HEAD = """
       a.id AS affair_id, a.body_key, b.name AS body_name, b.level AS body_level, a.number,
       coalesce(a.title_de, a.title_fr, a.title_it, a.title_rm) AS title,
       a.type_harmonized_en AS type, a.raw->>'type_harmonized_de' AS type_de, a.begin_date"""
# Ein Label (schemas.LabelOut), mit tags t
LABEL_COLUMNS = """
       l.id, l.tag_id, t.name_de, l.scheme, l.confidence, l.evidence, l.evidence_verified, l.status,
       l.review_status, l.reviewed_by, l.reviewed_at, l.task, l.stage, l.model_version,
       l.prompt_version, l.registry_version, l.input_hash, l.run_id, l.created_at,
       t.status AS tag_status"""

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
# Volltext (F15) ohne Sprachangabe: die Anfrage in allen Konfigurationen, verbunden mit ODER.
TSQUERY = """(websearch_to_tsquery('german', %(q)s) || websearch_to_tsquery('french', %(q)s)
           || websearch_to_tsquery('italian', %(q)s) || websearch_to_tsquery('simple', %(q)s))"""
SEARCH_FILTER = f"""
FROM search_documents d JOIN affairs a ON a.id = d.affair_id
LEFT JOIN bodies b ON b.body_key = a.body_key
WHERE d.document @@ {TSQUERY}
  AND (%(body_key)s::text IS NULL OR a.body_key = %(body_key)s::text)
  AND (%(level)s::text IS NULL OR b.level = %(level)s::text)
  AND (%(date_from)s::date IS NULL OR a.begin_date >= %(date_from)s::date)
  AND (%(date_to)s::date IS NULL OR a.begin_date <= %(date_to)s::date)
  AND (%(language)s::text IS NULL OR d.language = %(language)s::text)
  AND (%(topic)s::text IS NULL OR EXISTS (
      SELECT 1 FROM affair_tags l
      WHERE l.affair_id = a.id AND l.tag_id = %(topic)s::text AND l.status = 'active'))
"""
# Treffer markieren STX und ETX; search() maskiert den Rest und macht daraus <mark>.
MARK = ("\x02", "\x03")
HEADLINE = f"MaxFragments=2, MaxWords=25, MinWords=10, StartSel={MARK[0]}, StopSel={MARK[1]}"


def hit_topics(affair: str) -> str:
    """Aktive Themen eines Geschäfts als JSON-Liste mit Beleg (schemas.HitTopic)."""
    return f"""(SELECT coalesce(json_agg(json_build_object(
                    'tag_id', l.tag_id, 'name_de', t.name_de, 'confidence', l.confidence,
                    'evidence', l.evidence, 'evidence_verified', l.evidence_verified,
                    'stage', l.stage) ORDER BY l.confidence DESC), '[]')
        FROM affair_tags l JOIN tags t ON t.tag_id = l.tag_id
        WHERE l.affair_id = {affair} AND l.status = 'active')"""


SEARCH = f"""
WITH page AS (
    SELECT {AFFAIR_HEAD}, d.language, ts_rank_cd(d.document, {TSQUERY}) AS rank
    {SEARCH_FILTER}
    ORDER BY rank DESC, a.begin_date DESC NULLS LAST, a.id DESC
    LIMIT %(limit)s OFFSET %(offset)s
)
SELECT page.*,
       ts_headline((CASE page.language WHEN 'de' THEN 'german' WHEN 'fr' THEN 'french'
                                       WHEN 'it' THEN 'italian' ELSE 'simple' END)::regconfig,
                   i.text, {TSQUERY}, %(headline)s) AS headline,
       {hit_topics("page.affair_id")} AS topics
FROM page JOIN affair_inputs i ON i.affair_id = page.affair_id
ORDER BY page.rank DESC, page.begin_date DESC NULLS LAST, page.affair_id DESC
"""
# Evaluation aus den Entscheiden der Menschen. Nur Labels des Modells zählen; die Stichprobe
# (jedes 50. Geschäft) ist unabhängig von der Konfidenz ausgewählt, die übrige Warteschlange nicht.
BANDS = 5
REVIEWED_MODEL_LABELS = """
FROM affair_tags
WHERE stage <> 'human' AND review_status IS NOT NULL AND status IN ('active', 'rejected')
"""
CALIBRATION = f"""
SELECT least(floor(confidence * {BANDS}), {BANDS - 1})::int AS band, count(*) AS reviewed,
       count(*) FILTER (WHERE review_status = 'confirmed') AS confirmed,
       count(*) FILTER (WHERE mod(affair_id, {SAMPLE_EVERY}) = 0) AS sample_reviewed,
       count(*) FILTER (WHERE mod(affair_id, {SAMPLE_EVERY}) = 0
                          AND review_status = 'confirmed') AS sample_confirmed
{REVIEWED_MODEL_LABELS}
GROUP BY 1
"""
# Gold-Set: der aktuelle Entscheid je Geschäft und Thema, auch von Hand gesetzte Labels.
GOLD = f"""
SELECT l.affair_id, l.tag_id,
       CASE WHEN l.stage = 'human' THEN 'added' ELSE l.review_status END AS decision,
       l.review_status = 'confirmed' AS belongs,
       CASE WHEN l.stage = 'human' THEN NULL ELSE l.confidence END AS confidence,
       l.stage, l.model_version, l.prompt_version, l.registry_version, l.input_hash,
       l.reviewed_by, l.reviewed_at, mod(l.affair_id, {SAMPLE_EVERY}) = 0 AS sample
FROM affair_tags l
WHERE l.review_status IS NOT NULL AND l.status IN ('active', 'rejected')
ORDER BY l.reviewed_at, l.id
"""
# Graph (F20), Themen untereinander: Kantengewicht = gemeinsame Geschäfte. Ohne Bereich ein
# Knoten je APS-Bereich (der Teil der ID vor dem ersten Punkt), mit Bereich seine Themen.
GRAPH_LABELLED = """
SELECT DISTINCT affair_id,
       CASE WHEN %(area)s::text IS NULL THEN split_part(tag_id, '.', 1) ELSE tag_id END AS node
FROM affair_tags
WHERE status = 'active' AND scheme = 'aps'
  AND (%(area)s::text IS NULL OR tag_id LIKE %(area)s::text || '.%%')
"""
GRAPH_NODES = f"""
WITH labelled AS ({GRAPH_LABELLED})
SELECT node, count(*) AS count FROM labelled GROUP BY node
"""
GRAPH_EDGES = f"""
WITH labelled AS ({GRAPH_LABELLED})
SELECT x.node AS a, y.node AS b, count(*) AS weight, count(*) OVER () AS qualifying
FROM labelled x JOIN labelled y ON y.affair_id = x.affair_id AND x.node < y.node
GROUP BY x.node, y.node
HAVING count(*) >= %(min_weight)s
ORDER BY weight DESC, a, b
LIMIT %(limit)s
"""
CO_TOPICS = """
SELECT o.tag_id, t.name_de, count(DISTINCT o.affair_id) AS shared
FROM affair_tags l
JOIN affair_tags o ON o.affair_id = l.affair_id AND o.tag_id <> l.tag_id AND o.status = 'active'
JOIN tags t ON t.tag_id = o.tag_id
WHERE l.tag_id = %(tag_id)s AND l.status = 'active'
GROUP BY o.tag_id, t.name_de
ORDER BY shared DESC, o.tag_id
LIMIT %(limit)s
"""
# Tag-Vorschläge (F7) mit Varianten, Zahl und Auswahl der betroffenen Geschäfte.
PROPOSALS = """
SELECT p.id, p.name_de, p.desc_de, p.reason, p.recommendation, p.related_tag_id,
       rt.name_de AS related_name_de, p.status, p.decision, p.decided_by, p.decided_at,
       p.created_at, p.model_version,
       (SELECT count(*) FROM tag_proposal_affairs pa WHERE pa.proposal_id = p.id) AS n_affairs,
       ARRAY(SELECT DISTINCT r.name_de FROM tag_proposal_raw r WHERE r.proposal_id = p.id
             ORDER BY r.name_de LIMIT 5) AS variants,
       ARRAY(SELECT pa.affair_id FROM tag_proposal_affairs pa WHERE pa.proposal_id = p.id
             ORDER BY pa.affair_id DESC LIMIT 5) AS affair_ids
FROM tag_proposals p LEFT JOIN tags rt ON rt.tag_id = p.related_tag_id
"""
PROPOSAL_STATE = {"open": "p.status <> 'done'", "done": "p.status = 'done'"}
PROPOSAL_ORDER = {"open": "n_affairs DESC, p.id DESC", "done": "p.decided_at DESC, p.id DESC"}
RUNS = """
SELECT id, task, kind, started_at, finished_at, n_total, n_done, n_failed, n_escalated,
       prompt_version, registry_version,
       extract(epoch FROM coalesce(finished_at, now()) - started_at)::int AS duration_s,
       round(n_done * 60.0
             / nullif(extract(epoch FROM coalesce(finished_at, now()) - started_at), 0), 1)
           AS per_minute
FROM classification_runs ORDER BY id DESC LIMIT 10
"""
JOB_ERRORS = """
SELECT task, left(split_part(coalesce(last_error, ''), chr(10), 1), 160) AS reason,
       count(*) AS count
FROM classification_jobs WHERE status = 'failed'
GROUP BY 1, 2 ORDER BY count DESC, reason LIMIT 10
"""
STATS = """
SELECT (SELECT count(*) FROM affairs) AS affairs,
       (SELECT count(*) FROM affair_inputs) AS prepared,
       (SELECT count(*) FROM search_documents) AS indexed,
       (SELECT count(*) FROM classification_jobs
        WHERE task = 'classify:aps' AND status = 'done') AS classified,
       (SELECT count(DISTINCT affair_id) FROM affair_tags WHERE status = 'active') AS labelled,
       (SELECT count(*) FROM affair_tags WHERE status = 'active') AS labels,
       (SELECT count(*) FROM affair_tags
        WHERE review_status IS NOT NULL AND status IN ('active', 'rejected')) AS reviewed
"""
# Nur Parlamente mit klassifizierten Geschäften: Filter ohne leere Treffer.
BODIES = """
SELECT a.body_key, b.name, b.level, count(DISTINCT a.id) AS n_affairs
FROM affairs a JOIN affair_tags l ON l.affair_id = a.id AND l.status = 'active'
LEFT JOIN bodies b ON b.body_key = a.body_key
GROUP BY a.body_key, b.name, b.level
ORDER BY array_position(ARRAY['country', 'canton', 'city', 'municipality'], b.level), b.name,
         a.body_key
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


def runs(conn: psycopg.Connection) -> list[dict]:
    return conn.cursor(row_factory=dict_row).execute(RUNS).fetchall()


def job_errors(conn: psycopg.Connection) -> list[dict]:
    return conn.cursor(row_factory=dict_row).execute(JOB_ERRORS).fetchall()


def stats(conn: psycopg.Connection) -> dict:
    return conn.cursor(row_factory=dict_row).execute(STATS).fetchone()


def bodies(conn: psycopg.Connection) -> list[dict]:
    return conn.cursor(row_factory=dict_row).execute(BODIES).fetchall()


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


def search(
    conn: psycopg.Connection,
    *,
    q: str,
    topic: str | None,
    body_key: str | None,
    level: str | None,
    language: str | None,
    date_from: date | None,
    date_to: date | None,
    limit: int,
    offset: int,
) -> tuple[int, list[dict]]:
    """Volltextsuche: (Treffer insgesamt, eine Seite mit Ausschnitt als sicherem HTML).

    shortcut: rechnet den Rang für alle Treffer; bei sehr häufigen Wörtern über 326k Geschäfte
    wird das langsam, dann Treffer vor dem Rang begrenzen.
    """
    params = {
        "q": q,
        "topic": topic,
        "body_key": body_key,
        "level": level,
        "language": language,
        "date_from": date_from,
        "date_to": date_to,
        "limit": limit,
        "offset": offset,
        "headline": HEADLINE,
    }
    cursor = conn.cursor(row_factory=dict_row)
    total = cursor.execute(f"SELECT count(*) AS n {SEARCH_FILTER}", params).fetchone()["n"]
    rows = cursor.execute(SEARCH, params).fetchall()
    for row in rows:
        # Der Text ist frei von Tags, kann aber Zeichen wie < enthalten: erst maskieren.
        escaped = html.escape(row["headline"])
        row["headline"] = escaped.replace(MARK[0], "<mark>").replace(MARK[1], "</mark>")
    return total, rows


def calibration(conn: psycopg.Connection) -> list[dict]:
    """Je Konfidenzband: geprüft, bestätigt und Trefferquote, gesamt und nur in der Stichprobe."""
    rows = {row["band"]: row for row in conn.cursor(row_factory=dict_row).execute(CALIBRATION)}
    empty = {"reviewed": 0, "confirmed": 0, "sample_reviewed": 0, "sample_confirmed": 0}

    def share(part: int, whole: int) -> float | None:
        return part / whole if whole else None

    bands = []
    for band in range(BANDS):
        row = rows.get(band, empty)
        bands.append(
            {
                "low": band / BANDS,
                "high": (band + 1) / BANDS,
                "reviewed": row["reviewed"],
                "confirmed": row["confirmed"],
                "precision": share(row["confirmed"], row["reviewed"]),
                "sample_reviewed": row["sample_reviewed"],
                "sample_confirmed": row["sample_confirmed"],
                "sample_precision": share(row["sample_confirmed"], row["sample_reviewed"]),
            }
        )
    return bands


def gold(conn: psycopg.Connection) -> list[dict]:
    return conn.cursor(row_factory=dict_row).execute(GOLD).fetchall()


def topic_graph(
    conn: psycopg.Connection, *, area: str | None, min_weight: int, limit: int
) -> tuple[list[dict], list[dict], int]:
    """Knoten, die stärksten Kanten und die Zahl der Kanten, die wegen limit fehlen.

    shortcut: rechnet bei jedem Aufruf über alle aktiven Labels; bei voller Klassifikation
    (rund 650k Labels) das Ergebnis nach jedem Lauf zwischenspeichern.
    """
    params = {"area": area, "min_weight": min_weight, "limit": limit}
    cursor = conn.cursor(row_factory=dict_row)
    nodes = sorted(
        cursor.execute(GRAPH_NODES, params).fetchall(), key=lambda n: sort_key(n["node"])
    )
    edges = cursor.execute(GRAPH_EDGES, params).fetchall()
    return nodes, edges, (edges[0]["qualifying"] - len(edges)) if edges else 0


def co_topics(conn: psycopg.Connection, tag_id: str, limit: int) -> list[dict]:
    """Themen mit den meisten gemeinsamen Geschäften (aktive Labels)."""
    params = {"tag_id": tag_id, "limit": limit}
    return conn.cursor(row_factory=dict_row).execute(CO_TOPICS, params).fetchall()


def affair_heads(conn: psycopg.Connection, ids: list[int]) -> list[dict]:
    """Köpfe dieser Geschäfte in der Reihenfolge von ids."""
    sql = f"""SELECT {AFFAIR_HEAD} FROM affairs a LEFT JOIN bodies b ON b.body_key = a.body_key
              WHERE a.id = ANY(%s)"""
    rows = {row["affair_id"]: row for row in conn.cursor(row_factory=dict_row).execute(sql, (ids,))}
    return [rows[affair_id] for affair_id in ids if affair_id in rows]


def proposals(
    conn: psycopg.Connection, *, state: str, limit: int, offset: int
) -> tuple[int, list[dict]]:
    """Offene (meiste Geschäfte zuerst) oder entschiedene Vorschläge (neueste zuerst)."""
    where = PROPOSAL_STATE[state]
    cursor = conn.cursor(row_factory=dict_row)
    count = f"SELECT count(*) AS n FROM tag_proposals p WHERE {where}"
    total = cursor.execute(count).fetchone()["n"]
    rows = cursor.execute(
        f"{PROPOSALS} WHERE {where} ORDER BY {PROPOSAL_ORDER[state]}"
        " LIMIT %(limit)s OFFSET %(offset)s",
        {"limit": limit, "offset": offset},
    ).fetchall()
    return total, _with_affairs(conn, rows)


def proposal(conn: psycopg.Connection, proposal_id: int) -> dict | None:
    sql = f"{PROPOSALS} WHERE p.id = %(id)s"
    rows = conn.cursor(row_factory=dict_row).execute(sql, {"id": proposal_id}).fetchall()
    return _with_affairs(conn, rows)[0] if rows else None


def _with_affairs(conn: psycopg.Connection, rows: list[dict]) -> list[dict]:
    """Ersetzt affair_ids durch die Köpfe der Geschäfte, mit einer Abfrage für alle Zeilen."""
    ids = [affair_id for row in rows for affair_id in row["affair_ids"]]
    heads = {head["affair_id"]: head for head in affair_heads(conn, ids)}
    for row in rows:
        row["affairs"] = [heads[i] for i in row.pop("affair_ids") if i in heads]
    return rows


def hits(conn: psycopg.Connection, ids: list[int]) -> list[dict]:
    """Köpfe dieser Geschäfte mit ihren aktiven Themen, in der Reihenfolge von ids."""
    sql = f"""SELECT {AFFAIR_HEAD}, {hit_topics("a.id")} AS topics
              FROM affairs a LEFT JOIN bodies b ON b.body_key = a.body_key WHERE a.id = ANY(%s)"""
    rows = {row["affair_id"]: row for row in conn.cursor(row_factory=dict_row).execute(sql, (ids,))}
    return [rows[affair_id] for affair_id in ids if affair_id in rows]


# Gespeicherte OpenParlData-Datensätze (raw), Sprachfelder geschachtelt wie bei OpenParlData.
OPENPARLDATA = "https://api.openparldata.ch/v1"  # nur als Link in den Antworten, nie aufgerufen
LANGUAGE_KEY = re.compile(r"(.+)_(de|fr|it|rm|en)")
AFFAIR_RECORD = """
SELECT a.id, a.body_key, a.raw, b.id AS body_row_id, b.raw AS body_raw
FROM affairs a LEFT JOIN bodies b ON b.body_key = a.body_key
WHERE a.id = %s
"""
BODY_RECORD = """
SELECT b.id, b.body_key, b.raw,
       (SELECT count(*) FROM affairs a WHERE a.body_key = b.body_key) AS n_affairs,
       (SELECT count(DISTINCT l.affair_id) FROM affair_tags l JOIN affairs a ON a.id = l.affair_id
        WHERE a.body_key = b.body_key AND l.status = 'active') AS n_labelled
FROM bodies b WHERE b.body_key = %s
"""
DOCS_OF_AFFAIR = "FROM affair_docs WHERE parent_type = 'affair' AND parent_id = %(affair_id)s"
# Der Text der Dokumente bleibt in der Liste weg (bis einige MB je Dokument).
DOC_COLUMNS = "id, raw, coalesce(text, '') <> '' AS has_text"
FIRST_DOCS = 20


def nest_languages(record: dict) -> dict:
    """title_de, title_fr → title {"de": …, "fr": …}. Leere Sprachen fallen weg, der Schlüssel
    bleibt ({}); ein gleichnamiges Feld ohne Sprache (bodies: name) weicht der Schachtelung."""
    flat: dict = {}
    nested: dict[str, dict] = {}
    for key, value in record.items():
        match = LANGUAGE_KEY.fullmatch(key)
        if match is None:
            flat[key] = value
            continue
        languages = nested.setdefault(match[1], {})
        if value is not None:
            languages[match[2]] = value
    return flat | nested


def _body(body_id: int, body_key: str, raw: dict) -> dict:
    url = f"{OPENPARLDATA}/bodies/{body_id}"
    return {**nest_languages(raw), "id": body_id, "body_key": body_key, "url_api": url}


def _text(row: dict) -> dict:
    """Ein Text mit allen Sprachen: Ingest legt die erste in text ab, die übrigen bleiben in raw."""
    raw = dict(row["raw"])
    if row["language"]:
        raw[f"text_{row['language']}"] = row["text"]
    return {**nest_languages(raw), "id": row["id"]}


def _doc(row: dict) -> dict:
    return {**nest_languages(row.pop("raw")), **row}


def affair_exists(conn: psycopg.Connection, affair_id: int) -> bool:
    return conn.execute("SELECT 1 FROM affairs WHERE id = %s", (affair_id,)).fetchone() is not None


def affair_record(conn: psycopg.Connection, affair_id: int) -> dict | None:
    """affairs.raw mit Parlament, Texten und den ersten Dokumenten; None, wenn es fehlt."""
    cursor = conn.cursor(row_factory=dict_row)
    row = cursor.execute(AFFAIR_RECORD, (affair_id,)).fetchone()
    if row is None:
        return None
    texts = cursor.execute(
        "SELECT id, language, text, raw FROM affair_texts WHERE affair_id = %s ORDER BY id",
        (affair_id,),
    ).fetchall()
    n_docs, docs = affair_docs(conn, affair_id, limit=FIRST_DOCS, offset=0)
    body = row["body_row_id"]
    return {
        **nest_languages(row["raw"]),
        "id": affair_id,
        "body_key": row["body_key"],
        "url_api": f"{OPENPARLDATA}/affairs/{affair_id}",
        "body": _body(body, row["body_key"], row["body_raw"]) if body is not None else None,
        "texts": [_text(text) for text in texts],
        "docs": docs,
        "n_docs": n_docs,
    }


def affair_docs(
    conn: psycopg.Connection, affair_id: int, *, limit: int, offset: int
) -> tuple[int, list[dict]]:
    """Dokumente eines Geschäfts ohne Text, nach Datum: (Treffer insgesamt, eine Seite)."""
    params = {"affair_id": affair_id, "limit": limit, "offset": offset}
    cursor = conn.cursor(row_factory=dict_row)
    total = cursor.execute(f"SELECT count(*) AS n {DOCS_OF_AFFAIR}", params).fetchone()["n"]
    rows = cursor.execute(
        f"SELECT {DOC_COLUMNS} {DOCS_OF_AFFAIR}"
        " ORDER BY doc_date NULLS LAST, id LIMIT %(limit)s OFFSET %(offset)s",
        params,
    ).fetchall()
    return total, [_doc(row) for row in rows]


def doc(conn: psycopg.Connection, doc_id: int) -> dict | None:
    """Ein Dokument mit extrahiertem Text, zu welchem Elternteil auch immer."""
    sql = f"SELECT {DOC_COLUMNS}, parent_type, parent_id, text FROM affair_docs WHERE id = %s"
    row = conn.cursor(row_factory=dict_row).execute(sql, (doc_id,)).fetchone()
    return _doc(row) if row else None


def body_record(conn: psycopg.Connection, body_key: str) -> dict | None:
    row = conn.cursor(row_factory=dict_row).execute(BODY_RECORD, (body_key,)).fetchone()
    if row is None:
        return None
    counts = {"n_affairs": row["n_affairs"], "n_labelled": row["n_labelled"]}
    return {**_body(row["id"], row["body_key"], row["raw"]), **counts}
