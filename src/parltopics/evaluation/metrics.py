"""Rechnungen des Evaluationsberichts (PRD F16, 13), ohne Datenbank.

Das Gold-Set sind die Entscheide der Menschen je Geschäft und Thema (api.queries.GOLD): bestätigt
oder von Hand gesetzt gehört dazu, verworfen oder ersetzt nicht. Es ist unvollständig, denn nicht
jedes Label wird geprüft. Darum zählen nur entschiedene Paare: Ein Label ohne Entscheid ist weder
Treffer noch Fehler.
"""

from collections.abc import Set as AbstractSet
from dataclasses import dataclass

LEVELS = ("bereich", "kapitel", "thema")
EDGES = (0.6, 0.7, 0.8, 0.9)  # Konfidenzbänder nach PRD 13, darunter ein Band ab 0

Gold = dict[int, dict[str, bool]]  # affair_id → tag_id → gehört dazu
Labels = dict[int, set[str]]  # affair_id → tag_ids, die das Modell vergeben hat


@dataclass(frozen=True)
class Share:
    """Anteil mit Nenner, damit der Bericht keine Quote ohne Zählung zeigt."""

    hits: int
    total: int

    def __str__(self) -> str:
        return (
            f"{self.hits}/{self.total} ({100 * self.hits / self.total:.0f} %)"
            if self.total
            else "–"
        )


@dataclass(frozen=True)
class Counts:
    tp: int = 0
    fp: int = 0
    fn: int = 0

    @property
    def precision(self) -> Share:
        return Share(self.tp, self.tp + self.fp)

    @property
    def recall(self) -> Share:
        return Share(self.tp, self.tp + self.fn)


def node(tag_id: str, level: str) -> str | None:
    """Knoten eines APS-Tags auf einer Stufe, aus der ID abgeleitet: aps:6.1.9 liegt im Bereich
    aps:6 und im Kapitel aps:6.1. None für Ad-hoc-Tags und für Stufen unterhalb des Tags."""
    if not tag_id.startswith("aps:"):
        return None
    depth = LEVELS.index(level) + 1
    parts = tag_id.removeprefix("aps:").split(".")
    return "aps:" + ".".join(parts[:depth]) if len(parts) >= depth else None


def score(labels: Labels, gold: Gold, level: str) -> Counts:
    """Labels gegen die Entscheide je Geschäft in gold, auf einer Hierarchiestufe (nur APS).

    Ein Knoten ist richtig, wenn ein bestätigtes Thema darauf fällt, und falsch, wenn nur
    verworfene darauf fallen. So zählt ein falsches Thema im richtigen Kapitel auf Kapitel- und
    Bereichsstufe als Treffer (Teiltreffer, PRD 13). Bestätigte Knoten ohne Label fehlen (fn).
    """
    tp = fp = fn = 0
    for affair_id, decisions in gold.items():
        right = {node(tag, level) for tag, belongs in decisions.items() if belongs} - {None}
        wrong = {node(tag, level) for tag, belongs in decisions.items() if not belongs}
        wrong -= right | {None}
        guessed = {node(tag, level) for tag in labels.get(affair_id, ())} - {None}
        tp += len(guessed & right)
        fp += len(guessed & wrong)
        fn += len(right - guessed)
    return Counts(tp, fp, fn)


@dataclass(frozen=True)
class Band:
    low: float
    high: float | None  # None: bis und mit 1
    labels: Share  # bestätigt von geprüft
    sample: Share  # dasselbe nur in der Stichprobe, die nicht nach Konfidenz ausgewählt ist
    from_low: Share  # alle geprüften Labels ab low: Präzision bei dieser Schwelle


def bands(decisions: list[tuple[float, bool, bool]]) -> list[Band]:
    """Präzision je Konfidenzband aus (Konfidenz, bestätigt, in der Stichprobe) je geprüftem
    Modell-Label."""
    edges = (0.0, *EDGES)
    result = []
    for low, high in zip(edges, (*EDGES, None), strict=True):
        inside = [
            (ok, sample) for c, ok, sample in decisions if low <= c and (high is None or c < high)
        ]
        above = [ok for c, ok, _ in decisions if c >= low]
        result.append(
            Band(
                low=low,
                high=high,
                labels=Share(sum(ok for ok, _ in inside), len(inside)),
                sample=Share(sum(ok for ok, s in inside if s), sum(s for _, s in inside)),
                from_low=Share(sum(above), len(above)),
            )
        )
    return result


@dataclass(frozen=True)
class PathRecall:
    """Recall im Kandidatenpfad eines Ad-hoc-Themas (PRD 7.4, 13), Stufen getrennt."""

    candidates: Share  # Positive unter den Stichworttreffern (Kandidaten-Recall)
    classifier: Share  # davon mit Label (Recall des Klassifikators innerhalb der Kandidaten)
    overall: Share  # Positive mit Label, ob Kandidat oder Stichprobe


def path_recall(
    positives: set[int],
    candidates: set[int],
    labelled: set[int],
    sample: AbstractSet[int] = frozenset(),
    weight: int = 1,
) -> PathRecall:
    """positives: wahre Treffer im Bereich des Laufs (Parlamente, Datum). Positive in sample
    zählen weight-fach, denn die Stichprobe steht für alle Geschäfte ohne Stichworttreffer."""

    def count(ids: set[int]) -> int:
        return sum(weight if affair_id in sample else 1 for affair_id in ids)

    found = positives & candidates
    return PathRecall(
        candidates=Share(count(found), count(positives)),
        classifier=Share(count(found & labelled), count(found)),
        overall=Share(count(positives & labelled), count(positives)),
    )
