"""Navigationssuche durch den Seitenbaum ohne Embeddings (PRD 7.10, ADR 0008).

Der Code steuert die Schleife; das Modell bewertet je Knoten alle Kinder in einem Aufruf und wählt
am Blatt die passenden Geschäfte. Grenzen, Rückweg und Volltext-Fallback liegen im Code.
Modell- und Datenbankzugriffe werden als Funktionen übergeben (M4 verbindet sie mit LLM und DB).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from parltopics.wiki.schemas import Statement

HEART_ID = "heart"
FALLBACK = "volltext"


class NavigationError(ValueError):
    """Die Modellausgabe passt nicht zu den angebotenen Seiten oder Geschäften."""


class _Output(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Filters(_Output):
    year_from: int | None = Field(None, ge=1990, le=2100)
    year_to: int | None = Field(None, ge=1990, le=2100)
    body_keys: list[str] = Field(default_factory=list)
    levels: list[Literal["bund", "kanton", "gemeinde"]] = Field(default_factory=list)
    affair_type: str | None = None


class ChildScore(_Output):
    page_id: str
    relevance: float = Field(ge=0, le=1)


class NavigationStep(_Output):
    scores: list[ChildScore] = Field(min_length=1)
    filters: Filters | None = None


class LeafAnswer(_Output):
    """Antwort am Blatt oder nach dem Fallback (navigate_answer_v1): Auswahl und Aussagen."""

    selected_ids: list[int] = Field(default_factory=list)
    statements: list[Statement] = Field(default_factory=list)


@dataclass(frozen=True)
class Limits:
    max_steps: int = 8  # Modellaufrufe je Suche, der Fallback eingeschlossen
    min_relevance: float = 0.3
    max_branches: int = 2
    max_candidates: int = 20


DEFAULT_LIMITS = Limits()


@dataclass
class Visit:
    page_id: str
    kind: Literal["knoten", "blatt", "volltext"]
    ranked: list[str] = field(default_factory=list)
    chosen: list[int] = field(default_factory=list)


@dataclass
class NavigationResult:
    affair_ids: list[int]
    path: list[str]
    visits: list[Visit]
    steps: int
    fallback_used: bool
    filters: Filters | None
    status: Literal["ok", "no_results", "limit_reached"]
    statements: list[Statement] = field(default_factory=list)


def parse_step(data: dict, offered: set[str]) -> NavigationStep:
    """Bewertung prüfen. Unbekannte Seiten gelten als erfunden und fallen weg; wird eine Seite
    mehrfach bewertet, zählt ihre höchste Relevanz."""
    step = NavigationStep.model_validate(data)
    best: dict[str, ChildScore] = {}
    for score in step.scores:
        known = best.get(score.page_id)
        if score.page_id in offered and (known is None or score.relevance > known.relevance):
            best[score.page_id] = score
    if not best:
        raise NavigationError("Keine bewertete Seite stammt aus der angebotenen Liste")
    return step.model_copy(update={"scores": list(best.values())})


def parse_selection(selected: list[int], offered: list[int]) -> list[int]:
    """Gewählte Geschäfte am Blatt: nur angebotene IDs, Reihenfolge der Auswahl bleibt."""
    allowed = set(offered)
    return [affair_id for affair_id in dict.fromkeys(selected) if affair_id in allowed]


def parse_answer(data: dict, offered: list[int]) -> LeafAnswer:
    """Antwort am Blatt prüfen: nur angebotene Geschäfte, jede Aussage nennt gewählte Geschäfte.

    Ohne Auswahl bleibt keine Aussage übrig, es gibt also keine Antwort ohne Treffer.
    """
    answer = LeafAnswer.model_validate(data)
    selected = parse_selection(answer.selected_ids, offered)
    chosen = set(selected)
    statements = [
        statement
        for statement in answer.statements
        if statement.affair_ids and set(statement.affair_ids) <= chosen and not statement.page_ids
    ]
    return LeafAnswer(selected_ids=selected, statements=statements if selected else [])


def _ranked(step: NavigationStep, kids: list[str], limits: Limits) -> list[str]:
    """Kinder nach Relevanz; doppelt bewertete Kinder zählen einmal, mit der höchsten Relevanz."""
    relevance: dict[str, float] = {}
    for score in step.scores:
        if score.page_id in kids:
            relevance[score.page_id] = max(score.relevance, relevance.get(score.page_id, 0.0))
    ordered = sorted(relevance.items(), key=lambda item: item[1], reverse=True)
    passing = [page_id for page_id, value in ordered if value >= limits.min_relevance]
    return passing[: limits.max_branches]


def navigate(
    query: str,
    *,
    children: Callable[[str], list[str]],
    score: Callable[[str, str, list[str], bool], NavigationStep],
    leaf_candidates: Callable[[str, Filters | None], list[int]],
    select: Callable[[str, str, list[int]], dict],
    fulltext: Callable[[str, Filters | None], list[int]],
    limits: Limits = DEFAULT_LIMITS,
) -> NavigationResult:
    """Suche von Heart abwärts mit Rückweg, Schrittgrenze und Volltext-Fallback.

    Jeder Modellaufruf ist ein Schritt. Der Baum nutzt höchstens limits.max_steps - 1 Schritte,
    der letzte bleibt für den Fallback, eine Suche macht also nie mehr als limits.max_steps
    Aufrufe. Ein Ast liefert nichts, wenn kein Kind die Mindestrelevanz erreicht oder am Blatt kein
    Geschäft gewählt wird; dann geht die Suche zum nächstbesten Geschwister zurück. Ohne Treffer im
    Baum greift die Volltextsuche. select liefert die rohe Modellausgabe, parse_answer prüft sie.
    """
    steps, visits = 0, []
    filters: Filters | None = None
    parent: dict[str, str] = {}
    frontier = [HEART_ID]
    hit_limit = False
    while frontier:
        if steps >= limits.max_steps - 1:
            hit_limit = True
            break
        page_id = frontier.pop()
        kids = children(page_id)
        if not kids:
            candidates = leaf_candidates(page_id, filters)[: limits.max_candidates]
            if not candidates:
                visits.append(Visit(page_id, "blatt"))
                continue
            steps += 1
            answer = parse_answer(select(query, page_id, candidates), candidates)
            visits.append(Visit(page_id, "blatt", chosen=answer.selected_ids))
            if answer.selected_ids:
                path = [page_id]
                while path[-1] in parent:
                    path.append(parent[path[-1]])
                path.reverse()
                return NavigationResult(
                    answer.selected_ids,
                    path,
                    visits,
                    steps,
                    False,
                    filters,
                    "ok",
                    answer.statements,
                )
            continue
        steps += 1
        step = score(query, page_id, kids, filters is None and page_id == HEART_ID)
        if page_id == HEART_ID and step.filters is not None:
            filters = step.filters
        ranked = _ranked(step, kids, limits)
        visits.append(Visit(page_id, "knoten", ranked=ranked))
        for child_id in ranked:
            parent[child_id] = page_id
        frontier.extend(reversed(ranked))
    candidates = fulltext(query, filters)[: limits.max_candidates]
    answer = LeafAnswer()
    if candidates:
        steps += 1
        answer = parse_answer(select(query, FALLBACK, candidates), candidates)
    visits.append(Visit(FALLBACK, "volltext", chosen=answer.selected_ids))
    status = "ok" if answer.selected_ids else ("limit_reached" if hit_limit else "no_results")
    return NavigationResult(
        answer.selected_ids, [FALLBACK], visits, steps, True, filters, status, answer.statements
    )
