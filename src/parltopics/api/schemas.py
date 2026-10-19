"""Antwortmodelle der Sidecar-API (PRD F10); sie bestimmen das Schema unter /v1/openapi.json."""

from datetime import date, datetime
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from parltopics.classify.adhoc import Keywords
from parltopics.wiki.tree import PageKind

# rule: Thema per Regel aus dem Titel eines Routinegeschäfts, ohne Modell (0006_rule_stage).
Stage = Literal["8b", "70b", "human", "rule"]
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


class PageStatement(BaseModel):
    text: str
    affair_ids: list[int] = Field(description="Geschäfte, auf die sich die Aussage stützt")
    page_ids: list[str] = Field(description="Unterseiten, auf die sich die Aussage stützt")


class PageSummary(BaseModel):
    """Zusammenfassung und Kennzahl einer Seite aus wiki_pages. Jede Aussage ist belegt."""

    page_status: Literal["open", "pending", "done", "failed"]
    n_affairs: int = Field(description="Geschäfte mit aktivem Label auf der Seite und darunter")
    summary_short: str | None = Field(description="ein Satz für die Navigation")
    summary_long: str | None = Field(description="Absatz aus den Aussagen")
    statements: list[PageStatement]
    built_at: datetime | None
    window_start: date | None = Field(description="Zeitfenster der Zusammenfassung")
    window_end: date | None
    model_version: str | None
    prompt_version: str | None


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
    summary: PageSummary | None = Field(
        None,
        description="Stand aus dem Seitenlauf (F23–F25); null ohne Lauf oder ohne Datenbank",
    )


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
    tag_status: Literal["proposed", "active", "merged", "retired"] = Field(
        description="Status des Themas; proposed heisst: noch nicht freigegeben, Treffer vorläufig"
    )


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
    rank: float | None = Field(
        description="ts_rank über die getippten Wörter und die bevorzugten Bezeichnungen der"
        " erkannten Themen; ein Treffer im Titel zählt mehr als im Text; 0: nur über ein Synonym"
        " oder das Label eines Themas gefunden; null ohne q"
    )
    headline: str | None = Field(
        description="Ausschnitte aus dem Klassifikationstext als HTML: alles maskiert,"
        " nur die Treffer stehen in <mark>; null ohne q",
        examples=["Der Bundesrat soll die Verwaltung <mark>digitalisieren</mark>."],
    )
    topics: list[HitTopic] = Field(description="aktive Themen, höchste Konfidenz zuerst")


class SearchTopic(BaseModel):
    """Ein Thema, das die Suche in der Anfrage erkannt hat: Seine Bezeichnungen in DE, FR und IT
    und die Geschäfte mit seinem Label gehören zu den Treffern."""

    tag_id: str = Field(examples=["aps:6.1.9"])
    name_de: str = Field(examples=["Digitalisierung"])
    source: Literal["registry", "llm"] = Field(
        description="registry: über eine Bezeichnung der Registry erkannt; llm: von 8B"
        " vorgeschlagen, weil die Registry nichts erkannte"
    )
    typed: str | None = Field(
        description="die Wörter der Anfrage, die das Thema trafen; null bei llm",
        examples=["Digitalisirung"],
    )
    label: str | None = Field(
        description="die Bezeichnung, die sie trafen; null bei llm", examples=["Digitalisierung"]
    )
    typo: bool = Field(description="true: als Tippfehler erkannt, typed weicht von label ab")


