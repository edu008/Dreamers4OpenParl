"""Ausgabeschemas der Klassifikation (PRD Anhang B, ARCHITEKTUR 3.4)."""

from collections.abc import Mapping
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from parltopics.registry.aps_import import aps_slug

Language = Literal["de", "fr", "it", "rm", "other"]

MAX_CHAPTERS = 3
MAX_TAGS = 3  # höchstens 3 Themen je Geschäft (Entscheid 19.10.2026)
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
    # Vorschlag A (classify_single_v2): Institution oder Verfahren, nur wenn das Geschäft sie regelt
    institution_tags: list[TagAssignment] = Field(default_factory=list)
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


def short_key(value: str) -> str:
    """Kurzname in fester Schreibweise: Gross- und Kleinschreibung, Umlaute, Leer- und
    Satzzeichen zählen nicht ("Ärzte und Pflegepersonal" = "aerzte-pflegepersonal")."""
    prefix = "adhoc:" if value.startswith("adhoc:") else ""
    return prefix + aps_slug(value.removeprefix("adhoc:").removeprefix("aps:"))


def _offered_id(tag_id: str, offered: set[str] | Mapping[str, str]) -> str:
    """Angebotene tag_id zur Angabe des Modells.

    Mit Kurznamen (Mapping short_key → tag_id, classify_single_v2) zählt nur ein Schlüssel des
    Mappings (Kurzname, eindeutiger Name oder Synonym), auch ohne das Präfix adhoc:; alles andere,
    auch ein Zahlencode, bleibt unbekannt und mit ? markiert.
    Sonst: Modelle lassen das Präfix manchmal weg ("7.2" statt "aps:7.2"); eindeutig, also ergänzen.
    """
    if isinstance(offered, Mapping):
        key = short_key(tag_id)
        return offered.get(key) or offered.get(f"adhoc:{key}") or f"?{tag_id}"
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
    data: dict, *, affair_id: int, offered: set[str] | Mapping[str, str]
) -> tuple[Stage2Output, list[str]]:
    """Stufe 2 prüfen. Gibt die bereinigte Ausgabe und die verworfenen Tag-IDs zurück.

    offered: angebotene tag_ids oder, bei Kurznamen im Prompt, short_key → tag_id. Nicht
    angebotene Tags werden verworfen; ein mehrfach genanntes Tag zählt einmal, mit seiner
    höchsten Konfidenz; behalten werden die 3 Tags mit der höchsten Konfidenz und die ersten 2
    Vorschläge.
    """
    output = Stage2Output.model_validate(data)
    if output.affair_id != affair_id:
        raise OutputError(f"Antwort für Geschäft {output.affair_id}, angefragt war {affair_id}")
    ids = set(offered.values()) if isinstance(offered, Mapping) else offered
    tags = [t.model_copy(update={"tag_id": _offered_id(t.tag_id, offered)}) for t in output.tags]
    unique: dict[str, TagAssignment] = {}
    for tag in _by_confidence(tags, len(tags)):
        if tag.tag_id in ids:
            unique.setdefault(tag.tag_id, tag)
    best = list(unique.values())[:MAX_TAGS]
    kept = {tag.tag_id for tag in best}
    dropped = [tag.tag_id for tag in tags if tag.tag_id not in kept]
    cleaned = output.model_copy(
        update={"tags": best, "proposed_tags": output.proposed_tags[:MAX_PROPOSALS]}
    )
    return cleaned, dropped


MAX_INSTITUTIONS = 1


# classify_single_v3: Passung statt selbst genannter Zahl. Die Zahl hielt sich an die Anker im
# Prompt (0.9, 0.7, 0.5) und trennte richtige nicht von falschen Labels (Lauf 7).
FIT = {"kern": 0.9, "neben": 0.6}


def _with_fit(tags: object) -> object:
    """fit → confidence; ein unbekannter fit bleibt stehen und scheitert an der Validierung."""
    if not isinstance(tags, list):
        return tags
    return [
        {**{k: v for k, v in t.items() if k != "fit"}, "confidence": FIT[t["fit"]]}
        if isinstance(t, dict) and t.get("fit") in FIT
        else t
        for t in tags
    ]


