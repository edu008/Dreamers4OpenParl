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
    definition: str | None = Field(
        description="Definition des Themas aus der Registry, in lang, sonst Deutsch;"
        " auf der Heart-Seite null"
    )
    alt_labels: list[str] = Field(
        description="weitere Bezeichnungen (Aliasse) in lang, sonst Deutsch",
        examples=[["E-Government", "Digitale Transformation"]],
    )
    related: list[PageOut] = Field(description="verwandte Themen aus der Registry (related)")


class JobCounts(BaseModel):
    task: str = Field(examples=["classify:aps"])
    open: int = Field(0, description="muss bearbeitet werden")
    pending: int = Field(0, description="ein Worker bearbeitet ihn gerade")
    done: int = Field(0, description="Ergebnis gespeichert")
    failed: int = Field(0, description="nicht klassifizierbar, mit Fehlergrund")
    total: int = 0


class HitTopic(BaseModel):
    """Ein aktives Thema eines Suchtreffers mit seinem Beleg (wie HitTopic in der Web-App)."""

    tag_id: str = Field(examples=["aps:6.1.9"])
    name_de: str = Field(examples=["Digitalisierung"])
    confidence: float = Field(ge=0, le=1)
    evidence: str | None
    evidence_verified: bool
    stage: Stage


class RunOut(BaseModel):
    """Ein Lauf der Klassifikation mit seinen Zählern."""

    id: int
    task: str = Field(examples=["classify:aps"])
    kind: Literal["full", "daily", "adhoc", "reclassify", "eval"]
    started_at: datetime
    finished_at: datetime | None
    n_total: int
    n_done: int
    n_failed: int
    n_escalated: int = Field(description="an Apertus 70B weitergegeben")
    prompt_version: str
    registry_version: str
    duration_s: int = Field(description="Dauer in Sekunden, bei laufenden Läufen bis jetzt")
    per_minute: float | None = Field(description="erledigte Geschäfte je Minute")


class JobError(BaseModel):
    task: str = Field(examples=["classify:aps"])
    reason: str = Field(description="erste Zeile der Fehlermeldung, gekürzt")
    count: int


class JobsSummary(BaseModel):
    tasks: list[JobCounts]
    runs: list[RunOut] = Field(description="die letzten zehn Läufe, neuester zuerst")
    errors: list[JobError] = Field(description="häufigste Gründe für failed, höchstens zehn")


class Stats(BaseModel):
    """Gesamtzahlen für die Fortschrittsanzeige."""

    affairs: int = Field(description="Geschäfte in der Datenbank", examples=[326396])
    prepared: int = Field(description="mit Klassifikationstext (affair_inputs)")
    indexed: int = Field(description="im Volltext (search_documents)")
    classified: int = Field(description="mit erledigtem Job classify:aps, auch ohne Thema")
    labelled: int = Field(description="mit mindestens einem aktiven Label")
    labels: int = Field(description="aktive Labels")
    reviewed: int = Field(description="Labels mit Entscheid eines Menschen")


class BodyOut(BaseModel):
    body_key: str = Field(examples=["CHE"])
    name: str | None = Field(examples=["Schweiz"])
    level: str | None = Field(description=LEVEL, examples=["country"])
    n_affairs: int = Field(description="Geschäfte mit mindestens einem aktiven Label")


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


class AffairHead(BaseModel):
    """Kopf eines Geschäfts, in Listen und auf der Geschäftsseite."""

    affair_id: int = Field(description="OpenParlData-ID", examples=[70435])
    body_key: str = Field(examples=["CHE"])
    body_name: str | None = Field(description="Name des Parlaments", examples=["Schweiz"])
    body_level: str | None = Field(description=LEVEL, examples=["country"])
    number: str | None = Field(examples=["24.3456"])
    title: str | None
    type: str | None = Field(description="harmonisierter Typ (englisch)", examples=["Postulate"])
    type_de: str | None = Field(
        description="harmonisierter Typ auf Deutsch, aus OpenParlData", examples=["Postulat"]
    )
    begin_date: date | None


class AffairTopics(AffairHead):
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


class TopicAffair(AffairHead):
    tag_id: str = Field(examples=["aps:6.1.9"])
    name_de: str = Field(examples=["Digitalisierung"])
    confidence: float = Field(ge=0, le=1)
    evidence: str | None
    evidence_verified: bool
    stage: Stage


class TopicAffairs(BaseModel):
    total: int = Field(description="Treffer insgesamt, unabhängig von limit und offset")
    limit: int
    offset: int
    items: list[TopicAffair] = Field(
        description="nach Konfidenz, dann neueste zuerst; eine Zeile je Geschäft und Thema"
    )


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


class SearchHit(AffairHead):
    language: str | None = Field(description="Sprache des Klassifikationstexts", examples=["de"])
    rank: float = Field(description="ts_rank_cd; ein Treffer im Titel zählt mehr als im Text")
    headline: str = Field(
        description="Ausschnitte aus dem Klassifikationstext als HTML: alles maskiert,"
        " nur die Treffer stehen in <mark>",
        examples=["Der Bundesrat soll die Verwaltung <mark>digitalisieren</mark>."],
    )
    topics: list[HitTopic] = Field(description="aktive Themen, höchste Konfidenz zuerst")


class SearchResult(BaseModel):
    q: str
    total: int = Field(description="Treffer insgesamt, unabhängig von limit und offset")
    limit: int
    offset: int
    duration_ms: int = Field(description="Dauer der Abfragen in der API")
    items: list[SearchHit] = Field(description="nach Rang, dann neueste zuerst")


class CalibrationBand(BaseModel):
    low: float = Field(description="untere Grenze der Konfidenz, eingeschlossen", examples=[0.6])
    high: float = Field(description="obere Grenze, ausgeschlossen (beim letzten Band 1.0 dabei)")
    reviewed: int = Field(description="Labels des Modells mit Entscheid")
    confirmed: int
    precision: float | None = Field(description="Anteil bestätigt; null ohne Entscheide")
    sample_reviewed: int = Field(description="davon in der Stichprobe (jedes 50. Geschäft)")
    sample_confirmed: int
    sample_precision: float | None = Field(
        description="Trefferquote nur in der Stichprobe: unabhängig davon, wie die Warteschlange"
        " auswählt, darum die ehrliche Zahl für den Bericht"
    )


class Calibration(BaseModel):
    threshold: float = Field(description="CONFIDENCE_THRESHOLD der Klassifikation")
    reviewed: int
    confirmed: int
    bands: list[CalibrationBand] = Field(description="fünf Bänder zu 0.2, tiefste zuerst")


class GoldLabel(BaseModel):
    """Ein Entscheid eines Menschen: gehört das Thema zum Geschäft?"""

    affair_id: int
    tag_id: str
    decision: Literal["confirmed", "rejected", "changed", "added"]
    belongs: bool = Field(description="true bei confirmed und added, false bei rejected, changed")
    confidence: float | None = Field(description="Konfidenz des Modells; null bei added")
    stage: Stage
    model_version: str
    prompt_version: str
    registry_version: str
    input_hash: str = Field(description="Text, auf den sich der Entscheid bezieht")
    reviewed_by: str | None
    reviewed_at: datetime | None
    sample: bool = Field(description="Geschäft der Stichprobe (jedes 50.)")
