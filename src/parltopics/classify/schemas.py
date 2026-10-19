"""Ausgabeschemas der Klassifikation (PRD Anhang B, ARCHITEKTUR 3.4)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Language = Literal["de", "fr", "it", "rm", "other"]
Fit = Literal["kern_explizit", "nebenaspekt_explizit", "implizit_abgeleitet", "unsicher"]

FIT_MAX: dict[str, float] = {
    "kern_explizit": 0.90,
    "nebenaspekt_explizit": 0.75,
    "implizit_abgeleitet": 0.55,
    "unsicher": 0.35,
}

FIT_ALIASES: dict[str, str] = {
    "kernthema": "kern_explizit",
    "kern": "kern_explizit",
    "exact": "kern_explizit",
    "nebenaspekt": "nebenaspekt_explizit",
    "neben": "nebenaspekt_explizit",
    "partial": "nebenaspekt_explizit",
    "abgeleitet": "implizit_abgeleitet",
    "nur_abgeleitet": "implizit_abgeleitet",
    "implizit": "implizit_abgeleitet",
    "implicit": "implizit_abgeleitet",
    "weak": "unsicher",
}

# Akteurs- und Institutionen-Themen (Kapitel aps:1.2), die in fast jedem Vorstoss als Adressat
# vorkommen ("Der Bundesrat wird beauftragt...") und Sachthemen nicht verdrängen dürfen.
ACTOR_TAGS: frozenset[str] = frozenset(
    {
        "aps:1.2.1",  # Bundesrat / Regierungsrat / Gemeinderat
        "aps:1.2.2",  # Verwaltung
        "aps:1.2.3",  # Konkordanz
        "aps:1.2.4",  # Parlament
        "aps:1.2.5",  # Lobbyismus
        "aps:1.2.6",  # Judikative
        "aps:1.2.7",  # Föderalismus
        "aps:1.2.8",  # Kantone
        "aps:1.2.9",  # Städte, Regionen, Gemeinden
        "aps:1.2.10",  # Parteiensystem
        "aps:1.2.11",  # Parteien
        "aps:1.2.12",  # Verbände
    }
)

MAX_CHAPTERS = 3
MAX_TAGS = 3  # höchstens 3 Themen je Geschäft (Entscheid 19.10.2026)
MAX_INSTITUTION_TAGS = 1
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
    chapters: list[ChapterChoice]  # leer: kein APS-Kapitel passt (classify_chapters_v2/v3)


def _shorten(text: str, limit: int) -> str:
    """Kürzt an einer Wortgrenze und markiert den Schnitt mit …"""
    return text if len(text) <= limit else text[: limit - 1].rsplit(" ", 1)[0] + "…"


class TagAssignment(_Output):
    evidence: str = Field(min_length=1)
    fit: Fit | None = None
    tag_id: str
    confidence: float = Field(ge=0, le=1)

    @field_validator("fit", mode="before")
    @classmethod
    def _fit(cls, value: object) -> object:
        if isinstance(value, str):
            v = value.strip().lower()
            return FIT_ALIASES.get(v, v)
        return value

    @field_validator("evidence")
    @classmethod
    def _evidence(cls, value: str) -> str:
        """Ein zu langes Zitat wird gekürzt, nicht verworfen; das Tag bleibt (wie summary_de)."""
        return _shorten(value, EVIDENCE_MAX)

    @model_validator(mode="before")
    @classmethod
    def _calibrate(cls, data: Any) -> Any:
        """Leitet die Konfidenz aus der Kategorie (fit) ab oder deckelt sie daran."""
        if isinstance(data, dict):
            fit = data.get("fit")
            if isinstance(fit, str):
                fit = FIT_ALIASES.get(fit.strip().lower(), fit.strip().lower())
                data = {**data, "fit": fit}
            conf = data.get("confidence")
            if fit in FIT_MAX and (
                conf is None or (isinstance(conf, (int, float)) and conf > FIT_MAX[fit])
            ):
                data = {**data, "confidence": FIT_MAX[fit]}
        return data


class TagProposal(_Output):
    name_de: str = Field(min_length=1, max_length=120)
    description_de: str = Field(min_length=1, max_length=1000)
    reason: str = Field(min_length=1, max_length=500)


class Stage2Output(_Output):
    affair_id: int
    language: Language
    summary_de: str | None = None
    tags: list[TagAssignment] = Field(default_factory=list)
    institution_tags: list[TagAssignment] = Field(default_factory=list)
    proposed_tags: list[TagProposal] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _normalize_keys(cls, data: Any) -> Any:
        if isinstance(data, dict):
            out = dict(data)
            if "sachthemen" in out and "tags" not in out:
                out["tags"] = out.pop("sachthemen")
            elif "sachthemen" in out:
                out.pop("sachthemen")
            for alias in ("institutions", "institution_verfahren", "actors"):
                if alias in out:
                    val = out.pop(alias)
                    if "institution_tags" not in out:
                        out["institution_tags"] = val
            return out
        return data

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
    data: dict, *, affair_id: int, offered: set[str], max_tags: int = MAX_TAGS
) -> tuple[Stage2Output, list[str]]:
    """Stufe 2 prüfen. Gibt die bereinigte Ausgabe und die verworfenen Tag-IDs zurück.

    Trennt Sachthemen (tags) und Institution/Verfahren (institution_tags):
    - Sind echte Sachthemen in tags vorhanden, verdrängen Akteurs-Tags (aps:1.2.*) in tags
      niemals ein Sachthema, sondern werden ausgefiltert.
    - Explizit in institution_tags gesetzte Institutionen (max. 1) werden übernommen, sofern
      Platz bis max_tags besteht (oder falls keine Sachthemen vorliegen).
    """
    output = Stage2Output.model_validate(data)
    if output.affair_id != affair_id:
        raise OutputError(f"Antwort für Geschäft {output.affair_id}, angefragt war {affair_id}")
    raw_tags = [
        t.model_copy(update={"tag_id": _offered_id(t.tag_id, offered)}) for t in output.tags
    ]
    raw_inst = [
        t.model_copy(update={"tag_id": _offered_id(t.tag_id, offered)})
        for t in output.institution_tags
    ]
    all_raw = raw_tags + raw_inst

    has_sachthema = any(t.tag_id in offered and t.tag_id not in ACTOR_TAGS for t in raw_tags)
    filtered_tags = (
        [t for t in raw_tags if t.tag_id not in ACTOR_TAGS] if has_sachthema else raw_tags
    )

    unique: dict[str, TagAssignment] = {}
    for tag in _by_confidence(filtered_tags, len(filtered_tags)):
        if tag.tag_id in offered:
            unique.setdefault(tag.tag_id, tag)

    # Optionales Institutionen-/Verfahrens-Tag anhängen (höchstens 1), falls explizit angegeben.
    inst_added = 0
    for tag in _by_confidence(raw_inst, len(raw_inst)):
        if tag.tag_id in offered and tag.tag_id not in unique:
            unique[tag.tag_id] = tag
            inst_added += 1
            if inst_added >= MAX_INSTITUTION_TAGS:
                break

    best = list(unique.values())[:max_tags]
    kept = {tag.tag_id for tag in best}
    dropped = [tag.tag_id for tag in all_raw if tag.tag_id not in kept]
    cleaned = output.model_copy(
        update={
            "tags": best,
            "institution_tags": [],
            "proposed_tags": output.proposed_tags[:MAX_PROPOSALS],
        }
    )
    return cleaned, dropped
