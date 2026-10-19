"""Die lesenden Werkzeuge des Agenten (PRD 7.8, ARCHITEKTUR 4.3).

Jedes Werkzeug liefert ein kleines Ergebnis für den Prompt und die Geschäfts-IDs, die der Agent
danach zitieren darf. Keines schreibt: propose_adhoc_topic liefert nur einen Entwurf, den ein
Mensch in der Web-App mit POST /v1/adhoc bestätigt. navigate_tree protokolliert wie jede
Navigationssuche in search_runs.
"""

import asyncio
import json
import re
from dataclasses import dataclass, field
from typing import Any

import httpx
import psycopg
from psycopg.rows import dict_row

from parltopics.agent.tools import (
    BODIES,
    CountAffairsArgs,
    GenerateKeywordsArgs,
    GetAffairArgs,
    ListTagsArgs,
    NavigateTreeArgs,
    ProposeAdhocTopicArgs,
    ReadPageArgs,
    SearchAffairsArgs,
    ToolArgs,
    ToolError,
)
from parltopics.api import navigate, queries
from parltopics.classify import adhoc
from parltopics.config import Settings
from parltopics.registry import Registry
from parltopics.wiki.tree import Page, children, sort_key, subtree_tag_ids

TEXT_MAX = 2000
SHORT_MAX = 300
GROUPS_MAX = 50
EXAMPLES = 5
TAG_FILTER = """
  AND (cardinality(%(tags)s::text[]) = 0 OR EXISTS (
      SELECT 1 FROM affair_tags l
      WHERE l.affair_id = a.id AND l.status = 'active' AND l.tag_id = ANY(%(tags)s::text[])))
"""
SEARCH = f"""
SELECT d.affair_id FROM search_documents d JOIN affairs a ON a.id = d.affair_id
LEFT JOIN bodies b ON b.body_key = a.body_key
WHERE d.document @@ {queries.TSQUERY} {navigate.FILTERS} {TAG_FILTER}
ORDER BY ts_rank_cd(d.document, {queries.TSQUERY}) DESC, a.id DESC
LIMIT %(limit)s
"""
GROUPS = {
    "body_key": "a.body_key AS key, max(b.name) AS name, max(b.level) AS level",
    "level": "b.level AS key",
    "year": "extract(year FROM a.begin_date)::int AS key",
}
TAG_ID = re.compile(r'"(?:tag_id|page_id)": "([^"]+)"')
BODY_NAMES = """
SELECT body_key, name, level FROM bodies
WHERE body_key = ANY(%(keys)s::text[]) OR name ILIKE ANY(%(keys)s::text[])
"""
ALL_AFFAIRS = (
    "Ohne tags zählt count_affairs alle Geschäfte, nicht die eines Themas. Für ein Thema die"
    " Tag-IDs mit list_tags suchen und als tags übergeben; für alle Geschäfte all_affairs: true."
)

Found = tuple[Any, list[int]]  # Ergebnis für den Prompt, zitierbare Geschäfts-IDs


def _short(text: str | None) -> str | None:
    return text[:SHORT_MAX] if text else text


def _heads(rows: list[dict]) -> list[dict]:
    """Kopf und aktive Themen je Geschäft, knapp für den Prompt."""
    return [
        {
            "affair_id": row["affair_id"],
            "title": row["title"],
            "parliament": row["body_name"] or row["body_key"],
            "level": row["body_level"],
            "date": row["begin_date"],
            "type": row["type_de"] or row["type"],
            "topics": [
                {"tag_id": t["tag_id"], "name_de": t["name_de"], "confidence": t["confidence"]}
                for t in row.get("topics", [])
            ],
        }
        for row in rows
    ]


def _filters(args: SearchAffairsArgs | CountAffairsArgs, tags: list[str]) -> dict:
    """Parameter für navigate.FILTERS und TAG_FILTER."""
    return {
        "tags": tags,
        "body_keys": args.body_keys,
        "levels": [],
        "year_from": args.year_from,
        "year_to": args.year_to,
        "affair_type": getattr(args, "affair_type", None),
    }


