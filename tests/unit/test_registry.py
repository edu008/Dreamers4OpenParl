import copy
import random
import re
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
    breit = registry.get("adhoc:digitalisierung-breit")
    assert breit.status == "active"
    assert "cybersécurité" in breit.alt_labels.fr
    assert set(registry.schemes) == {"aps", "adhoc"}


def test_every_active_tag_has_a_name_in_four_languages(repo_root):
    """Eine tag_id verknüpft DE, FR, IT und EN; die Suche findet das Tag in jeder Sprache."""
    from parltopics.registry.sync import label_rows, tag_row

    registry = load_registry(repo_root / "registry" / "tags.yaml")
    for item in registry.active():
        names = item.pref_label
        assert all((names.de, names.fr, names.it, names.en)), item.tag_id
    krank = registry.get("aps:5.2.4")
    langs = {lang for _, kind, lang, _ in label_rows(krank) if kind == "pref"}
    assert langs == {"de", "fr", "it", "en"}
    assert "Health insurance" in tag_row(krank, registry.registry_version)["match_text"]


def test_example_registry_levels_and_narrower(data):
    registry = build(data)
    assert registry.get("aps:6").aps_level == "bereich"
    assert registry.get("aps:6.1").aps_level == "kapitel"
    assert registry.get("aps:6.1.9").aps_level == "thema"
    assert registry.get("adhoc:digitalisierung-breit").aps_level is None
    narrower = [t.tag_id for t in registry.narrower("aps:6.1")]
    assert narrower == ["aps:6.1.9", "adhoc:digitalisierung-breit"]
    assert registry.get("aps:6.1.9").alt_labels.all() == ["Digitale Transformation", "E-Government"]


def test_scheme_hash_ignores_order_and_non_prompt_fields(data):
    reference = scheme_hash(build(data), "aps")
    changed = copy.deepcopy(data)
    random.Random(7).shuffle(changed["tags"])
    topic = tag(changed, "aps:6.1.9")
    topic["alt_labels"]["de"].reverse()
    topic["hidden_labels"] = ["neu"]
    topic["related"] = []
    tag(changed, "aps:6.1")["close_match"] = ["curia:12"]
    topic["unreviewed_translations"] = []
    assert scheme_hash(build(changed), "aps") == reference


def test_adhoc_change_does_not_touch_aps_hash(data):
    before = build(data)
    changed = copy.deepcopy(data)
    tag(changed, "adhoc:digitalisierung-breit")["definition"]["de"] = "Neue Definition"
    after = build(changed)
    assert scheme_hash(after, "aps") == scheme_hash(before, "aps")
    assert scheme_hash(after, "adhoc") != scheme_hash(before, "adhoc")
    assert tag_hash(after.get("adhoc:digitalisierung-breit")) != tag_hash(
        before.get("adhoc:digitalisierung-breit")
    )


@pytest.mark.parametrize(
    ("tag_id", "field", "value"),
    [
        ("aps:6.1.9", "definition", {"de": "Andere Definition"}),
        ("aps:6.1.9", "pref_label", {"de": "Digitalisierung und KI"}),
        ("aps:6.1.9", "alt_labels", {"de": ["E-Government"]}),
    ],
)
def test_prompt_fields_change_the_aps_hash(data, tag_id, field, value):
    changed = copy.deepcopy(data)
    tag(changed, tag_id)[field] = value
    assert scheme_hash(build(changed), "aps") != scheme_hash(build(data), "aps")


def test_retired_and_proposed_tags_are_not_part_of_the_hash(data):
    changed = copy.deepcopy(data)
    tag(changed, "aps:6.1.10")["definition"]["de"] = "geändert"
    tag(changed, "adhoc:ki-verwaltung")["definition"]["de"] = "geändert"
    for scheme in ("aps", "adhoc"):
        assert scheme_hash(build(changed), scheme) == scheme_hash(build(data), scheme)


def mutate(path: str, value):
    """Setzt ein Feld eines Tags: 'tag_id.feld' = value (None löscht das Feld)."""

    def apply(d):
        tag_id, field = path.rsplit(".", 1)
        entry = tag(d, tag_id)
        if value is None:
            entry.pop(field, None)
        else:
            entry[field] = value

    return apply