def parse_single(
    data: dict,
    *,
    affair_id: int,
    topics: set[str],
    institutions: set[str],
    keys: Mapping[str, str] | None = None,
) -> tuple[Stage2Output, list[str]]:
    """Einstufig mit getrennten Listen (Vorschlag A, 19.10.2026).

    Sachthemen kommen zuerst, ein Institutions-Thema (Parlament, Verwaltung, Bundesrat …) höchstens
    einmal und nur dahinter; insgesamt höchstens 3. Steht ein Institutions-Thema in `tags`, wird es
    als Institution behandelt: Wer ein Geschäft einreicht oder behandelt, ist nicht sein Thema.
    keys: Kurzname → tag_id (classify_single_v2 und v3); ein Kapitelname bleibt unbekannt.
    """
    if isinstance(data, dict):
        lists = ("tags", "institution_tags")
        data = {k: _with_fit(v) if k in lists else v for k, v in data.items()}
    output = Stage2Output.model_validate(data)
    if output.affair_id != affair_id:
        raise OutputError(f"Antwort für Geschäft {output.affair_id}, angefragt war {affair_id}")
    offered = keys if keys else topics | institutions
    given = [
        t.model_copy(update={"tag_id": _offered_id(t.tag_id, offered)})
        for t in [*output.tags, *output.institution_tags]
    ]

    def best(ids: set[str], limit: int) -> list[TagAssignment]:
        unique: dict[str, TagAssignment] = {}
        for tag in _by_confidence([t for t in given if t.tag_id in ids], len(given)):
            unique.setdefault(tag.tag_id, tag)
        return list(unique.values())[:limit]

    kept = [*best(topics, MAX_TAGS), *best(institutions, MAX_INSTITUTIONS)][:MAX_TAGS]
    kept_ids = {tag.tag_id for tag in kept}
    dropped = [tag.tag_id for tag in given if tag.tag_id not in kept_ids]
    cleaned = output.model_copy(
        update={
            "tags": kept,
            "institution_tags": [],
            "proposed_tags": output.proposed_tags[:MAX_PROPOSALS],
        }
    )
    return cleaned, dropped


def single_format(
    affair_id: int, topics: list[str], institutions: list[str], *, min_tags: int = 0
) -> dict:
    """response_format für classify_single_v3: das JSON-Format erzwingen, Beleg vor dem Thema.

    Leere Listen lassen tag_id frei; parse_single verwirft unbekannte Namen. Ein enum über alle
    Kurznamen brachte keinen Gewinn (Lauf 13–15 mit, 16–18 ohne: gleiche Treffer), zwingt aber
    einen erfundenen Namen in ein gültiges Thema mit gleichem Anfang, statt ihn zu verwerfen.
    Mit enum nur für kleine Listen, etwa die Themen eines Kapitels bei der Nachfrage.
    """

    def assignment(ids: list[str]) -> dict:
        return {
            "type": "object",
            "additionalProperties": False,
            "required": ["evidence", "tag_id", "fit"],
            "properties": {
                "evidence": {"type": "string"},
                "tag_id": {"type": "string", "enum": list(dict.fromkeys(ids))}
                if ids
                else {"type": "string"},
                "fit": {"type": "string", "enum": list(FIT)},
            },
        }

    text = {"type": "string"}
    proposal = {
        "type": "object",
        "additionalProperties": False,
        "required": ["name_de", "description_de", "reason"],
        "properties": {"name_de": text, "description_de": text, "reason": text},
    }
    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "affair_id",
            "language",
            "summary_de",
            "tags",
            "institution_tags",
            "proposed_tags",
        ],
        "properties": {
            "affair_id": {"type": "integer", "enum": [affair_id]},
            "language": {"type": "string", "enum": ["de", "fr", "it", "rm", "other"]},
            "summary_de": text,
            "tags": {
                "type": "array",
                "items": assignment(topics),
                "minItems": min_tags,
                "maxItems": MAX_TAGS,
            },
            "institution_tags": {
                "type": "array",
                "items": assignment(institutions),
                "maxItems": MAX_INSTITUTIONS,
            },
            "proposed_tags": {"type": "array", "items": proposal, "maxItems": MAX_PROPOSALS},
        },
    }
    spec = {"name": "classify", "strict": True, "schema": schema}
    return {"type": "json_schema", "json_schema": spec}