@dataclass
class Tools:
    """Die Werkzeuge auf einer Verbindung; ein Aufruf mit geprüften Argumenten (parse_tool_call)."""

    settings: Settings
    conn: psycopg.Connection
    registry: Registry
    tree: dict[str, Page]
    transport: httpx.AsyncBaseTransport | None = None
    known_tags: set[str] = field(default_factory=set)  # Tag-IDs aus Werkzeugergebnissen

    async def __call__(self, name: str, args: ToolArgs) -> Found:
        result, ids = await getattr(self, name)(args)
        self.known_tags.update(TAG_ID.findall(json.dumps(result, ensure_ascii=False, default=str)))
        return result, ids

    def _expand(self, tags: list[str]) -> list[str]:
        """Tags mit ihren Unterthemen (aps:6.1 umfasst aps:6.1.9). Nur IDs aus Werkzeugen: eine
        erfundene ID zählte sonst still null Geschäfte."""
        unknown = [tag for tag in tags if tag not in self.known_tags]
        if unknown:
            raise ToolError(f"Tag-IDs ohne Werkzeugergebnis: {unknown}. Suche sie mit list_tags.")
        below = {
            t.tag_id for t in self.registry.tags for tag in tags if t.tag_id.startswith(f"{tag}.")
        }
        return sorted({*tags, *below})

    def _bodies(self, keys: list[str]) -> dict[str, str]:
        """Namen der Parlamente. Ein unbekanntes Kürzel (Tessin statt TI) geht als Fehler zurück,
        mit passenden Namen als Hinweis: Es zählte sonst still null Geschäfte."""
        if not keys:
            return {}
        rows = self.conn.execute(BODY_NAMES, {"keys": keys}).fetchall()
        names = {key: f"{name} ({level})" for key, name, level in rows if key in keys}
        unknown = [key for key in keys if key not in names]
        if unknown:
            hints = [f"{key} {name} ({level})" for key, name, level in rows if key not in names]
            raise ToolError(f"Unbekannte Parlamente: {unknown}. {BODIES}. Passend: {hints}")
        return names

    async def search_affairs(self, args: SearchAffairsArgs) -> Found:
        tags = self._expand(args.tags)

        def run() -> list[dict]:
            self._bodies(args.body_keys)
            params = {**_filters(args, tags), "q": args.query, "limit": args.limit}
            ids = [row[0] for row in self.conn.execute(SEARCH, params)]
            return _heads(queries.hits(self.conn, ids))

        found = await asyncio.to_thread(run)
        return found, [row["affair_id"] for row in found]

    async def list_tags(self, args: ListTagsArgs) -> Found:
        words = args.query.lower().split()

        def score(tag) -> int:
            labels = (tag.pref_label.de, tag.pref_label.fr, tag.pref_label.it)
            text = " ".join([tag.tag_id, *filter(None, labels), *tag.alt_labels.all()])
            return sum(word in f"{text} {tag.definition.de}".lower() for word in words)

        tags = [
            tag
            for tag in self.registry.tags
            if tag.status in ("active", "proposed") and args.scheme in (None, tag.scheme)
        ]
        ranked = sorted(
            (tag for tag in tags if score(tag)), key=lambda t: (-score(t), sort_key(t.tag_id))
        )
        found = [
            {
                "tag_id": tag.tag_id,
                "name_de": tag.pref_label.de,
                "status": tag.status,
                "definition": _short(tag.definition.de),
            }
            for tag in ranked[: args.limit]
        ]
        return found, []

    async def get_affair(self, args: GetAffairArgs) -> Found:
        affair = await asyncio.to_thread(queries.affair_topics, self.conn, args.affair_id)
        if affair is None:
            return {"error": f"Geschäft {args.affair_id} unbekannt"}, []
        topics = [
            {
                "tag_id": label["tag_id"],
                "name_de": label["name_de"],
                "confidence": label["confidence"],
                "evidence": _short(label["evidence"]),
                "evidence_verified": label["evidence_verified"],
            }
            for label in affair["labels"]
            if label["status"] == "active"
        ]
        (head,) = _heads([affair])
        found = {
            **head,
            "topics": topics,
            "summary_de": affair["summary_de"],
            "url": affair["url_external"],
            "text": (affair["text"] or "")[:TEXT_MAX],
        }
        return found, [args.affair_id]

    async def count_affairs(self, args: CountAffairsArgs) -> Found:
        # Live-Test F21: Ohne diese Sperre gab 70B eine Zählung aller Geschäfte als Thema aus.
        if not args.tags and not args.all_affairs:
            raise ToolError(ALL_AFFAIRS)
        tags = self._expand(args.tags)
        sql = (
            f"SELECT {GROUPS[args.group_by]}, count(*) AS count"
            " FROM affairs a LEFT JOIN bodies b ON b.body_key = a.body_key"
            f" WHERE true {navigate.FILTERS} {TAG_FILTER}"
            f" GROUP BY 1 ORDER BY count DESC, 1 LIMIT {GROUPS_MAX}"
        )
        cursor = self.conn.cursor(row_factory=dict_row)
        params = _filters(args, tags)

        def run() -> tuple[dict[str, str], list[dict]]:
            return self._bodies(args.body_keys), cursor.execute(sql, params).fetchall()

        bodies, rows = await asyncio.to_thread(run)
        # Die Filter stehen mit Namen im Ergebnis, damit das Modell keine Zählung aller Geschäfte,
        # eines anderen Themas oder eines anderen Parlaments dem gefragten zuschreibt.
        names = {tag.tag_id: tag.pref_label.de for tag in self.registry.tags}
        counted = {
            "themen": [f"{tag} {names.get(tag, '')}".strip() for tag in args.tags]
            or "keine: alle Geschäfte, nicht nur eines Themas",
            "parlamente": [f"{key} {bodies[key]}" for key in args.body_keys] or "alle",
            "jahre": [args.year_from, args.year_to],
        }
        return {"group_by": args.group_by, "gezählt": counted, "groups": rows}, []

    async def navigate_tree(self, args: NavigateTreeArgs) -> Found:
        searched = await navigate.search(
            self.settings, self.conn, self.registry, self.tree, args.query, transport=self.transport
        )
        result = searched.result
        hits = await asyncio.to_thread(queries.hits, self.conn, result.affair_ids)
        found = {
            "status": result.status,
            "path": [
                self.tree[p].title if p in self.tree else "Volltextsuche" for p in result.path
            ],
            "statements": [statement.model_dump() for statement in result.statements],
            "affairs": _heads(hits),
        }
        return found, result.affair_ids

    async def read_page(self, args: ReadPageArgs) -> Found:
        page = self.tree.get(args.page_id)
        if page is None:
            return {"error": f"Seite {args.page_id} gibt es nicht"}, []
        tag = next((tag for tag in self.registry.tags if tag.tag_id == page.tag_id), None)
        tag_ids = subtree_tag_ids(self.tree, page.page_id)
        figures = await asyncio.to_thread(queries.page_summary, self.conn, tag_ids)
        kids = children(self.tree, page.page_id)
        found = {
            "page_id": page.page_id,
            "title": page.title,
            "kind": page.kind,
            "definition": _short(tag.definition.de) if tag else None,
            "children": [{"page_id": kid.page_id, "title": kid.title} for kid in kids],
            "figures": {
                key: figures[key]
                for key in ("affairs", "bodies", "first_date", "last_date", "by_level", "by_year")
            },
        }
        return found, []

    async def generate_keywords(self, args: GenerateKeywordsArgs) -> Found:
        keywords = await adhoc.suggest_keywords(
            self.settings, args.name, args.description, transport=self.transport
        )
        return keywords.model_dump(), []

    async def propose_adhoc_topic(self, args: ProposeAdhocTopicArgs) -> Found:
        # Die Stichwörter gelten in allen drei Sprachen; ein Mensch prüft sie vor POST /v1/adhoc.
        keywords = adhoc.Keywords(de=args.keywords, fr=args.keywords, it=args.keywords)

        def run() -> dict:
            candidates, sample = adhoc.find_affairs(self.conn, keywords, bodies=None, since=None)
            return {
                "name_de": args.name,
                "description_de": args.description,
                "keywords": keywords.model_dump(),
                "candidates": len(candidates),
                "sample": len(sample),
                "examples": queries.affair_heads(self.conn, candidates[:EXAMPLES]),
            }

        draft = await asyncio.to_thread(run)
        return draft, [example["affair_id"] for example in draft["examples"]]