def mutate_duplicate(d):
    d["tags"].append(copy.deepcopy(d["tags"][0]))


def mutate_unknown_scheme(d):
    del d["schemes"]["adhoc"]


def mutate_bad_version(d):
    d["registry_version"] = "v2"


INVALID = {
    "doppelte ID": mutate_duplicate,
    "Schema fehlt": mutate_unknown_scheme,
    "Version": mutate_bad_version,
    "unbekanntes broader": mutate("adhoc:digitalisierung-breit.broader", ["aps:9.9"]),
    "APS-broader passt nicht zur ID": mutate("aps:6.1.9.broader", ["aps:2.4"]),
    "APS ohne slug": mutate("aps:6.1.9.slug", None),
    "Ad-hoc mit slug": mutate("adhoc:digitalisierung-breit.slug", "digitalisierung-breit"),
    "Ad-hoc unter Bereich": mutate("adhoc:digitalisierung-breit.broader", ["aps:6"]),
    "related überschneidet broader": mutate("adhoc:digitalisierung-breit.related", ["aps:6.1"]),
    "Selbstbezug": mutate("aps:6.1.9.related", ["aps:6.1.9"]),
    "unbekanntes related": mutate("aps:6.1.9.related", ["adhoc:gibt-es-nicht"]),
    "Mapping-Format": mutate("aps:6.1.close_match", ["48"]),
    "Mapping doppelt": mutate("aps:6.1.exact_match", ["curia:48"]),
    "merged ohne Ziel": mutate("adhoc:e-government.merged_into", None),
    "Ziel ohne merged": mutate("adhoc:ki-verwaltung.merged_into", "adhoc:digitalisierung-breit"),
    "Präfix": mutate("adhoc:digitalisierung-breit.scheme", "aps"),
    "ID-Format": mutate("aps:6.tag_id", "APS:6"),
    "APS-ID nicht numerisch": mutate("aps:6.1.10.tag_id", "aps:6.1.x"),
    "related zu einem Vorfahren": mutate("aps:6.1.9.related", ["aps:6"]),
    "related zu einem Nachfahren": mutate("aps:6.1.9.related", ["adhoc:ki-verwaltung"]),
    "unbekanntes Feld": mutate("aps:6.colour", "rot"),
    "prefLabel ohne de": mutate("aps:6.pref_label", {"fr": "Infrastructure"}),
}


@pytest.mark.parametrize("change", INVALID.values(), ids=INVALID.keys())
def test_invalid_registries_are_rejected(data, change):
    broken = copy.deepcopy(data)
    change(broken)
    with pytest.raises(ValidationError):
        build(broken)


def test_duplicate_ids_are_named(data):
    broken = copy.deepcopy(data)
    mutate_duplicate(broken)
    with pytest.raises(ValidationError, match="Doppelte tag_id: aps:2"):
        build(broken)


@pytest.mark.parametrize("content", ["registry_version: [", "- nur\n- eine Liste\n"])
def test_load_registry_reports_file_errors(tmp_path, content):
    path = tmp_path / "tags.yaml"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(RegistryError, match=re.escape(str(path))):
        load_registry(path)


def test_slug_may_repeat_because_the_file_name_contains_the_tag_id(data):
    """APS nennt Bereich 3 und Kapitel 3.1 gleich; die Dateinamen bleiben trotzdem eindeutig."""
    tag(data, "aps:2.4.1")["slug"] = "digitalisierung"
    registry = build(data)
    assert registry.get("aps:2.4.1").slug == registry.get("aps:6.1.9").slug


def test_broader_and_other_languages_do_not_change_the_hash(data):
    """Nur was die Prompts zeigen, zählt: broader und Definitionen ausser DE öffnen keine Jobs."""
    reference = {scheme: scheme_hash(build(data), scheme) for scheme in ("aps", "adhoc")}
    changed = copy.deepcopy(data)
    tag(changed, "adhoc:digitalisierung-breit")["broader"] = ["aps:6.1"]
    tag(changed, "adhoc:digitalisierung-breit")["definition"]["fr"] = "Autre définition"
    tag(changed, "aps:6.1.9")["definition"]["it"] = "Altra definizione"
    assert {scheme: scheme_hash(build(changed), scheme) for scheme in reference} == reference
