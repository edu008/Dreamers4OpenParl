"""Seitenbaum des ParlWiki aus der Registry (PRD 7.9, ADR 0008).

Reine Logik ohne Datenbank: Seiten, Eltern und Kinder, Dateinamen, Jahresteilung, Weitergabe
von Änderungen nach oben und Schwellen. Speicherung und LLM-Aufrufe folgen in Meilenstein M3.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field, replace
from typing import Literal

from parltopics.registry.models import Registry, Tag

HEART_ID = "heart"
HEART_PATH = "HEART.md"
# Anzeigetitel der Wurzel. page_id und Dateiname bleiben intern ("heart", HEART.md).
HEART_TITLES = {"de": "Themen", "fr": "Thèmes", "it": "Temi"}
YEAR_SPLIT_THRESHOLD = 1000

PageKind = Literal["heart", "bereich", "kapitel", "tag", "querschnitt"]
PageStatus = Literal["open", "pending", "done", "failed"]
FOLDERS: dict[str, str] = {
    "bereich": "bereiche",
    "kapitel": "kapitel",
    "tag": "tags",
    "querschnitt": "querschnitt",
}


class TreeError(ValueError):
    """Die Registry ergibt keinen gültigen Seitenbaum."""


@dataclass(frozen=True)
class Page:
    """title ist der deutsche Anzeigetitel; titles trägt alle Sprachen der Registry (prefLabel)."""

    page_id: str
    kind: PageKind
    title: str
    path: str
    tag_id: str | None = None
    parent_id: str | None = None
    linked_from: tuple[str, ...] = ()
    titles: dict[str, str] = field(default_factory=dict, compare=False)

    def title_in(self, lang: str) -> str:
        """Titel in der gewünschten Sprache, sonst Deutsch."""
        return self.titles.get(lang) or self.title


def page_kind(tag: Tag) -> PageKind:
    if tag.scheme == "adhoc":
        return "querschnitt"
    return {"bereich": "bereich", "kapitel": "kapitel", "thema": "tag"}[tag.aps_level]


def page_path(tag: Tag) -> str:
    """Stabiler Dateiname aus der Tag-ID; APS mit festem slug, Ad-hoc trägt den Namen in der ID."""
    stem = tag.tag_id.replace(":", "-")
    if tag.slug:
        stem = f"{stem}-{tag.slug}"
    return f"{FOLDERS[page_kind(tag)]}/{stem}.md"


def year_list_path(page: Page, year: int) -> str:
    """Geschäftsliste eines Jahres; die Hub-Datei der Seite bleibt unverändert."""
    return f"{page.path.removesuffix('.md')}/{year}.md"


def needs_year_split(n_affairs: int) -> bool:
    return n_affairs > YEAR_SPLIT_THRESHOLD


def sort_key(page_id: str) -> tuple:
    """Heart zuerst, dann APS nach Code (6.1.9 vor 6.1.10), dann Ad-hoc alphabetisch."""
    if page_id == HEART_ID:
        return (0,)
    scheme, code = page_id.split(":", 1)
    if scheme == "aps":
        return (1, tuple(int(part) for part in code.split(".")))
    return (2, code)


def build_tree(registry: Registry) -> dict[str, Page]:
    """Seite für jedes aktive Tag plus Heart. Ad-hoc-Tags hängen als Querschnitt unter Heart."""
    pages: dict[str, Page] = {
        HEART_ID: Page(
            page_id=HEART_ID,
            kind="heart",
            title=HEART_TITLES["de"],
            path=HEART_PATH,
            titles=dict(HEART_TITLES),
        )
    }
    active = {tag.tag_id: tag for tag in registry.active()}
    for tag in active.values():
        kind = page_kind(tag)
        if kind in ("bereich", "querschnitt"):
            parent = HEART_ID
        else:
            parent = tag.broader[0]
            if parent not in active:
                raise TreeError(f"{tag.tag_id}: Eltern-Seite {parent} ist nicht aktiv")
        linked = (
            tuple(sorted(t for t in tag.broader if t in active)) if kind == "querschnitt" else ()
        )
        pages[tag.tag_id] = Page(
            page_id=tag.tag_id,
            kind=kind,
            title=tag.pref_label.de,
            path=page_path(tag),
            tag_id=tag.tag_id,
            parent_id=parent,
            linked_from=linked,
            titles=tag.pref_label.model_dump(exclude_none=True),
        )
    return pages


def children(pages: dict[str, Page], page_id: str) -> list[Page]:
    found = [page for page in pages.values() if page.parent_id == page_id]
    return sorted(found, key=lambda page: sort_key(page.page_id))


def linked_querschnitt(pages: dict[str, Page], page_id: str) -> list[Page]:
    """Querschnittsseiten, die von dieser Seite verlinkt, aber nicht zusammengefasst werden."""
    found = [page for page in pages.values() if page_id in page.linked_from]
    return sorted(found, key=lambda page: sort_key(page.page_id))


def ancestors(pages: dict[str, Page], page_id: str) -> list[str]:
    chain, current = [], pages[page_id].parent_id
    while current is not None:
        chain.append(current)
        current = pages[current].parent_id
    return chain


@dataclass(frozen=True)
class Thresholds:
    """Ab wann eine Zusammenfassung neu entsteht (PRD 7.9, konfigurierbar)."""

    tag_changes: int = 5
    parent_changes: int = 1
    max_age: dt.timedelta = dt.timedelta(days=7)


DEFAULT_THRESHOLDS = Thresholds()


@dataclass
class PageState:
    """Stand einer Seite. Neue Seiten beginnen als open, wie in wiki_pages."""

    status: PageStatus = "open"
    pending_changes: int = 0
    built_at: dt.datetime | None = None
    cited_label_removed: bool = False
    last_error: str | None = None


PageOutcome = Literal["changed", "unchanged", "failed"]


def should_open(
    page: Page, state: PageState, now: dt.datetime, thresholds: Thresholds = DEFAULT_THRESHOLDS
) -> bool:
    """Seite in diesem Lauf bauen?

    Immer bei weggefallenem Beleg und bei neuen Seiten (open, nie gebaut). Eine failed-Seite erst
    wieder, wenn neue Änderungen eintreffen; eine pending-Seite gehört einem anderen Worker.
    Sonst entscheiden Schwelle und Alter.
    """
    if state.cited_label_removed:
        return True
    if state.status == "pending":
        return False
    if state.status == "failed":
        return state.pending_changes > 0
    if state.status == "open" or state.built_at is None:
        return True
    if state.pending_changes <= 0:
        return False
    limit = (
        thresholds.tag_changes if page.kind in ("tag", "querschnitt") else thresholds.parent_changes
    )
    if state.pending_changes >= limit:
        return True
    return now - state.built_at >= thresholds.max_age


@dataclass
class RunEvent:
    page_id: str
    from_status: PageStatus
    to_status: PageStatus


@dataclass
class RunResult:
    events: list[RunEvent] = field(default_factory=list)
    states: dict[str, PageState] = field(default_factory=dict)


def run_pages(
    pages: dict[str, Page],
    states: dict[str, PageState],
    changed_tags: dict[str, int],
    now: dt.datetime,
    rebuild: Callable[[Page], PageOutcome],
    thresholds: Thresholds = DEFAULT_THRESHOLDS,
) -> RunResult:
    """Ein Lauf über den Seitenbaum, Hierarchiestufe für Hierarchiestufe von unten nach oben.

    changed_tags: neue, geänderte oder aus dem Zeitfenster gefallene Geschäfte je Tag.
    rebuild(page) erzeugt die Zusammenfassung und meldet changed (Inhalts-Hash neu), unchanged
    oder failed. Nur changed gibt eine Änderung an die Eltern-Seite weiter. Ein Fehler setzt nur
    diese Seite auf failed; der Lauf geht mit den übrigen Seiten weiter. Kennzahlen und
    Linklisten entstehen unabhängig davon bei jedem Lauf.
    """
    result = RunResult(states={pid: replace(state) for pid, state in states.items()})
    current = result.states
    for tag_id, count in changed_tags.items():
        if tag_id in pages:
            current.setdefault(tag_id, PageState()).pending_changes += count

    def level(page: Page) -> int:
        return len(ancestors(pages, page.page_id))

    def move(page: Page, state: PageState, to_status: PageStatus) -> None:
        result.events.append(RunEvent(page.page_id, state.status, to_status))
        state.status = to_status

    for depth in sorted({level(page) for page in pages.values()}, reverse=True):
        for page in sorted(
            (p for p in pages.values() if level(p) == depth), key=lambda p: sort_key(p.page_id)
        ):
            state = current.setdefault(page.page_id, PageState())
            if not should_open(page, state, now, thresholds):
                continue
            if state.status != "open":
                move(page, state, "open")
            move(page, state, "pending")
            try:
                outcome = rebuild(page)
            except Exception as error:  # Modell- oder Datenfehler: nur diese Seite scheitert
                outcome, state.last_error = "failed", str(error)
            if outcome == "failed":
                move(page, state, "failed")
                state.pending_changes = 0
                continue
            move(page, state, "done")
            state.pending_changes, state.cited_label_removed = 0, False
            state.built_at, state.last_error = now, None
            if outcome == "changed" and page.parent_id is not None:
                current.setdefault(page.parent_id, PageState()).pending_changes += 1
    return result


def opened(result: RunResult) -> list[str]:
    return [event.page_id for event in result.events if event.to_status == "open"]


def page_ids(pages: Iterable[Page]) -> list[str]:
    return sorted((page.page_id for page in pages), key=sort_key)
