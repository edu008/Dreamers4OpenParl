"""Ad-hoc-Tags in der Registry anlegen und freischalten (PRD 7.4, F8)."""

import datetime as dt
import shutil
from pathlib import Path

import pytest

from parltopics.registry import RegistryError, load_registry
from parltopics.registry.edit import add_adhoc_tag, adhoc_id, set_status

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "tags_example.yaml"
TODAY = dt.date(2026, 10, 18)


@pytest.fixture
def registry_file(tmp_path):
    path = tmp_path / "tags.yaml"
    shutil.copy(FIXTURE, path)
    return path


def test_adhoc_id_spells_out_umlauts_and_drops_filler_words():
    assert adhoc_id("Förderung der Velowege") == "adhoc:foerderung-velowege"


def test_add_an_adhoc_tag_as_proposed_and_activate_it(registry_file):
    tag_id, registry = add_adhoc_tag(
        registry_file,
        name_de="Velowege",
        definition_de="Geschäfte zu Velowegen",
        by="Mia",
        broader=["aps:6.1"],
        today=TODAY,
    )
    assert (tag_id, registry.registry_version) == ("adhoc:velowege", "2026-10-18.4")
    tag = load_registry(registry_file).get(tag_id)
    assert (tag.status, tag.pref_label.de, tag.broader) == ("proposed", "Velowege", ["aps:6.1"])
    assert (tag.created.by, tag.created.at) == ("Mia", TODAY)
    assert registry_file.read_text(encoding="utf-8").startswith("# ParlTopics Tag-Registry")

    active = set_status(registry_file, tag_id, "active", today=dt.date(2026, 10, 19))
    assert (active.get(tag_id).status, active.registry_version) == ("active", "2026-10-19.1")


def test_invalid_changes_keep_the_old_file(registry_file):
    before = registry_file.read_bytes()
    with pytest.raises(RegistryError, match="gibt es schon"):
        add_adhoc_tag(registry_file, name_de="Digitalisierung breit", definition_de="x", by="M")
    with pytest.raises(RegistryError):
        add_adhoc_tag(registry_file, name_de="Neu", definition_de="x", by="M", broader=["aps:9.9"])
    with pytest.raises(RegistryError, match="kein Ad-hoc-Tag"):
        set_status(registry_file, "aps:6.1.9", "retired")
    assert registry_file.read_bytes() == before
    assert not list(registry_file.parent.glob(".*.new"))
