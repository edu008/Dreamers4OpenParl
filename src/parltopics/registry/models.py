"""Pydantic-Modell von registry/tags.yaml (PRD 7.2, Anhang A)."""

from __future__ import annotations

import datetime as dt
import re
from collections import Counter
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Scheme = Literal["aps", "adhoc"]
Status = Literal["proposed", "active", "merged", "retired"]

TAG_ID_PATTERN = re.compile(r"^(aps|adhoc):[a-z0-9][a-z0-9.\-]*$")
VERSION_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}\.\d+$")


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LocalizedText(_Strict):
    de: str = Field(min_length=1)
    fr: str | None = None
    it: str | None = None
    rm: str | None = None


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


class Tag(_Strict):
    tag_id: str
    scheme: Scheme
    status: Status
    names: LocalizedText
    descriptions: LocalizedText
    aliases: list[str] = Field(default_factory=list)
    parent: str | None = None
    merged_into: str | None = None
    unreviewed_translations: list[Literal["fr", "it", "rm"]] = Field(default_factory=list)
    created: Created | None = None
    proposal: ProposalInfo | None = None

    @property
    def aps_level(self) -> Literal["bereich", "kapitel", "thema"] | None:
        """Ebene im APS-Schema aus der ID: aps:6 Bereich, aps:6.1 Kapitel, aps:6.1.9 Thema."""
        if self.scheme != "aps":
            return None
        depth = self.tag_id.split(":", 1)[1].count(".")
        return ("bereich", "kapitel", "thema")[min(depth, 2)]

    @field_validator("tag_id")
    @classmethod
    def _tag_id_format(cls, value: str) -> str:
        if not TAG_ID_PATTERN.match(value):
            raise ValueError(f"tag_id {value!r} passt nicht zu <schema>:<kleinbuchstaben-ziffern>")
        return value

    @model_validator(mode="after")
    def _consistent(self) -> Tag:
        if self.tag_id.split(":", 1)[0] != self.scheme:
            raise ValueError(f"{self.tag_id}: Präfix passt nicht zum Schema {self.scheme!r}")
        if (self.status == "merged") != (self.merged_into is not None):
            raise ValueError(f"{self.tag_id}: status 'merged' und merged_into gehören zusammen")
        if self.parent == self.tag_id or self.merged_into == self.tag_id:
            raise ValueError(f"{self.tag_id}: verweist auf sich selbst")
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
        for tag in self.tags:
            if tag.scheme not in self.schemes:
                raise ValueError(f"{tag.tag_id}: Schema {tag.scheme!r} fehlt unter schemes")
            for field, target in (("parent", tag.parent), ("merged_into", tag.merged_into)):
                if target is not None and target not in counts:
                    raise ValueError(f"{tag.tag_id}: {field} verweist auf unbekanntes Tag {target}")
        return self

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
