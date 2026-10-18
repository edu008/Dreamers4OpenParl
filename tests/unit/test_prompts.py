import re
from pathlib import Path

import pytest
import yaml
from jinja2 import Environment, StrictUndefined

from parltopics.registry import Registry

ROOT = Path(__file__).resolve().parents[2]
PROMPTS = sorted((ROOT / "prompts").glob("*_v*.md"))
FIXTURE = ROOT / "tests" / "fixtures" / "tags_example.yaml"
ENV = Environment(undefined=StrictUndefined, keep_trailing_newline=True)


def split(path: Path) -> tuple[dict, dict[str, str]]:
    _, header, body = path.read_text(encoding="utf-8").split("---", 2)
    parts = re.split(r"^## (system|user)\s*$", body, flags=re.MULTILINE)
    return yaml.safe_load(header), dict(zip(parts[1::2], parts[2::2], strict=True))


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
    assert "<<<\nDer Bundesrat …\n>>>" in user
