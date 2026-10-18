"""Ausgabeschemas der Klassifikation (PRD Anhang B, ARCHITEKTUR 3.4)."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Language = Literal["de", "fr", "it", "rm", "other"]

MAX_CHAPTERS = 3
MAX_TAGS = 5
MAX_PROPOSALS = 2
SUMMARY_MAX = 300
EVIDENCE_MAX = 300


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
    chapters: list[ChapterChoice]  # leer: kein APS-Kapitel passt (classify_chapters_v2)


def _shorten(text: str, limit: int) -> str:
    """Kürzt an einer Wortgrenze und markiert den Schnitt mit …"""
    return text if len(text) <= limit else text[: limit - 1].rsplit(" ", 1)[0] + "…"


class TagAssignment(_Output):
    tag_id: str
    confidence: float = Field(ge=0, le=1)
    evidence: str = Field(min_length=1)

    @field_validator("evidence")
    @classmethod
    def _evidence(cls, value: str) -> str:
        """Ein zu langes Zitat wird gekürzt, nicht verworfen; das Tag bleibt (wie summary_de)."""
        return _shorten(value, EVIDENCE_MAX)


class TagProposal(_Output):
    name_de: str = Field(min_length=1, max_length=120)
    description_de: str = Field(min_length=1, max_length=1000)
    reason: str = Field(min_length=1, max_length=500)


class Stage2Output(_Output):
    affair_id: int
    language: Language
    summary_de: str | None = None
    tags: list[TagAssignment] = Field(default_factory=list)
    proposed_tags: list[TagProposal] = Field(default_factory=list)

    @field_validator("summary_de", mode="before")
    @classmethod
    def _summary(cls, value: object) -> str | None:
        """Kurzzusammenfassung für die Tag-Seiten. Fehlt sie oder ist sie zu lang, bleiben die
        Tags trotzdem gültig: leer wird None, zu lang wird gekürzt (PRD 7.3, Anhang B)."""
        if not isinstance(value, str):
            return None
        text = " ".join(value.split())
        return _shorten(text, SUMMARY_MAX) if text else None


def _by_confidence(items: list, limit: int) -> list:
    return sorted(items, key=lambda item: item.confidence, reverse=True)[:limit]


def _offered_id(tag_id: str, offered: set[str]) -> str:
    """Modelle lassen das Präfix manchmal weg ("7.2" statt "aps:7.2"); eindeutig, also ergänzen."""
    prefixed = f"aps:{tag_id}"
    return prefixed if tag_id not in offered and prefixed in offered else tag_id


def parse_stage1(data: dict, *, affair_id: int, offered: set[str]) -> Stage1Output:
    """Stufe 1 prüfen: richtiges Geschäft, nur angebotene Kapitel, höchstens 3."""
    output = Stage1Output.model_validate(data)
    if output.affair_id != affair_id:
        raise OutputError(f"Antwort für Geschäft {output.affair_id}, angefragt war {affair_id}")
    chapters = [
        c.model_copy(update={"chapter_id": _offered_id(c.chapter_id, offered)})
        for c in output.chapters
    ]
    unknown = sorted({c.chapter_id for c in chapters} - offered)
    if unknown:
        raise OutputError(f"Kapitel nicht angeboten: {', '.join(unknown)}")
    return output.model_copy(update={"chapters": _by_confidence(chapters, MAX_CHAPTERS)})


def parse_stage2(
    data: dict, *, affair_id: int, offered: set[str]
) -> tuple[Stage2Output, list[str]]:
    """Stufe 2 prüfen. Gibt die bereinigte Ausgabe und die verworfenen Tag-IDs zurück.

    Nicht angebotene Tags werden verworfen; ein mehrfach genanntes Tag zählt einmal, mit seiner
    höchsten Konfidenz; behalten werden die 5 Tags mit der höchsten Konfidenz und die ersten 2
    Vorschläge.
    """
    output = Stage2Output.model_validate(data)
    if output.affair_id != affair_id:
        raise OutputError(f"Antwort für Geschäft {output.affair_id}, angefragt war {affair_id}")
    tags = [t.model_copy(update={"tag_id": _offered_id(t.tag_id, offered)}) for t in output.tags]
    unique: dict[str, TagAssignment] = {}
    for tag in _by_confidence(tags, len(tags)):
        if tag.tag_id in offered:
            unique.setdefault(tag.tag_id, tag)
    best = list(unique.values())[:MAX_TAGS]
    kept = {tag.tag_id for tag in best}
    dropped = [tag.tag_id for tag in tags if tag.tag_id not in kept]
    cleaned = output.model_copy(
        update={"tags": best, "proposed_tags": output.proposed_tags[:MAX_PROPOSALS]}
    )
    return cleaned, dropped
