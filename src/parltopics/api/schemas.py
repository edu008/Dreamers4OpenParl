"""Antwortmodelle der Sidecar-API (PRD F10); sie bestimmen das Schema unter /v1/openapi.json."""

from datetime import date, datetime
from typing import Annotated, Literal, Self

from pydantic import BaseModel, Field, StringConstraints, model_validator

from parltopics.wiki.tree import PageKind

Stage = Literal["8b", "70b", "human"]
Lang = Literal["de", "fr", "it", "rm"]
Reason = Literal["low_confidence", "no_evidence", "evidence_unverified", "sample"]
LEVEL = "country, canton, city oder municipality"


class PageOut(BaseModel):
    page_id: str = Field(examples=["aps:6.1.9"])
    kind: PageKind
    title: str = Field(examples=["Digitalisierung"])
    path: str = Field(description="Datei im Markdown-Export", examples=["tags/aps-6.1.9-x.md"])
    parent_id: str | None
    linked_from: list[str] = Field(description="Kapitel, die eine Querschnittsseite verlinken")


class PageTree(BaseModel):
    registry_version: str = Field(examples=["2026-10-18.4"])
    lang: Lang
    pages: list[PageOut] = Field(description="Wurzel zuerst, dann APS nach Code, dann Ad-hoc")


class PageDetail(BaseModel):
    """Eine Seite mit Vorfahren (von der Wurzel abwärts), Unterseiten und Querschnittsverweisen."""

    registry_version: str
    lang: Lang
    page: PageOut
    ancestors: list[PageOut]
    children: list[PageOut]
    linked: list[PageOut]


class JobCounts(BaseModel):
    task: str = Field(examples=["classify:aps"])
    open: int = Field(0, description="muss bearbeitet werden")
    pending: int = Field(0, description="ein Worker bearbeitet ihn gerade")
    done: int = Field(0, description="Ergebnis gespeichert")
    failed: int = Field(0, description="nicht klassifizierbar, mit Fehlergrund")
    total: int = 0


class JobsSummary(BaseModel):
    tasks: list[JobCounts]


class LabelOut(BaseModel):
    id: int
    tag_id: str = Field(examples=["aps:6.1.9"])
    name_de: str = Field(examples=["Digitalisierung"])
    scheme: Literal["aps", "adhoc"]
    confidence: float = Field(
        ge=0, le=1, description="Konfidenz, bei unbelegter Textstelle halbiert", examples=[0.86]
    )
    evidence: str | None = Field(
        description="Textstelle aus dem Klassifikationstext", examples=["Der Bundesrat wird …"]
    )
    evidence_verified: bool = Field(description="Die Textstelle steht (unscharf) im Text")
    status: Literal["active", "rejected", "superseded"]
    review_status: Literal["confirmed", "rejected", "changed"] | None
    reviewed_by: str | None = Field(description="Name der Person, die entschieden hat")
    reviewed_at: datetime | None
    task: str = Field(examples=["classify:aps"])
    stage: Stage
    model_version: str = Field(examples=["apertus-v1-5-8b"])
    prompt_version: str = Field(examples=["classify_chapters_v1+3f2a9c1d classify_topics_v1+…"])
    registry_version: str
    input_hash: str
    run_id: int | None
    created_at: datetime


class AffairTopics(BaseModel):
    affair_id: int = Field(description="OpenParlData-ID", examples=[70435])
    body_key: str = Field(examples=["CHE"])
    body_name: str | None = Field(description="Name des Parlaments", examples=["Schweiz"])
    body_level: str | None = Field(description=LEVEL, examples=["country"])
    number: str | None = Field(examples=["24.3456"])
    title: str | None
    type: str | None = Field(description="harmonisierter Typ (englisch)", examples=["Motion"])
    begin_date: date | None
    url_external: str | None
    text: str | None = Field(
        description="Klassifikationstext, in dem die Belege stehen: erste Zeile der Titel,"
        " danach die Absätze, getrennt durch Zeilenumbrüche (\\n)"
    )
    language: str | None = Field(examples=["de"])
    summary_de: str | None = Field(description="Kurzzusammenfassung in einem Satz")
    labels: list[LabelOut] = Field(description="Aktive Labels zuerst, danach der Verlauf")


class ReviewIn(BaseModel):
    """Ein Entscheid zum Label eines Themas an einem Geschäft."""

    affair_id: int = Field(examples=[70435])
    tag_id: str = Field(examples=["aps:6.1.9"])
    action: Literal["confirm", "reject", "change", "add", "undo"] = Field(
        description="confirm und reject: aktives Label bestätigen oder verwerfen; change: aktives"
        " Label verwerfen und new_tag_id von Hand setzen; add: Thema von Hand setzen; undo: den"
        " letzten Entscheid zu diesem Thema zurücknehmen"
    )
    new_tag_id: str | None = Field(None, description="nur bei change: das richtige Thema")
    comment: str | None = Field(None, max_length=2000)
    user_name: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)
    ] = Field(description="Name aus der Review-Anmeldung", examples=["Mia Muster"])

    @model_validator(mode="after")
    def _new_tag_only_for_change(self) -> Self:
        if (self.action == "change") != (self.new_tag_id is not None):
            raise ValueError("new_tag_id gehört zu change und nur dorthin")
        if self.new_tag_id == self.tag_id:
            raise ValueError("new_tag_id muss ein anderes Thema sein als tag_id")
        return self


class TopicOut(BaseModel):
    tag_id: str = Field(examples=["aps:6.1.9"])
    scheme: Literal["aps", "adhoc"]
    status: Literal["proposed", "active", "merged", "retired"]
    parent_id: str | None = Field(examples=["aps:6.1"])
    name_de: str = Field(examples=["Digitalisierung"])
    name_fr: str | None
    name_it: str | None
    n_affairs: int = Field(description="Geschäfte mit aktivem Label")


class AffairHead(BaseModel):
    """Kopf eines Geschäfts in Listen."""

    affair_id: int = Field(description="OpenParlData-ID", examples=[70435])
    body_key: str = Field(examples=["CHE"])
    body_name: str | None = Field(description="Name des Parlaments", examples=["Schweiz"])
    body_level: str | None = Field(description=LEVEL, examples=["country"])
    number: str | None
    title: str | None
    type: str | None = Field(description="harmonisierter Typ (englisch)", examples=["Motion"])
    begin_date: date | None


class TopicAffair(AffairHead):
    confidence: float = Field(ge=0, le=1)
    evidence: str | None
    evidence_verified: bool
    stage: Stage


class TopicAffairs(BaseModel):
    total: int = Field(description="Treffer insgesamt, unabhängig von limit und offset")
    limit: int
    offset: int
    items: list[TopicAffair] = Field(description="nach Konfidenz, dann neueste zuerst")


class ReviewItem(AffairHead):
    """Ein Label mit Prüfbedarf oder Entscheid, mit dem Kopf seines Geschäfts."""

    label: LabelOut
    reasons: list[Reason] = Field(
        description="low_confidence: Konfidenz unter threshold; no_evidence: ohne Beleg;"
        " evidence_unverified: Beleg nicht im Text gefunden;"
        " sample: Stichprobe (jedes 50. Geschäft)"
    )


class ReviewQueue(BaseModel):
    threshold: float = Field(
        description="CONFIDENCE_THRESHOLD der Klassifikation; darunter gilt sie als tief",
        examples=[0.6],
    )
    total: int = Field(description="Treffer insgesamt, unabhängig von limit und offset")
    limit: int
    offset: int
    items: list[ReviewItem] = Field(
        description="open: tiefste Konfidenz zuerst; done: neuester Entscheid zuerst"
    )
