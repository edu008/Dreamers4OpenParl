"""Curia-Vista-Check: Mapping-Vererbung und Kennzahlen (PRD 13)."""

from pathlib import Path

from parltopics.evaluation.curia import load_curia, score, tag_areas
from parltopics.registry import load_registry

REGISTRY = """\
registry_version: '2026-10-18.1'
schemes:
  aps: {label: APS, source: x, fixed: true}
  adhoc: {label: Ad hoc, source: x, fixed: false}
tags:
  - tag_id: 'aps:6'
    scheme: aps
    status: active
    slug: umwelt
    pref_label: {de: Umwelt}
    definition: {de: x}
  - tag_id: 'aps:6.1'
    scheme: aps
    status: active
    slug: verkehr
    pref_label: {de: Verkehr}
    definition: {de: x}
    broader: ['aps:6']
    close_match: ['curia:48']
  - tag_id: 'aps:6.1.3'
    scheme: aps
    status: active
    slug: strasse
    pref_label: {de: Strasse}
    definition: {de: x}
    broader: ['aps:6.1']
  - tag_id: 'aps:6.4'
    scheme: aps
    status: active
    slug: umweltschutz
    pref_label: {de: Umweltschutz}
    definition: {de: x}
    broader: ['aps:6']
    close_match: ['curia:52']
  - tag_id: 'aps:6.4.6'
    scheme: aps
    status: active
    slug: klima
    pref_label: {de: Klima}
    definition: {de: x}
    broader: ['aps:6.4']
  - tag_id: 'adhoc:x'
    scheme: adhoc
    status: active
    pref_label: {de: X}
    definition: {de: x}
"""


def test_topics_inherit_the_mapping_of_their_chapter(tmp_path: Path):
    path = tmp_path / "tags.yaml"
    path.write_text(REGISTRY, encoding="utf-8")
    areas = tag_areas(load_registry(path))
    assert areas["aps:6.1.3"] == {"curia:48"}
    assert areas["aps:6.4.6"] == {"curia:52"}
    assert "adhoc:x" not in areas


def test_score_counts_top1_any_hit_and_precision(tmp_path: Path):
    path = tmp_path / "tags.yaml"
    path.write_text(REGISTRY, encoding="utf-8")
    areas = tag_areas(load_registry(path))
    csv = tmp_path / "che.csv"
    csv.write_text("openparldata_id,topic_ids\n1,48\n2,52 | 48\n3,52\n4,\n", encoding="utf-8")
    curia = load_curia(csv)
    assert curia == {1: {"curia:48"}, 2: {"curia:52", "curia:48"}, 3: {"curia:52"}}
    result = score(
        {
            1: [("aps:6.1.3", 0.9), ("adhoc:x", 0.95)],  # Treffer; Ad-hoc zählt nicht
            2: [("aps:6.4.6", 0.6), ("aps:6.1.3", 0.8)],  # beide treffen
            3: [("aps:6.1.3", 0.9), ("aps:6.4.6", 0.5)],  # Top-1 daneben, zweites trifft
            4: [("aps:6.1.3", 0.9)],  # ohne Sachbereich: nicht gezählt
            5: [("adhoc:x", 0.9)],  # nur Ad-hoc: nicht gezählt
        },
        curia,
        areas,
    )
    assert (result.affairs, result.labels) == (3, 5)
    assert round(result.top1, 3) == round(2 / 3, 3)
    assert result.any_hit == 1.0
    assert result.precision == 4 / 5
