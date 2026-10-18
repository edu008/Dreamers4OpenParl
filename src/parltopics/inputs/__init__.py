"""Klassifikationstext je Geschäft: HTML entfernen, Sprache, Längenlimit, input_hash (PRD F3, 7.1).

Mit Texten (Bund, einige Kantone): Titel, eingereichter Text, Begründung, übrige Texte. Antworten
der Regierung und die Titel-Zeilen aus affair_texts zählen nicht, der Titel kommt aus affairs.
Ohne Texte: Titel und das älteste Dokument mit Text (PRD 15, Frage 8), sonst nur der Titel.
Als Titel dient der lange Titel aus raw, wenn es ihn in der Sprache gibt, sonst der kurze.
"""

import functools
import hashlib
import html
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from html.parser import HTMLParser

import psycopg
from lingua import Language, LanguageDetectorBuilder
from psycopg.rows import dict_row

INPUT_MAX_CHARS = 6000  # p99 der Bundestexte seit 2024: 5'448 Zeichen
BATCH = 500
LANGS = ("de", "fr", "it", "rm")
SKIP_TYPES = re.compile(r"(?:titel|titre|titolo|antwort|réponse|risposta)", re.IGNORECASE)
RANK = {
    "Eingereichter Text": 0,
    "Texte déposé": 0,
    "Testo depositato": 0,
    "Begründung": 1,
    "Développement": 1,
    "Motivazione": 1,
}
INLINE_TAGS = {"a", "b", "em", "font", "i", "span", "strong", "sub", "sup", "u"}  # sonst Umbruch

AFFAIRS = """
SELECT id, title_de, title_fr, title_it, title_rm,
       raw->>'title_long_de' AS title_long_de, raw->>'title_long_fr' AS title_long_fr,
       raw->>'title_long_it' AS title_long_it, raw->>'title_long_rm' AS title_long_rm
FROM affairs
WHERE id > %(last)s
  AND (%(bodies)s::text[] IS NULL OR body_key = ANY(%(bodies)s::text[]))
  AND (%(since)s::date IS NULL OR begin_date >= %(since)s::date)
ORDER BY id
LIMIT %(batch)s
"""
TEXTS = """
SELECT affair_id, id, text_type, language, text FROM affair_texts
WHERE affair_id = ANY(%s) AND text <> ''
"""
# Das älteste Dokument mit Text; 20'000 Zeichen reichen für 6'000 nach dem Bereinigen.
DOCS = """
SELECT DISTINCT ON (parent_id) parent_id, language, left(text, 20000) AS text FROM affair_docs
WHERE parent_type = 'affair' AND parent_id = ANY(%s) AND text <> ''
ORDER BY parent_id, doc_date NULLS LAST, id
"""
UPSERT = """
INSERT INTO affair_inputs (affair_id, text, language, source, input_hash)
SELECT * FROM unnest(%s::bigint[], %s::text[], %s::text[], %s::text[], %s::text[])
ON CONFLICT (affair_id) DO UPDATE
SET text = EXCLUDED.text, language = EXCLUDED.language, source = EXCLUDED.source,
    input_hash = EXCLUDED.input_hash, built_at = now()
WHERE affair_inputs.input_hash <> EXCLUDED.input_hash
RETURNING affair_id
"""
# Geänderter Text öffnet erledigte Jobs aller Aufgaben (PRD 7.7, F18); failed bleibt failed.
REOPEN = """
WITH reopened AS (
    UPDATE classification_jobs
    SET status = 'open', attempts = 0, last_error = NULL, updated_at = now()
    WHERE affair_id = ANY(%s) AND status = 'done'
    RETURNING affair_id, task, run_id
)
INSERT INTO job_events (affair_id, task, from_status, to_status, reason, run_id)
SELECT affair_id, task, 'done', 'open', 'input_changed', run_id FROM reopened
"""


class _TextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.hidden = 0  # innerhalb von script oder style

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("script", "style"):
            self.hidden += 1
        elif tag not in INLINE_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style"):
            self.hidden = max(0, self.hidden - 1)
        elif tag not in INLINE_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.hidden:
            self.parts.append(data)


def strip_html(value: str) -> str:
    """Text ohne Tags und Entities; Leerraum je Zeile zusammengezogen, leere Zeilen entfernt."""
    parser = _TextParser()
    parser.feed(value)
    parser.close()
    # Einige Quellen kodieren doppelt (&amp;nbsp;): der Parser löst nur eine Ebene auf.
    lines = html.unescape("".join(parser.parts)).splitlines()
    return "\n".join(" ".join(line.split()) for line in lines if line.strip())


