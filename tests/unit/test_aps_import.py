from pathlib import Path

from openpyxl import Workbook

from parltopics.registry import load_registry
from parltopics.registry.aps_import import import_aps


def _xlsx(path: Path) -> None:
    workbook = Workbook()
    workbook.active.title = "Domains"
    workbook["Domains"].append(["code", "domain_de", "domain_fr"])
    workbook["Domains"].append(["1", "Akteure", "Acteurs"])
    chapters = workbook.create_sheet("Chapters")
    chapters.append(["code", "chapter_de", "chapter_fr"])
    chapters.append(["1.1", "Grundfragen", "Questions"])
    topics = workbook.create_sheet("Topics")
    topics.append(["code", "topic_de", "topic_fr"])
    topics.append(["1.1.1", "Identität", "Identité"])
    workbook.save(path)


def test_import_aps_keeps_adhoc_and_is_idempotent(tmp_path: Path) -> None:
    xlsx = tmp_path / "aps.xlsx"
    _xlsx(xlsx)
    registry_file = tmp_path / "tags.yaml"
    registry_file.write_text(
        "registry_version: '2026-10-18.1'\n"
        "schemes:\n"
        "  aps: {label: APS, source: x, fixed: true}\n"
        "  adhoc: {label: Ad hoc, source: x, fixed: false}\n"
        "tags:\n"
        "  - tag_id: 'adhoc:a'\n    scheme: adhoc\n    status: active\n"
        "    names: {de: A}\n    descriptions: {de: A}\n",
        encoding="utf-8",
    )
    count, version = import_aps(xlsx, registry_file)
    registry = load_registry(registry_file)
    assert count == 3
    assert [tag.tag_id for tag in registry.tags] == ["aps:1", "aps:1.1", "aps:1.1.1", "adhoc:a"]
    assert registry.get("aps:1.1.1").parent == "aps:1.1"
    assert import_aps(xlsx, registry_file) == (3, version)