class SearchResult(BaseModel):
    q: str | None = Field(description="Suchbegriffe; null listet die neuesten Geschäfte")
    total: int = Field(description="Treffer insgesamt, unabhängig von limit und offset")
    limit: int
    offset: int
    duration_ms: int = Field(description="Dauer der Abfragen in der API")
    items: list[SearchHit] = Field(
        description="nach Rang, dann neueste zuerst; mit erkanntem Thema und ohne Sprachfilter"
        " abwechselnd je Sprache, Treffer mit Rang 0 zuletzt; ohne q die neuesten"
    )
    topics: list[SearchTopic] = Field(
        default_factory=list, description="erkannte Themen; leer: wie getippt gesucht"
    )
    expanded_terms: dict[str, list[str]] = Field(
        default_factory=dict,
        description="zusätzlich gesuchte Bezeichnungen der Themen je Sprache (de, fr, it), ohne"
        " versteckte Schreibweisen; leer ohne Thema",
        examples=[{"de": ["Digitalisierung"], "fr": ["Numérisation"], "it": ["Digitalizzazione"]}],
    )
    model_version: str | None = Field(
        None, description="Modell, das Themen vorschlug; nur wenn die Registry nichts erkannte"
    )
    prompt_version: str | None = Field(
        None, description="Prompt dazu, z. B. search_topics_v1+…; sonst null"
    )


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


class GraphNode(BaseModel):
    id: str = Field(description="Seite und Tag", examples=["aps:6"])
    label: str = Field(examples=["Infrastruktur und Umwelt"])
    kind: PageKind = Field(
        description="bereich in der Übersicht, sonst kapitel, tag oder querschnitt (Ad-hoc)"
    )
    count: int = Field(description="Geschäfte mit aktivem Label auf diesem Knoten")
    group: str = Field(
        description="APS-Bereich, zum Beispiel für die Farbe; adhoc bei Ad-hoc-Themen",
        examples=["aps:6"],
    )


class GraphEdge(BaseModel):
    a: str
    b: str
    weight: int = Field(description="Geschäfte, die beide Knoten tragen")


class TopicGraph(BaseModel):
    area: str | None = Field(
        description="geöffneter Bereich oder all für alle Themen; null in der Übersicht"
    )
    nodes: list[GraphNode] = Field(description="sortiert wie der Seitenbaum")
    edges: list[GraphEdge] = Field(description="stärkste zuerst, höchstens limit")
    hidden: int = Field(description="Kanten ab min_weight, die wegen limit fehlen")


class RelatedTopic(BaseModel):
    tag_id: str = Field(examples=["adhoc:digitalisierung-breit"])
    name_de: str
    shared: int = Field(description="Geschäfte mit beiden Themen (aktive Labels)")
    in_registry: bool = Field(description="in der Registry als verwandt eingetragen")


UserName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]


class KeywordsIn(BaseModel):
    name_de: str = Field(min_length=2, max_length=120, examples=["Velowege"])
    description_de: str = Field(min_length=10, max_length=2000)


class AdhocScope(BaseModel):
    keywords: Keywords
    bodies: list[str] | None = Field(None, description='nur diese Parlamente, z. B. ["CHE"]')
    since: date | None = Field(None, description="nur Geschäfte ab diesem Datum")


class AdhocPreview(BaseModel):
    candidates: int = Field(description="Geschäfte mit Stichworttreffer")
    sample: int = Field(description="Stichprobe ohne Treffer (jedes 50. Geschäft)")
    examples: list[AffairHead] = Field(description="die neuesten Kandidaten, höchstens fünf")


class AdhocIn(AdhocScope):
    name_de: str = Field(min_length=2, max_length=120, examples=["Velowege"])
    description_de: str = Field(min_length=10, max_length=2000)
    broader: list[str] = Field(
        default_factory=list, description="APS-Tags, auf deren Seiten das Thema verlinkt wird"
    )
    user_name: UserName = Field(description="wer das Thema anlegt", examples=["Mia Muster"])


class AdhocCreated(BaseModel):
    tag_id: str = Field(examples=["adhoc:velowege"])
    registry_version: str
    run_id: int
    jobs: int = Field(description="Jobs des Laufs: Kandidaten und Stichprobe")
    candidates: int
    sample: int


class AdhocStepIn(BaseModel):
    """Zurückziehen; Name und Zeit stehen im Tag unter changes."""

    user_name: UserName = Field(description="wer den Schritt macht", examples=["Mia Muster"])


