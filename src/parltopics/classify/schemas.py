"""Ausgabeschemas der Klassifikation (PRD Anhang B, ARCHITEKTUR 3.4)."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Language = Literal["de", "fr", "it", "rm", "other"]

MAX_CHAPTERS = 3
MAX_TAGS = 5
MAX_PROPOSALS = 2


class OutputError(ValueError):
    """Die Modellausgabe ist formal gültig, passt aber nicht zur Anfrage."""


class _Output(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ChapterChoice(_Output):
    chapter_id: str
    confidence: float = Field(ge=0, le=1)


class Stage1Output(_Output):
    affair_id: int
    language: Language
    chapters: list[ChapterChoice] = Field(min_length=1)


class TagAssignment(_Output):
    tag_id: str
    confidence: float = Field(ge=0, le=1)
    evidence: str = Field(min_length=1, max_length=300)


class TagProposal(_Output):
    name_de: str = Field(min_length=1, max_length=120)
    description_de: str = Field(min_length=1, max_length=1000)
    reason: str = Field(min_length=1, max_length=500)


class Stage2Output(_Output):
    affair_id: int
    language: Language
    summary_de: str = Field(min_length=1, max_length=300)
    tags: list[TagAssignment] = Field(default_factory=list)
    proposed_tags: list[TagProposal] = Field(default_factory=list)


def _by_confidence(items: list, limit: int) -> list:
    return sorted(items, key=lambda item: item.confidence, reverse=True)[:limit]


def parse_stage1(data: dict, *, affair_id: int, offered: set[str]) -> Stage1Output:
    """Stufe 1 prüfen: richtiges Geschäft, nur angebotene Kapitel, höchstens 3."""
    output = Stage1Output.model_validate(data)
    if output.affair_id != affair_id:
        raise OutputError(f"Antwort für Geschäft {output.affair_id}, angefragt war {affair_id}")
    unknown = sorted({c.chapter_id for c in output.chapters} - offered)
    if unknown:
        raise OutputError(f"Kapitel nicht angeboten: {', '.join(unknown)}")
    return output.model_copy(update={"chapters": _by_confidence(output.chapters, MAX_CHAPTERS)})


def parse_stage2(
    data: dict, *, affair_id: int, offered: set[str]
) -> tuple[Stage2Output, list[str]]:
    """Stufe 2 prüfen. Gibt die bereinigte Ausgabe und die verworfenen Tag-IDs zurück.

    Nicht angebotene Tags werden verworfen; behalten werden die 5 Tags mit der höchsten
    Konfidenz und die ersten 2 Vorschläge.
    """
    output = Stage2Output.model_validate(data)
    if output.affair_id != affair_id:
        raise OutputError(f"Antwort für Geschäft {output.affair_id}, angefragt war {affair_id}")
    kept = [tag for tag in output.tags if tag.tag_id in offered]
    dropped = [tag.tag_id for tag in output.tags if tag.tag_id not in offered]
    best = _by_confidence(kept, MAX_TAGS)
    dropped += [tag.tag_id for tag in kept if tag not in best]
    cleaned = output.model_copy(
        update={"tags": best, "proposed_tags": output.proposed_tags[:MAX_PROPOSALS]}
    )
    return cleaned, dropped