@functools.cache
def _detector():
    codes = {Language.GERMAN: "de", Language.FRENCH: "fr", Language.ITALIAN: "it"}
    return LanguageDetectorBuilder.from_languages(*codes).build(), codes


def detect_language(text: str) -> str:
    """de, fr oder it per lingua (offline, Modelle im Wheel); unklar heisst other."""
    detector, codes = _detector()
    return codes.get(detector.detect_language_of(text), "other")


def text_blocks(rows: list[dict]) -> list[tuple[str | None, str]]:
    """(Sprache, Text) der brauchbaren Zeilen aus affair_texts, eingereichter Text zuerst."""
    usable = sorted(
        (row for row in rows if not SKIP_TYPES.match(row["text_type"] or "")),
        key=lambda row: (RANK.get(row["text_type"], 2), row["id"]),
    )
    blocks = [(row["language"], strip_html(row["text"] or "")) for row in usable]
    return [(language, text) for language, text in blocks if text]


def _title(affair: dict, language: str | None) -> str:
    order = (language, *LANGS) if language else LANGS
    # Der lange Titel (Geschäftsart, Urheber, Titel) sagt mehr; sonst der kurze.
    titles = (
        strip_html(affair.get(f"title_long_{lang}") or affair.get(f"title_{lang}") or "")
        for lang in order
    )
    return next((title for title in titles if title), "")


def _clip(parts: list[str]) -> str:
    return "\n".join(part for part in parts if part)[:INPUT_MAX_CHARS]


def compose(
    affair: dict,
    blocks: list[tuple[str | None, str]],
    doc: dict | None,
    detect: Callable[[str], str] = detect_language,
) -> tuple[str, str, str] | None:
    """Klassifikationstext, Sprache und Quelle (texts, first_doc, title_only); None ohne Inhalt."""
    if blocks:
        language = blocks[0][0]
        text = _clip([_title(affair, language), *(body for _, body in blocks)])
        return text, language or detect(text), "texts"
    title = _title(affair, None)
    body = strip_html(doc["text"]) if doc else ""
    if body:
        text = _clip([title, body])
        return text, doc["language"] if doc["language"] in LANGS else detect(text), "first_doc"
    if title:
        text = _clip([title])
        return text, detect(text), "title_only"
    return None


@dataclass(frozen=True)
class InputResult:
    changed: int  # neu oder mit neuem input_hash
    unchanged: int
    skipped: int  # weder Titel noch Text
    reopened: int  # erledigte Jobs, deren Text sich geändert hat


def build_inputs(
    conn: psycopg.Connection,
    *,
    bodies: list[str] | None = None,
    since: date | None = None,
    limit: int | None = None,
) -> InputResult:
    """Baut affair_inputs für die gefilterten Geschäfte, in Stapeln mit je einer Transaktion."""
    changed = unchanged = skipped = reopened = 0
    last = seen = 0
    cursor = conn.cursor(row_factory=dict_row)
    while limit is None or seen < limit:
        batch = BATCH if limit is None else min(BATCH, limit - seen)
        params = {"last": last, "bodies": bodies, "since": since, "batch": batch}
        with conn.transaction():
            affairs = cursor.execute(AFFAIRS, params).fetchall()
            if not affairs:
                break
            ids = [affair["id"] for affair in affairs]
            texts: dict[int, list[dict]] = {}
            for row in cursor.execute(TEXTS, (ids,)).fetchall():
                texts.setdefault(row["affair_id"], []).append(row)
            blocks = {affair_id: text_blocks(texts.get(affair_id, [])) for affair_id in ids}
            missing = [affair_id for affair_id in ids if not blocks[affair_id]]
            docs = {}
            if missing:
                docs = {row["parent_id"]: row for row in cursor.execute(DOCS, (missing,))}
            rows = []
            for affair in affairs:
                built = compose(affair, blocks[affair["id"]], docs.get(affair["id"]))
                if built is None:
                    skipped += 1
                    continue
                text, language, source = built
                digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
                rows.append((affair["id"], text, language, source, digest))
            new = []
            if rows:
                columns = [list(column) for column in zip(*rows, strict=True)]
                new = [row["affair_id"] for row in cursor.execute(UPSERT, columns).fetchall()]
            if new:
                reopened += conn.execute(REOPEN, (new,)).rowcount
        changed += len(new)
        unchanged += len(rows) - len(new)
        last, seen = ids[-1], seen + len(ids)
    return InputResult(changed, unchanged, skipped, reopened)
