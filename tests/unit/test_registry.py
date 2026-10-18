import copy
import random
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from parltopics.registry import Registry, RegistryError, load_registry, scheme_hash, tag_hash

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "tags_example.yaml"


@pytest.fixture
def data() -> dict:
    return yaml.safe_load(FIXTURE.read_text(encoding="utf-8"))


def build(data: dict) -> Registry:
    return Registry.model_validate(data)


def tag(data: dict, tag_id: str) -> dict:
    return next(t for t in data["tags"] if t["tag_id"] == tag_id)


def test_repository_registry_is_valid(repo_root):
    registry = load_registry(repo_root / "registry" / "tags.yaml")
    assert registry.get("adhoc:digitalisierung-breit").status == "active"
    assert set(registry.schemes) == {"aps", "adhoc"}


def test_example_registry(data):
    registry = build(data)
    assert [t.tag_id for t in registry.active("aps")] == ["aps:6", "aps:6.1", "aps:6.1.9"]
    assert registry.get("aps:6").aps_level == "bereich"
    assert registry.get("aps:6.1").aps_level == "kapitel"
    assert registry.get("aps:6.1.9").aps_level == "thema"
    assert registry.get("adhoc:digitalisierung-breit").aps_level is None


def test_scheme_hash_ignores_order_of_tags_and_aliases(data):
    reference = scheme_hash(build(data), "aps")
    shuffled = copy.deepcopy(data)
    random.Random(7).shuffle(shuffled["tags"])
    tag(shuffled, "aps:6.1.9")["aliases"].reverse()
    assert scheme_hash(build(shuffled), "aps") == reference


def test_adhoc_change_does_not_touch_aps_hash(data):
    before = build(data)
    changed = copy.deepcopy(data)
    tag(changed, "adhoc:digitalisierung-breit")["descriptions"]["de"] = "Neue Beschreibung"
    after = build(changed)
    assert scheme_hash(after, "aps") == scheme_hash(before, "aps")
    assert scheme_hash(after, "adhoc") != scheme_hash(before, "adhoc")
    assert tag_hash(after.get("adhoc:digitalisierung-breit")) != tag_hash(
        before.get("adhoc:digitalisierung-breit")
    )


def test_aps_description_change_changes_aps_hash(data):
    changed = copy.deepcopy(data)
    tag(changed, "aps:6.1.9")["descriptions"]["de"] = "Andere Beschreibung"
    assert scheme_hash(build(changed), "aps") != scheme_hash(build(data), "aps")


def test_metadata_does_not_change_hashes(data):
    changed = copy.deepcopy(data)
    tag(changed, "aps:6.1.9")["unreviewed_translations"] = []
    tag(changed, "adhoc:digitalisierung-breit")["created"]["by"] = "jemand anders"
    for scheme in ("aps", "adhoc"):
        assert scheme_hash(build(changed), scheme) == scheme_hash(build(data), scheme)


def test_retired_and_proposed_tags_are_not_part_of_the_hash(data):
    changed = copy.deepcopy(data)
    tag(changed, "aps:6.1.10")["descriptions"]["de"] = "geändert"
    tag(changed, "adhoc:ki-verwaltung")["descriptions"]["de"] = "geändert"
    for scheme in ("aps", "adhoc"):
        assert scheme_hash(build(changed), scheme) == scheme_hash(build(data), scheme)


def mutate_duplicate(d):
    d["tags"].append(copy.deepcopy(d["tags"][0]))


def mutate_unknown_parent(d):
    tag(d, "aps:6.1.9")["parent"] = "aps:9.9"


def mutate_merged_without_target(d):
    del tag(d, "adhoc:e-government")["merged_into"]


def mutate_target_without_merged(d):
    tag(d, "adhoc:ki-verwaltung")["merged_into"] = "adhoc:digitalisierung-breit"


def mutate_prefix_mismatch(d):
    tag(d, "adhoc:digitalisierung-breit")["scheme"] = "aps"


def mutate_bad_id(d):
    tag(d, "aps:6")["tag_id"] = "APS:6"


def mutate_bad_version(d):
    d["registry_version"] = "v2"


def mutate_unknown_field(d):
    tag(d, "aps:6")["colour"] = "rot"


def mutate_missing_german_name(d):
    tag(d, "aps:6")["names"] = {"fr": "Infrastructure"}


def mutate_unknown_scheme(d):
    del d["schemes"]["adhoc"]


@pytest.mark.parametrize(
    "mutate",
    [
        mutate_duplicate,
        mutate_unknown_parent,
        mutate_merged_without_target,
        mutate_target_without_merged,
        mutate_prefix_mismatch,
        mutate_bad_id,
        mutate_bad_version,
        mutate_unknown_field,
        mutate_missing_german_name,
        mutate_unknown_scheme,
    ],
)
def test_invalid_registries_are_rejected(data, mutate):
    broken = copy.deepcopy(data)
    mutate(broken)
    with pytest.raises(ValidationError):
        build(broken)


def test_duplicate_ids_are_named(data):
    broken = copy.deepcopy(data)
    mutate_duplicate(broken)
    with pytest.raises(ValidationError, match="Doppelte tag_id: aps:6"):
        build(broken)


@pytest.mark.parametrize("content", ["registry_version: [", "- nur\n- eine Liste\n"])
def test_load_registry_reports_file_errors(tmp_path, content):
    path = tmp_path / "tags.yaml"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(RegistryError, match=str(path)):
        load_registry(path)
