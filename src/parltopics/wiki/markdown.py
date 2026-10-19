"""Markdown-Export des ParlWiki (PRD 7.5, 7.9, F14): Heart, Bereiche, Kapitel, Tag-Seiten,
Querschnitt und Parlamente aus der Datenbank, mit Frontmatter und relativen Links für Obsidian.

Keine Datei je Geschäft: Geschäfte verlinken auf die Web-App und auf OpenParlData, einzeln gibt
es sie nur mit `parltopics wiki --affair`. Zusammengelegte und zurückgezogene Tags bekommen eine
Weiterleitungsseite. Gleiche Datenbank und gleicher Tag ergeben dieselben Dateien; unveränderte
Dateien werden nicht neu geschrieben. Der Export liest die Datenbank nur.

shortcut: Dateien, die der Export nicht mehr erzeugt (Jahreslisten einer Seite unter der Grenze,
Parlamente ohne Labels), bleiben liegen; bei Bedarf das Zielverzeichnis vorher leeren.
"""

import datetime as dt
import posixpath
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import psycopg
import yaml
from psycopg.rows import dict_row

from parltopics.api import queries
from parltopics.registry import Registry
from parltopics.registry.models import Tag
from parltopics.wiki.run import LEVEL_NAMES, months_before, page_stats, prompt_stats
from parltopics.wiki.tree import (
    Page,
    children,
    linked_querschnitt,
    needs_year_split,
    page_ids,
    page_path,
    subtree_tag_ids,
    year_list_path,
)

BODIES_DIR, AFFAIRS_DIR = "parlamente", "geschaefte"
CO_TOPICS = 10
FOOTER = (
    "_Erzeugt aus der Datenbank mit `parltopics wiki`; Änderungen von Hand gehen beim nächsten"
    " Export verloren._"
)
AFFAIR_TABLE = [
    "| Datum | Geschäft | Parlament | Typ | Konfidenz | Quelle |",
    "|---|---|---|---|---|---|",
]
PAGES = """
SELECT page_id, status, summary_short, statements, built_at, window_start, window_end,
       input_hash, model_version, prompt_version
FROM wiki_pages
"""
BODY_TOPICS = """
SELECT a.body_key, l.tag_id, count(DISTINCT l.affair_id) AS count
FROM affair_tags l JOIN affairs a ON a.id = l.affair_id
WHERE l.status = 'active'
GROUP BY a.body_key, l.tag_id
ORDER BY a.body_key, count DESC, l.tag_id
"""


def frontmatter(data: dict) -> str:
    return f"---\n{yaml.safe_dump(data, sort_keys=False, allow_unicode=True)}---\n"


def document(head: dict, lines: list[str]) -> str:
    return f"{frontmatter(head)}\n" + "\n".join([*lines, FOOTER]) + "\n"


def cell(value: object) -> str:
    """Eine Zeile ohne Zeichen, die Tabellen oder Links brechen."""
    text = " ".join(str("" if value is None else value).split())
    return text.replace("|", "\\|").replace("[", "\\[").replace("]", "\\]")


def link(source: str, target: str, text: object) -> str:
    """Relativer Link, damit der Ordner in Obsidian und auf der Festplatte funktioniert."""
    return f"[{cell(text)}]({posixpath.relpath(target, posixpath.dirname(source) or '.')})"


def section(title: str, items: list[str]) -> list[str]:
    return [f"## {title}", "", *items, ""] if items else []


