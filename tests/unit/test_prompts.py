import re
from pathlib import Path

import pytest
import yaml

from parltopics.llm.prompts import ENV, load_prompt, split_prompt
from parltopics.registry import Registry

ROOT = Path(__file__).resolve().parents[2]
PROMPTS = sorted((ROOT / "prompts").glob("*_v*.md"))
FIXTURE = ROOT / "tests" / "fixtures" / "tags_example.yaml"


def split(path: Path) -> tuple[dict, dict[str, str]]:
    return split_prompt(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("path", PROMPTS, ids=lambda p: p.name)
def test_prompt_header_and_sections(path):
    meta, sections = split(path)
    name, version = path.stem.rsplit("_v", 1)
    assert meta["prompt"] == name
    assert meta["version"] == int(version)
    assert meta["model"] in {"small", "large"}
    assert set(sections) == {"system", "user"}
    for text in sections.values():
        ENV.parse(text)


def test_classification_prompts_render_with_registry_tags():
    registry = Registry.model_validate(yaml.safe_load(FIXTURE.read_text(encoding="utf-8")))
    chapters = [t for t in registry.active("aps") if t.aps_level == "kapitel"]
    topics = [t for t in registry.active() if t.aps_level in ("thema", None)]
    _, stage1 = split(ROOT / "prompts" / "classify_chapters_v1.md")
    _, stage2 = split(ROOT / "prompts" / "classify_topics_v1.md")
    system1 = ENV.from_string(stage1["system"]).render(chapters=chapters)
    system2 = ENV.from_string(stage2["system"]).render(tags=topics)
    user = ENV.from_string(stage2["user"]).render(affair_id=70435, text="Der Bundesrat …")
    assert "aps:6.1 | Verkehr und Kommunikation" in system1
    assert "aps:6.1.9 | Digitalisierung | Numérisation | Digitalizzazione" in system2
    assert "adhoc:digitalisierung-breit" in system2
    assert "Digitale Transformation, E-Government" in system2
    assert "summary_de" in system2
    assert "<<<\nDer Bundesrat …\n>>>" in user


def test_load_prompt_builds_messages_and_version():
    registry = Registry.model_validate(yaml.safe_load(FIXTURE.read_text(encoding="utf-8")))
    chapters = [t for t in registry.active("aps") if t.aps_level == "kapitel"]
    prompt = load_prompt(ROOT / "prompts", "classify_chapters_v1")
    system, user = prompt.messages({"chapters": chapters}, {"affair_id": 7, "text": "Text"})
    assert re.fullmatch(r"classify_chapters_v1\+[0-9a-f]{8}", prompt.version)
    assert system["role"] == "system"
    assert "aps:6.1 | Verkehr und Kommunikation" in system["content"]
    assert user == {"role": "user", "content": "Geschäft 7:\n<<<\nText\n>>>"}


def test_prompt_version_ignores_line_endings(tmp_path):
    """Ein Windows-Checkout (CRLF) ergibt dieselbe prompt_version wie LF."""
    text = (ROOT / "prompts" / "classify_topics_v1.md").read_text(encoding="utf-8")
    versions = set()
    for newline in ("\n", "\r\n"):
        folder = tmp_path / str(len(newline))
        folder.mkdir()
        (folder / "classify_topics_v1.md").write_text(text, encoding="utf-8", newline=newline)
        versions.add(load_prompt(folder, "classify_topics_v1").version)
    assert len(versions) == 1


def render(name: str, section: str, **context) -> str:
    _, sections = split(ROOT / "prompts" / f"{name}.md")
    return ENV.from_string(sections[section]).render(**context)


def test_page_and_navigation_prompts_render():
    registry = Registry.model_validate(yaml.safe_load(FIXTURE.read_text(encoding="utf-8")))
    topic = registry.get("aps:6.1.9")
    affair = {
        "id": 70435,
        "body_key": "CHE",
        "begin_date": "2025-03-01",
        "title": "Motion",
        "summary_de": "Bericht zur digitalen Verwaltung.",
    }
    child = {
        "page_id": "aps:6.1.9",
        "title": "Digitalisierung",
        "summary_short": "Kurz.",
        "summary_long": "Lang.",
    }
    stats = {"Geschäfte": 12, "davon Bund": 9}
    tag_user = render(
        "summarize_tag_v1",
        "user",
        tag=topic,
        window_start="2025-10-18",
        window_end="2026-10-18",
        stats=stats,
        affairs=[affair],
    )
    parent_user = render(
        "summarize_parent_v1",
        "user",
        title="Verkehr",
        page_id="aps:6.1",
        stats=stats,
        children=[child],
        samples=[affair],
    )
    first = render("navigate_v1", "system", first_step=True)
    later = render("navigate_v1", "system", first_step=False)
    step_user = render(
        "navigate_v1",
        "user",
        query="KI seit 2024",
        children=[child],
        node={"page_id": "heart", "title": "Heart"},
    )
    answer_user = render(
        "navigate_answer_v1",
        "user",
        query="KI",
        affairs=[affair],
        path=["Heart", "Digitalisierung"],
    )
    assert "70435 | CHE | 2025-03-01 | Bericht zur digitalen Verwaltung." in tag_user
    assert "aps:6.1.9 | Digitalisierung | Kurz. | Lang." in parent_user
    assert "filters" in first and "filters" not in later
    assert "aps:6.1.9 | Digitalisierung | Kurz." in step_user
    assert "Suchweg: Heart → Digitalisierung" in answer_user
