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


@dataclass(frozen=True)
class Limits:
    max_steps: int = 8
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


def parse_step(data: dict, offered: set[str]) -> NavigationStep:
    """Bewertung prüfen; unbekannte Seiten-IDs gelten als erfunden und werden verworfen."""
    step = NavigationStep.model_validate(data)
    known = [score for score in step.scores if score.page_id in offered]
    if not known:
        raise NavigationError("Keine bewertete Seite stammt aus der angebotenen Liste")
    return step.model_copy(update={"scores": known})


def parse_selection(selected: list[int], offered: list[int]) -> list[int]:
    """Gewählte Geschäfte am Blatt: nur angebotene IDs, Reihenfolge der Auswahl bleibt."""
    allowed = set(offered)
    return [affair_id for affair_id in dict.fromkeys(selected) if affair_id in allowed]


def navigate(
    query: str,
    *,
    children: Callable[[str], list[str]],
    score: Callable[[str, str, list[str], bool], NavigationStep],
    leaf_candidates: Callable[[str, Filters | None], list[int]],
    select: Callable[[str, str, list[int]], list[int]],
    fulltext: Callable[[str, Filters | None], list[int]],
    limits: Limits = DEFAULT_LIMITS,
) -> NavigationResult:
    """Suche von Heart abwärts mit Rückweg, Schrittgrenze und Volltext-Fallback.

    Jeder Modellaufruf ist ein Schritt. Ein Ast liefert nichts, wenn kein Kind die Mindestrelevanz
    erreicht oder am Blatt kein Geschäft gewählt wird; dann geht die Suche zum nächstbesten
    Geschwister zurück. Ohne Treffer im Baum greift die Volltextsuche.
    """
    steps, visits = 0, []
    filters: Filters | None = None
    parent: dict[str, str] = {}
    frontier = [HEART_ID]
    hit_limit = False
    while frontier:
        if steps >= limits.max_steps:
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
            chosen = parse_selection(select(query, page_id, candidates), candidates)
            visits.append(Visit(page_id, "blatt", chosen=chosen))
            if chosen:
                path = [page_id]
                while path[-1] in parent:
                    path.append(parent[path[-1]])
                path.reverse()
                return NavigationResult(chosen, path, visits, steps, False, filters, "ok")
            continue
        steps += 1
        step = score(query, page_id, kids, filters is None and page_id == HEART_ID)
        if page_id == HEART_ID and step.filters is not None:
            filters = step.filters
        ranked = [
            s.page_id
            for s in sorted(step.scores, key=lambda s: s.relevance, reverse=True)
            if s.relevance >= limits.min_relevance and s.page_id in kids
        ][: limits.max_branches]
        visits.append(Visit(page_id, "knoten", ranked=ranked))
        for child_id in ranked:
            parent[child_id] = page_id
        frontier.extend(reversed(ranked))
    candidates = fulltext(query, filters)[: limits.max_candidates]
    chosen = parse_selection(select(query, FALLBACK, candidates), candidates) if candidates else []
    visits.append(Visit(FALLBACK, "volltext", chosen=chosen))
    status = "ok" if chosen else ("limit_reached" if hit_limit else "no_results")
    return NavigationResult(
        chosen, [FALLBACK], visits, steps + bool(candidates), True, filters, status
    )
