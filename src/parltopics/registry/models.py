"""Pydantic-Modell von registry/tags.yaml, ausgerichtet an SKOS (PRD 7.2, Anhang A, ADR 0007).

Zuordnung zu SKOS: pref_label = skos:prefLabel, alt_labels = skos:altLabel,
hidden_labels = skos:hiddenLabel, definition = skos:definition, broader = skos:broader,
related = skos:related, exact_match/close_match/broad_match = skos:exactMatch/closeMatch/broadMatch
(Curia-Vista-Sachbereiche). skos:narrower wird nicht gespeichert, sondern aus broader abgeleitet.
"""

from __future__ import annotations

import datetime as dt
import re
from collections import Counter
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Scheme = Literal["aps", "adhoc"]
Status = Literal["proposed", "active", "merged", "retired"]
ApsLevel = Literal["bereich", "kapitel", "thema"]

TAG_ID_PATTERN = re.compile(r"^(aps:\d+(?:\.\d+){0,2}|adhoc:[a-z0-9][a-z0-9.\-]*)$")
SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
MATCH_PATTERN = re.compile(r"^curia:[A-Za-z0-9.\-]+$")
VERSION_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}\.\d+$")


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LocalizedText(_Strict):
    """Ein Text je Sprache, Deutsch ist Pflicht (prefLabel, definition). Alle Sprachen hängen an
    derselben tag_id; Englisch dient der Suche und Schnittstellen (19.10.2026)."""

    de: str = Field(min_length=1)
    fr: str | None = None
    it: str | None = None
    rm: str | None = None
    en: str | None = None


class LocalizedLabels(_Strict):
    """Mehrere Bezeichnungen je Sprache (altLabel)."""

    de: list[str] = Field(default_factory=list)
    fr: list[str] = Field(default_factory=list)
    it: list[str] = Field(default_factory=list)
    rm: list[str] = Field(default_factory=list)
    en: list[str] = Field(default_factory=list)

    def all(self) -> list[str]:
        """Alle Bezeichnungen über alle Sprachen, sortiert und ohne Doppel."""
        return sorted(
            {label for labels in (self.de, self.fr, self.it, self.rm, self.en) for label in labels}
        )


class SchemeInfo(_Strict):
    label: str
    source: str
    fixed: bool


class Created(_Strict):
    at: dt.date
    by: str


class ProposalInfo(_Strict):
    by: str
    run: str | None = None
    recommendation: Literal["new", "duplicate_of", "child_of"]
    related_tag: str | None = None


def aps_parent(tag_id: str) -> str | None:
    """Eltern-Code im APS-Schema: aps:6.1.9 -> aps:6.1 -> aps:6 -> None."""
    code = tag_id.split(":", 1)[1]
    return f"aps:{code.rsplit('.', 1)[0]}" if "." in code else None


class Tag(_Strict):
    tag_id: str
    scheme: Scheme
    status: Status
    slug: str | None = None
    pref_label: LocalizedText
    alt_labels: LocalizedLabels = Field(default_factory=LocalizedLabels)
    hidden_labels: list[str] = Field(default_factory=list)
    definition: LocalizedText
    broader: list[str] = Field(default_factory=list)
    related: list[str] = Field(default_factory=list)
    exact_match: list[str] = Field(default_factory=list)
    close_match: list[str] = Field(default_factory=list)
    broad_match: list[str] = Field(default_factory=list)
    merged_into: str | None = None
    unreviewed_translations: list[Literal["fr", "it", "rm"]] = Field(default_factory=list)
    created: Created | None = None
    proposal: ProposalInfo | None = None

    @property
    def aps_level(self) -> ApsLevel | None:
        """Hierarchiestufe aus der ID: aps:6 Bereich, aps:6.1 Kapitel, aps:6.1.9 Thema."""
        if self.scheme != "aps":
            return None
        depth = self.tag_id.split(":", 1)[1].count(".")
        return ("bereich", "kapitel", "thema")[min(depth, 2)]

    @field_validator("tag_id")
    @classmethod
    def _tag_id_format(cls, value: str) -> str:
        if not TAG_ID_PATTERN.match(value):
            raise ValueError(
                f"tag_id {value!r}: APS als aps:<Bereich>[.<Kapitel>[.<Thema>]],"
                " Ad-hoc als adhoc:<kleinbuchstaben-ziffern>"
            )
        return value

    @field_validator("slug")
    @classmethod
    def _slug_format(cls, value: str | None) -> str | None:
        if value is not None and not SLUG_PATTERN.match(value):
            raise ValueError(
                f"slug {value!r} erlaubt nur Kleinbuchstaben, Ziffern und Bindestriche"
            )
        return value

    @field_validator("exact_match", "close_match", "broad_match")
    @classmethod
    def _match_format(cls, values: list[str]) -> list[str]:
        for value in values:
            if not MATCH_PATTERN.match(value):
                raise ValueError(f"Mapping {value!r} muss curia:<Sachbereich> sein")
        return values

    @model_validator(mode="after")
    def _consistent(self) -> Tag:
        tag_id = self.tag_id
        if tag_id.split(":", 1)[0] != self.scheme:
            raise ValueError(f"{tag_id}: Präfix passt nicht zum Schema {self.scheme!r}")
        if (self.status == "merged") != (self.merged_into is not None):
            raise ValueError(f"{tag_id}: status 'merged' und merged_into gehören zusammen")
        if tag_id in self.broader or tag_id in self.related or self.merged_into == tag_id:
            raise ValueError(f"{tag_id}: verweist auf sich selbst")
        for field in ("broader", "related"):
            values = getattr(self, field)
            if len(values) != len(set(values)):
                raise ValueError(f"{tag_id}: {field} enthält Doppel")
        overlap = sorted(set(self.broader) & set(self.related))
        if overlap:
            raise ValueError(
                f"{tag_id}: related und broader überschneiden sich: {', '.join(overlap)}"
            )
        targets = self.exact_match + self.close_match + self.broad_match
        if len(targets) != len(set(targets)):
            raise ValueError(f"{tag_id}: ein Curia-Sachbereich steht in mehr als einem Mapping")
        if self.scheme == "aps":
            if self.slug is None:
                raise ValueError(f"{tag_id}: APS-Tags brauchen einen festen slug (Dateiname)")
            parent = aps_parent(tag_id)
            expected = [parent] if parent else []
            if self.broader != expected:
                raise ValueError(f"{tag_id}: broader muss {expected} sein (Eltern-Code)")
        elif self.slug is not None:
            raise ValueError(f"{tag_id}: Ad-hoc-Tags haben keinen slug, die ID ist der Name")
        return self