def count(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


def body_path(body_key: str) -> str:
    return f"{BODIES_DIR}/{body_key}.md"


def write(path: Path, text: str) -> bool:
    """Schreibt nur bei geändertem Inhalt, damit Obsidian und Git nichts Neues sehen."""
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    return True


@dataclass
class Wiki:
    """Rendert die Seiten; Kennzahlen und Seitenstand kommen fertig aus export_wiki."""

    conn: psycopg.Connection
    registry: Registry
    tree: dict[str, Page]
    web_url: str
    window_months: int
    stats: dict[str, dict]
    built: dict[str, dict]

    def to(self, source: str, page_id: str) -> str:
        page = self.tree[page_id]
        return link(source, page.path, page.title)

    def affair_url(self, affair_id: int) -> str:
        return f"{self.web_url}/geschaefte/{affair_id}"

    def affair_row(self, source: str, row: dict) -> str:
        """Tabellenzeile: Geschäft in der Web-App, Parlament im Wiki, Quelle bei OpenParlData."""
        affair_id = row["affair_id"]
        name = " ".join(str(part) for part in (row["number"], row["title"] or affair_id) if part)
        parliament = link(source, body_path(row["body_key"]), row["body_name"] or row["body_key"])
        return (
            f"| {row['begin_date'] or ''} | [{cell(name)}]({self.affair_url(affair_id)})"
            f" | {parliament} | {cell(row['type_de'] or row['type'])} | {row['confidence']:.2f}"
            f" | [OpenParlData]({queries.OPENPARLDATA}/affairs/{affair_id}) |"
        )

    def statement(self, source: str, statement: dict) -> str:
        refs = [f"[{i}]({self.affair_url(i)})" for i in statement["affair_ids"]]
        refs += [self.to(source, p) for p in statement["page_ids"] if p in self.tree]
        text = " ".join(statement["text"].split())
        return f"{text} ({', '.join(refs)})" if refs else text

    def page(self, page: Page) -> dict[str, str]:
        """Die Seite selbst, bei grossen Tag-Seiten dazu die Geschäftslisten je Jahr."""
        tag = self.registry.get(page.tag_id) if page.tag_id else None
        row, stats, source = self.built.get(page.page_id, {}), self.stats[page.page_id], page.path
        kids = children(self.tree, page.page_id)
        head = {
            "tag_id": page.tag_id,
            "scheme": tag.scheme if tag else None,
            "registry_version": self.registry.registry_version,
            "parents": [p for p in (page.parent_id, *page.linked_from) if p],
            "children": [kid.page_id for kid in kids],
            "n_affairs": stats["affairs"],
            "page_status": row.get("status"),
            "input_hash": row.get("input_hash"),
            "model_version": row.get("model_version"),
            "prompt_version": row.get("prompt_version"),
            "updated_at": row.get("built_at"),
        }
        lines = [f"# {page.title}", ""]
        if tag:
            lines += [" ".join(tag.definition.de.split()), ""]
        if page.parent_id:
            also = [self.to(source, p) for p in page.linked_from]
            lines += [
                f"Übergeordnet: {self.to(source, page.parent_id)}"
                + (f" · verlinkt von {', '.join(also)}" if also else ""),
                "",
            ]
        if row.get("summary_short"):
            lines += [f"> {' '.join(row['summary_short'].split())}", ""]
            period = (
                f"Zeitraum {row['window_start']} bis {row['window_end']}, {row['model_version']}"
            )
            statements = [f"- {self.statement(source, s)}" for s in row["statements"]]
            lines += section("Zusammenfassung", [f"{period}:", "", *statements])
        subpages = []
        for kid in kids:
            n = self.stats[kid.page_id]["affairs"]
            entry = f"- {self.to(source, kid.page_id)} ({count(n, 'Geschäft', 'Geschäfte')})"
            short = self.built.get(kid.page_id, {}).get("summary_short")
            subpages.append(f"{entry}: {' '.join(short.split())}" if short else entry)
        lines += section("Unterseiten", subpages)
        cross = linked_querschnitt(self.tree, page.page_id)
        lines += section("Querschnittsthemen", [f"- {self.to(source, p.page_id)}" for p in cross])
        figures = [f"- {k}: {v}" for k, v in prompt_stats(stats, self.window_months).items()]
        if stats["first_date"]:
            figures.append(f"- Zeitraum: {stats['first_date']} bis {stats['last_date']}")
        lines += section("Kennzahlen", figures)
        related = tag.related if tag else []
        lines += section("Verwandt", [f"- {self.to(source, t)}" for t in related if t in self.tree])
        files: dict[str, str] = {}
        if page.kind in ("tag", "querschnitt"):
            together = queries.co_topics(self.conn, page.tag_id, CO_TOPICS)
            lines += section(
                "Häufig zusammen mit",
                [
                    f"- {self.to(source, r['tag_id'])}"
                    f" ({count(r['shared'], 'gemeinsames Geschäft', 'gemeinsame Geschäfte')})"
                    for r in together
                    if r["tag_id"] in self.tree
                ],
            )
            rows = sorted(
                queries.stream_topic_affairs(self.conn, [page.tag_id]),
                key=lambda r: (r["begin_date"] or dt.date.min, r["affair_id"]),
                reverse=True,
            )
            if needs_year_split(len(rows)):
                years: dict[int | str, list[dict]] = defaultdict(list)
                for r in rows:
                    years[r["begin_date"].year if r["begin_date"] else "ohne-datum"].append(r)
                for year, chunk in years.items():
                    files[year_list_path(page, year)] = self.year_list(page, year, chunk)
                items = [
                    f"- {link(source, year_list_path(page, y), y)} ({len(c)})"
                    for y, c in years.items()
                ]
                lines += section("Geschäfte nach Jahr", items)
            else:
                lines += section(
                    "Geschäfte", [*AFFAIR_TABLE, *(self.affair_row(source, r) for r in rows)]
                )
        files[page.path] = document(head, lines)
        return files

    def year_list(self, page: Page, year: int | str, rows: list[dict]) -> str:
        path = year_list_path(page, year)
        head = {
            "tag_id": page.tag_id,
            "year": year if isinstance(year, int) else None,
            "n_affairs": len(rows),
            "registry_version": self.registry.registry_version,
        }
        lines = [f"# {page.title}: {year}", "", f"Zurück zu {self.to(path, page.page_id)}", ""]
        return document(
            head, [*lines, *AFFAIR_TABLE, *(self.affair_row(path, r) for r in rows), ""]
        )

    def redirect(self, tag: Tag) -> str:
        """Weiterleitung für ein zusammengelegtes oder zurückgezogenes Tag (PRD 7.9)."""
        path = page_path(tag)
        target = tag.merged_into if tag.merged_into in self.tree else None
        text = (
            f"Dieses Thema ist in {self.to(path, target)} aufgegangen."
            if target
            else "Dieses Thema wird nicht mehr vergeben."
        )
        head = {
            "tag_id": tag.tag_id,
            "scheme": tag.scheme,
            "registry_version": self.registry.registry_version,
            "tag_status": tag.status,
            "merged_into": tag.merged_into,
        }
        return document(head, [f"# {tag.pref_label.de}", "", text, ""])

    def body(self, body: dict, topics: list[dict]) -> str:
        path = body_path(body["body_key"])
        head = {
            "body_key": body["body_key"],
            "name": body["name"],
            "level": body["level"],
            "n_affairs": body["n_affairs"],
            "registry_version": self.registry.registry_version,
        }
        level = LEVEL_NAMES.get(body["level"], body["level"] or "ohne Ebene")
        rows = [
            f"| {self.to(path, t['tag_id'])} | {t['count']} |"
            for t in topics
            if t["tag_id"] in self.tree
        ]
        lines = [
            f"# {cell(body['name'] or body['body_key'])}",
            "",
            f"Ebene: {level}. Geschäfte mit aktiven Labels: {body['n_affairs']}.",
            "",
            *section("Themen", ["| Thema | Geschäfte |", "|---|---|", *rows] if rows else []),
        ]
        return document(head, lines)


def export_wiki(
    conn: psycopg.Connection,
    registry: Registry,
    tree: dict[str, Page],
    out: Path,
    *,
    web_url: str,
    window_months: int,
    today: dt.date,
) -> tuple[int, int]:
    """Alle Seiten, Weiterleitungen und Parlamente nach out: (Dateien, davon geändert)."""
    window_start = months_before(today, window_months)
    stats = {pid: page_stats(conn, subtree_tag_ids(tree, pid), window_start) for pid in tree}
    built = {row["page_id"]: row for row in conn.cursor(row_factory=dict_row).execute(PAGES)}
    wiki = Wiki(conn, registry, tree, web_url.rstrip("/"), window_months, stats, built)
    files: dict[str, str] = {}
    for page_id in page_ids(tree.values()):
        files |= wiki.page(tree[page_id])
    for tag in registry.tags:
        if tag.status in ("merged", "retired"):
            files[page_path(tag)] = wiki.redirect(tag)
    topics: dict[str, list[dict]] = defaultdict(list)
    for row in conn.cursor(row_factory=dict_row).execute(BODY_TOPICS):
        topics[row["body_key"]].append(row)
    for body in queries.bodies(conn):
        files[body_path(body["body_key"])] = wiki.body(body, topics[body["body_key"]])
    return len(files), sum(write(out / path, text) for path, text in files.items())


def export_affair(
    conn: psycopg.Connection, tree: dict[str, Page], out: Path, affair_id: int, *, web_url: str
) -> Path | None:
    """Ein Geschäft als eigene Datei, nur auf Wunsch (PRD 7.5); None, wenn es fehlt."""
    affair = queries.affair_topics(conn, affair_id)
    if affair is None:
        return None
    path = f"{AFFAIRS_DIR}/{affair_id}.md"
    labels = [label for label in affair["labels"] if label["status"] == "active"]
    head = {
        "affair_id": affair_id,
        "body_key": affair["body_key"],
        "number": affair["number"],
        "begin_date": affair["begin_date"],
        "tags": [label["tag_id"] for label in labels],
    }
    links = [
        f"[Web-App]({web_url.rstrip('/')}/geschaefte/{affair_id})",
        f"[OpenParlData]({queries.OPENPARLDATA}/affairs/{affair_id})",
    ]
    if affair["url_external"]:
        links.append(f"[Quelle]({affair['url_external']})")
    facts = [
        link(path, body_path(affair["body_key"]), affair["body_name"] or affair["body_key"]),
        cell(affair["type_de"] or affair["type"]),
        str(affair["begin_date"] or ""),
    ]

    def topic(label: dict) -> str:
        page = tree.get(label["tag_id"])
        return link(path, page.path, page.title) if page else cell(label["name_de"])

    rows = [
        f"| {topic(label)} | {label['confidence']:.2f} | {cell(label['evidence'])}"
        f" | {cell(label['model_version'])} |"
        for label in labels
    ]
    lines = [
        f"# {cell(affair['title'] or f'Geschäft {affair_id}')}",
        "",
        " · ".join(fact for fact in facts if fact),
        "",
        " · ".join(links),
        "",
    ]
    if affair["summary_de"]:
        lines += [" ".join(affair["summary_de"].split()), ""]
    table = ["| Thema | Konfidenz | Beleg | Modell |", "|---|---|---|---|", *rows] if rows else []
    lines += section("Themen", table)
    write(out / path, document(head, lines))
    return out / path
