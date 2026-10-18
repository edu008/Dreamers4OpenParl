"""Grobe Kontrolle der APS-Labels mit den Curia-Vista-Sachbereichen (PRD 13, README Hack-Datensatz).

Für APS gibt es keine Gold-Labels. Die Parlamentsdienste ordnen jedem Bundesgeschäft einen oder
mehrere von 28 Sachbereichen zu (che_affairs_keywords.csv). Ein APS-Label trifft, wenn es selbst
oder ein übergeordnetes Kapitel auf einen dieser Sachbereiche gemappt ist (close_match,
broad_match, exact_match in der Registry, ADR 0007). Ziel nach PRD 13: mindestens 75 % der
CHE-Geschäfte 2024–2026 haben mindestens einen Treffer. Ad-hoc-Labels zählen nicht.
"""

import csv
from dataclasses import dataclass
from pathlib import Path

from parltopics.registry import Registry

TARGET = 0.75


def load_curia(path: Path) -> dict[int, set[str]]:
    """openparldata_id → Sachbereiche als curia:<id>. Geschäfte ohne Sachbereich fehlen."""
    curia: dict[int, set[str]] = {}
    with path.open(encoding="utf-8", newline="") as rows:
        for row in csv.DictReader(rows):
            areas = {
                f"curia:{part.strip()}" for part in row["topic_ids"].split("|") if part.strip()
            }
            if areas:
                curia[int(row["openparldata_id"])] = areas
    return curia


def tag_areas(registry: Registry) -> dict[str, set[str]]:
    """Sachbereiche je APS-Tag: eigene Mappings plus die aller übergeordneten Tags."""
    tags = {tag.tag_id: tag for tag in registry.tags if tag.scheme == "aps"}

    def areas(tag_id: str) -> set[str]:
        tag = tags[tag_id]
        own = set(tag.exact_match + tag.close_match + tag.broad_match)
        for parent in tag.broader:
            own |= areas(parent)
        return own

    return {tag_id: areas(tag_id) for tag_id in tags}


@dataclass(frozen=True)
class CuriaScore:
    affairs: int  # Geschäfte mit Sachbereich und mindestens einem APS-Label
    labels: int
    top1: float  # Anteil, deren APS-Label mit der höchsten Konfidenz trifft
    any_hit: float  # Anteil mit mindestens einem Treffer (Ziel PRD 13)
    precision: float  # Anteil der APS-Labels, die treffen


def score(
    predictions: dict[int, list[tuple[str, float]]],
    curia: dict[int, set[str]],
    areas: dict[str, set[str]],
) -> CuriaScore:
    """Vergleicht Labels (tag_id, Konfidenz) je Geschäft mit den Curia-Sachbereichen."""
    top1 = any_hit = hits = labels = affairs = 0
    for affair_id, predicted in predictions.items():
        aps = sorted((p for p in predicted if p[0] in areas), key=lambda p: -p[1])
        if affair_id not in curia or not aps:
            continue
        matched = [bool(areas[tag_id] & curia[affair_id]) for tag_id, _ in aps]
        affairs += 1
        top1 += matched[0]
        any_hit += any(matched)
        hits += sum(matched)
        labels += len(matched)
    return CuriaScore(
        affairs=affairs,
        labels=labels,
        top1=top1 / affairs if affairs else 0.0,
        any_hit=any_hit / affairs if affairs else 0.0,
        precision=hits / labels if labels else 0.0,
    )