class AdhocActivateIn(BaseModel):
    """Freischalten; der Body ist freiwillig, damit bestehende Aufrufe ohne Namen weiter gehen."""

    user_name: UserName | None = Field(
        None, description="wer freischaltet; ohne Angabe «api»", examples=["Mia Muster"]
    )


class AdhocActivated(BaseModel):
    tag_id: str
    status: Literal["active"]
    registry_version: str


class AdhocRetired(BaseModel):
    tag_id: str
    status: Literal["retired"]
    registry_version: str
    jobs: int = Field(description="geschlossene Jobs (failed, Grund retired), auch erledigte")
    labels: int = Field(
        description="Labels ohne menschlichen Entscheid, jetzt superseded; bestätigte und von Hand"
        " gesetzte bleiben aktiv"
    )


class ProposalOut(BaseModel):
    """Ein gruppierter Tag-Vorschlag mit Empfehlung (F7)."""

    id: int
    name_de: str = Field(examples=["Digitale Behördenleistungen"])
    desc_de: str | None
    reason: str | None = Field(description="Begründung der Empfehlung")
    recommendation: Literal["new", "duplicate_of", "child_of"] | None
    related_tag_id: str | None = Field(description="bei duplicate_of und child_of das Tag")
    related_name_de: str | None
    variants: list[str] = Field(description="Namen der Rohvorschläge, höchstens fünf")
    n_affairs: int = Field(description="Geschäfte, bei denen das Modell das Thema vermisste")
    affairs: list[AffairHead] = Field(description="Auswahl dieser Geschäfte, höchstens fünf")
    status: Literal["open", "pending", "done"]
    decision: Literal["accepted", "merged", "rejected"] | None
    decided_by: str | None = Field(
        description="wer entschieden hat; bei offenem Vorschlag, wer den Entscheid zurücknahm"
    )
    decided_at: datetime | None
    created_at: datetime
    model_version: str | None = Field(description="Modell der Empfehlung; pg_trgm ohne Modell")