class Registry(_Strict):
    registry_version: str
    schemes: dict[Scheme, SchemeInfo]
    tags: list[Tag] = Field(default_factory=list)

    @field_validator("registry_version")
    @classmethod
    def _version_format(cls, value: str) -> str:
        if not VERSION_PATTERN.match(value):
            raise ValueError(f"registry_version {value!r} muss JJJJ-MM-TT.N sein")
        return value

    @model_validator(mode="after")
    def _references(self) -> Registry:
        counts = Counter(tag.tag_id for tag in self.tags)
        duplicates = sorted(tag_id for tag_id, count in counts.items() if count > 1)
        if duplicates:
            raise ValueError(f"Doppelte tag_id: {', '.join(duplicates)}")
        by_id = {tag.tag_id: tag for tag in self.tags}
        for tag in self.tags:
            if tag.scheme not in self.schemes:
                raise ValueError(f"{tag.tag_id}: Schema {tag.scheme!r} fehlt unter schemes")
            targets = [("merged_into", tag.merged_into)] if tag.merged_into else []
            targets += [("broader", t) for t in tag.broader] + [("related", t) for t in tag.related]
            for field, target in targets:
                if target not in by_id:
                    raise ValueError(f"{tag.tag_id}: {field} verweist auf unbekanntes Tag {target}")
            lineage = self._ancestors(tag.tag_id, by_id)
            for target in tag.related:
                if target in lineage or tag.tag_id in self._ancestors(target, by_id):
                    raise ValueError(
                        f"{tag.tag_id}: related {target} liegt in der eigenen Hierarchie (broader)"
                    )
            if tag.scheme == "adhoc":
                for target in tag.broader:
                    if by_id[target].aps_level not in ("kapitel", "thema"):
                        raise ValueError(
                            f"{tag.tag_id}: broader {target} muss ein APS-Kapitel oder -Thema sein"
                        )
        return self

    @staticmethod
    def _ancestors(tag_id: str, by_id: dict[str, Tag]) -> set[str]:
        """Alle Vorfahren über broader, ohne Endlosschleife bei fehlerhaften Daten."""
        seen: set[str] = set()
        stack = list(by_id[tag_id].broader)
        while stack:
            current = stack.pop()
            if current in seen or current not in by_id:
                continue
            seen.add(current)
            stack.extend(by_id[current].broader)
        return seen

    def get(self, tag_id: str) -> Tag:
        for tag in self.tags:
            if tag.tag_id == tag_id:
                return tag
        raise KeyError(tag_id)

    def active(self, scheme: Scheme | None = None) -> list[Tag]:
        return [
            tag
            for tag in self.tags
            if tag.status == "active" and (scheme is None or tag.scheme == scheme)
        ]

    def narrower(self, tag_id: str) -> list[Tag]:
        """skos:narrower, abgeleitet: aktive Tags, die tag_id unter broader führen."""
        return [tag for tag in self.active() if tag_id in tag.broader]