class ProposalList(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[ProposalOut]


class ProposalDecisionIn(BaseModel):
    decision: Literal["accepted", "merged", "rejected", "undo"] = Field(
        description="accepted: als Ad-hoc-Thema (proposed) anlegen und die betroffenen Geschäfte"
        " prüfen lassen; merged: geht in related_tag_id auf; rejected: verwerfen; undo: den"
        " Entscheid zurücknehmen, der Vorschlag ist wieder offen und ein mit accepted angelegtes"
        " Thema wird zurückgezogen"
    )
    user_name: UserName = Field(examples=["Mia Muster"])
    name_de: str | None = Field(None, min_length=2, max_length=120, description="nur accepted")
    description_de: str | None = Field(
        None, min_length=10, max_length=2000, description="nur accepted"
    )
    broader: list[str] | None = Field(
        None, description="nur accepted; ohne Angabe bei child_of das verwandte Tag"
    )
    related_tag_id: str | None = Field(None, description="bei merged das Tag, sonst die Empfehlung")


class ProposalDecisionOut(BaseModel):
    proposal: ProposalOut
    tag_id: str | None = Field(
        description="bei accepted das neue Ad-hoc-Tag, bei undo das zurückgezogene"
    )
    run_id: int | None
    jobs: int | None = Field(description="bei accepted: Jobs für die betroffenen Geschäfte")


class NavigateIn(BaseModel):
    query: str = Field(
        min_length=3, max_length=300, examples=["Was unternimmt der Bund gegen Cyberangriffe?"]
    )


class TopicName(BaseModel):
    tag_id: str
    name_de: str


class PathStep(BaseModel):
    page_id: str = Field(examples=["aps:6"])
    title: str


class AnswerStatement(BaseModel):
    text: str
    affair_ids: list[int] = Field(description="Geschäfte, auf die sich die Aussage stützt")


class NavigateHit(AffairHead):
    topics: list[HitTopic] = Field(description="aktive Themen, höchste Konfidenz zuerst")


class NavigateOut(BaseModel):
    """Antwort der Navigationssuche, wie search-contract.ts der Web-App (name_de statt name)."""

    query: str
    answer: str | None = Field(description="Kurzantwort aus belegten Aussagen; null ohne Treffer")
    statements: list[AnswerStatement] = Field(description="die Aussagen der Antwort")
    hits: list[NavigateHit] = Field(description="die gewählten Geschäfte")
    related_topics: list[TopicName] = Field(description="Themen auf dem Suchweg und der Treffer")
    path: list[PathStep] = Field(
        description="Suchweg von Heart bis zur Tag-Seite; beim Rückfall nur volltext"
    )
    status: Literal["ok", "no_results", "limit_reached"]
    steps: int = Field(description="Modellaufrufe dieser Suche")
    fallback_used: bool = Field(description="die Volltextsuche hat die Geschäfte geliefert")
    filters: dict | None = Field(description="aus der Frage gelesene Filter")
    duration_ms: int
    search_run_id: int = Field(description="Zeile in search_runs")


# Gespeicherte OpenParlData-Datensätze. Sprachfelder sind geschachtelt wie bei OpenParlData
# ({"de": …, "fr": …}, ohne Werte {}); weitere gespeicherte Felder kommen unverändert mit.
Localized = dict[str, str]
LINK = "Link nach aussen; die Web-App lädt nichts von dort (Offline)"


class BodyRecord(BaseModel):
    """Ein Parlament, wie es in bodies.raw liegt, mit Sitzen, Bevölkerung und Wikidata."""

    model_config = ConfigDict(extra="allow")

    id: int = Field(examples=[257])
    body_key: str = Field(examples=["GE"])
    url_api: str = Field(description=f"derselbe Datensatz bei OpenParlData; {LINK}")
    name: Localized = Field(default_factory=dict, examples=[{"de": "Genf", "fr": "Genève"}])
    type: str | None = Field(None, description=LEVEL, examples=["canton"])
    type_name: Localized = Field(default_factory=dict, examples=[{"de": "Kanton"}])
    legislative_name: Localized = Field(default_factory=dict, examples=[{"de": "Grosser Rat"}])
    executive_name: Localized = Field(default_factory=dict, examples=[{"de": "Staatsrat"}])
    canton_key: str | None = Field(None, examples=["GE"])
    languages: str | None = Field(None, description="Amtssprachen, kommagetrennt", examples=["FR"])
    flag_image_oparl_url: str | None = Field(None, description=f"Wappen; {LINK}")


class BodyDetail(BodyRecord):
    n_affairs: int = Field(description="Geschäfte dieses Parlaments in der Datenbank")
    n_labelled: int = Field(description="davon mit mindestens einem aktiven Label")


class TextRecord(BaseModel):
    """Ein Text des Geschäfts (affair_texts) mit allen gespeicherten Sprachen."""

    model_config = ConfigDict(extra="allow")

    id: int
    type: Localized = Field(default_factory=dict, examples=[{"de": "Eingereichter Text"}])
    text: Localized = Field(
        default_factory=dict,
        description="Text je Sprache wie aus der Quelle, oft HTML und nicht bereinigt: nur als"
        " Text anzeigen oder vorher bereinigen. Ohne HTML: GET /v1/affairs/{affair_id}/topics",
    )
    text_format: str | None = None
    text_date: str | None = None


class DocRecord(BaseModel):
    """Ein Dokument (affair_docs) ohne seinen Text."""

    model_config = ConfigDict(extra="allow")

    id: int
    name: str | None = None
    category: Localized = Field(default_factory=dict)
    category_harmonized: str | None = None
    date: str | None = Field(None, examples=["2026-10-13T00:00:00"])
    language: str | None = None
    format: str | None = Field(None, examples=["application/pdf"])
    size: int | None = Field(None, description="Grösse der Datei in Bytes")
    url: str | None = Field(None, description=f"Datei beim Parlament; {LINK}")
    url_oparl: str | None = Field(None, description=f"Kopie bei OpenParlData; {LINK}")
    has_text: bool = Field(description="Text extrahiert und gespeichert: GET /v1/docs/{doc_id}")


class DocDetail(DocRecord):
    parent_type: str | None = Field(description="affair, agenda, meeting, news oder session")
    parent_id: int | None
    text: str | None = Field(description="aus der Datei extrahierter Text, bis einige MB")


class DocList(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[DocRecord] = Field(description="nach Datum, ohne Datum zuletzt")


class AffairRecord(BaseModel):
    """Ein Geschäft, wie es in affairs.raw liegt, mit Parlament, Texten und Dokumenten."""

    model_config = ConfigDict(extra="allow")

    id: int = Field(description="OpenParlData-ID", examples=[341579])
    body_key: str = Field(examples=["GE"])
    url_api: str = Field(description=f"derselbe Datensatz bei OpenParlData; {LINK}")
    number: str | None = Field(None, examples=["E 3265"])
    title: Localized = Field(default_factory=dict, examples=[{"fr": "Election d'une juge …"}])
    title_long: Localized = Field(default_factory=dict)
    type_name: Localized = Field(default_factory=dict, description="Typ beim Parlament")
    type_harmonized: Localized = Field(default_factory=dict, examples=[{"de": "Wahl"}])
    state_name: Localized = Field(default_factory=dict, description="Stand beim Parlament")
    state_name_harmonized: Localized = Field(default_factory=dict)
    url_external: Localized = Field(default_factory=dict, description=f"beim Parlament; {LINK}")
    begin_date: str | None = Field(None, examples=["2026-10-29T00:00:00"])
    end_date: str | None = None
    body: BodyRecord | None = Field(description="null, wenn das Parlament nicht gespeichert ist")
    texts: list[TextRecord]
    docs: list[DocRecord] = Field(
        description="die ersten 20 nach Datum; alle unter GET /v1/affairs/{affair_id}/docs"
    )
    n_docs: int = Field(description="Dokumente des Geschäfts insgesamt")


class TopicStar(BaseModel):
    """Graph, Sicht 1: ein Thema in der Mitte, jede Kante führt zu einem seiner Geschäfte."""

    center: TopicName
    total: int = Field(description="Geschäfte mit aktivem Label ab min_confidence")
    nodes: list[TopicAffair] = Field(description="höchste Konfidenz zuerst, höchstens limit")


class Neighbour(AffairHead):
    shared: list[str] = Field(description="gemeinsame aktive Themen", examples=[["aps:6.1.9"]])
    score: float = Field(description="Summe der Konfidenzen des Nachbarn auf diesen Themen")


class AffairStar(BaseModel):
    """Graph, Sicht 2: ein Geschäft mit seinen Themen und Nachbarn über gemeinsame Themen."""

    center: NavigateHit
    neighbours: list[Neighbour] = Field(
        description="die meisten gemeinsamen Themen zuerst, dann nach score, höchstens limit"
    )


class ReasonCounts(BaseModel):
    low_confidence: int = 0
    no_evidence: int = 0
    evidence_unverified: int = 0
    sample: int = 0


class AreaCount(BaseModel):
    page_id: str = Field(examples=["aps:6"])
    title: str = Field(examples=["Infrastruktur und Umwelt"])
    count: int


class BodyCount(BaseModel):
    body_key: str = Field(examples=["CHE"])
    name: str | None = Field(examples=["Schweiz"])
    count: int


class TopicCount(BaseModel):
    tag_id: str = Field(examples=["aps:6.1.9"])
    name_de: str
    count: int


class ReviewSummary(BaseModel):
    """Zähler der Review-Warteschlange, ohne die Labels selbst zu laden."""

    threshold: float = Field(description="CONFIDENCE_THRESHOLD der Klassifikation")
    open: int = Field(description="Labels mit Prüfbedarf")
    done: int = Field(description="Labels mit Entscheid")
    by_reason: ReasonCounts = Field(
        description="offene Labels je Grund; ein Label kann mehrere Gründe haben"
    )
    by_area: list[AreaCount] = Field(
        description="offene Labels je APS-Bereich, wie der Seitenbaum; Ad-hoc-Themen gehören zu"
        " keinem Bereich"
    )
    by_body: list[BodyCount] = Field(description="offene Labels je Parlament, nach Name")
    by_topic: list[TopicCount] = Field(description="offene Labels je Thema, wie der Seitenbaum")


class LevelCount(BaseModel):
    level: str | None = Field(description=LEVEL, examples=["canton"])
    count: int


class PageBodyCount(BodyCount):
    level: str | None = Field(description=LEVEL)


class YearCount(BaseModel):
    year: int | None = Field(description="Jahr von begin_date; null ohne Datum", examples=[2026])
    count: int


class TypeCount(BaseModel):
    type: str | None = Field(description="harmonisierter Typ (englisch)", examples=["Motion"])
    type_de: str | None = Field(examples=["Motion"])
    count: int


class AffairsSummary(BaseModel):
    """Auswertung der Geschäfte einer Seite. Kennzahlen mit allen Filtern; jede Verteilung ohne
    ihren eigenen Filter, damit sie die Alternativen zeigt (wie die Web-App)."""

    rows: int = Field(description="Zeilen wie unter /affairs: eine je Geschäft und Thema")
    affairs: int = Field(description="Geschäfte, ohne Doppelzählung")
    bodies: int = Field(description="Parlamente")
    verified: int = Field(description="Zeilen mit gefundenem Beleg")
    first_date: date | None
    last_date: date | None
    by_level: list[LevelCount] = Field(description="Geschäfte je Ebene, ohne den Filter level")
    by_body: list[PageBodyCount] = Field(
        description="Geschäfte je Parlament, meiste zuerst, ohne den Filter body_key"
    )
    by_year: list[YearCount] = Field(description="Geschäfte je Jahr, ohne die Filter from und to")
    by_type: list[TypeCount] = Field(description="Geschäfte je Typ, meiste zuerst, ohne type")


class AgentIn(NavigateIn):
    """Eine Frage an den Agenten, auch über mehrere Schritte oder für ein neues Thema."""


class ToolCall(BaseModel):
    name: str = Field(examples=["search_affairs"])
    args: dict = Field(description="Argumente des Modells")
    result_size: int = Field(description="Zeichen des Ergebnisses im Prompt")
    ms: int
    error: str | None = Field(None, description="ungültige Argumente oder Fehler des Werkzeugs")


class AdhocDraft(BaseModel):
    """Entwurf eines Ad-hoc-Themas; angelegt wird es erst mit POST /v1/adhoc."""

    name_de: str
    description_de: str
    keywords: Keywords
    candidates: int = Field(description="Geschäfte mit Stichworttreffer")
    sample: int = Field(description="Stichprobe ohne Treffer")
    examples: list[AffairHead] = Field(description="die neuesten Kandidaten, höchstens fünf")


class AgentOut(BaseModel):
    query: str
    answer: str | None = Field(description="Antwort mit Belegen in eckigen Klammern, z. B. [70435]")
    cited_affair_ids: list[int] = Field(description="zitierte Geschäfte; alle kamen aus Werkzeugen")
    hits: list[NavigateHit] = Field(description="die zitierten Geschäfte mit ihren Themen")
    tool_calls: list[ToolCall]
    proposal: AdhocDraft | None = Field(
        description="Entwurf aus propose_adhoc_topic; die Web-App zeigt ihn mit einem"
        " Bestätigen-Knopf, der POST /v1/adhoc aufruft"
    )
    status: Literal["ok", "no_results", "limit_reached"] = Field(
        description="ok: belegt mit Zitaten, Zahlen aus count_affairs oder read_page oder einem"
        " Entwurf aus propose_adhoc_topic;"
        " limit_reached: Antwort nach 6 Werkzeugen oder 60 s erzwungen"
    )
    steps: int = Field(description="Modellaufrufe des Agenten, ohne die in den Werkzeugen")
    duration_ms: int
    agent_run_id: int = Field(description="Zeile in agent_runs")
