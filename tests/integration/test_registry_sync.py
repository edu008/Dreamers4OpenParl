"""Registry-Sync gegen ein echtes PostgreSQL (PRD F4, F27)."""

from pathlib import Path

import pytest

from parltopics.db import migrate
from parltopics.registry import RegistryError, file_hash, load_registry
from parltopics.registry.sync import sync_registry

pytestmark = pytest.mark.integration

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "tags_example.yaml"


def test_sync_mirrors_the_registry_and_is_idempotent(conn, repo_root):
    migrate(conn, repo_root / "migrations")
    registry = load_registry(FIXTURE)
    first = sync_registry(conn, registry, file_hash(FIXTURE))
    assert first.changed
    assert first.tags == len(registry.tags) == 10
    assert set(first.scheme_hashes) == {"aps", "adhoc"}

    parent, name_it, aliases, match_text = conn.execute(
        "SELECT parent_id, name_it, aliases, match_text FROM tags WHERE tag_id = 'aps:6.1.9'"
    ).fetchone()
    assert (parent, name_it) == ("aps:6.1", "Digitalizzazione")
    assert aliases == ["Digitale Transformation", "E-Government"]
    assert "Digitalisirung" in match_text
    labels = conn.execute(
        "SELECT kind, language, label FROM tag_labels WHERE tag_id = 'aps:6.1.9'"
    ).fetchall()
    assert len(labels) == 6  # pref de/fr/it, zwei alt, ein hidden
    assert ("hidden", None, "Digitalisirung") in labels
    relation = "SELECT relation FROM tag_relations WHERE tag_id = %s AND target_id = %s"
    assert conn.execute(relation, ("aps:6.1.9", "adhoc:digitalisierung-breit")).fetchone() == (
        "related",
    )
    assert conn.execute(relation, ("aps:6.1.9", "aps:6.1")).fetchone() == ("broader",)
    mapping = "SELECT match_type FROM tag_mappings WHERE tag_id = 'aps:6.1' AND target = 'curia:48'"
    assert conn.execute(mapping).fetchone() == ("close",)
    adhoc = "SELECT parent_id FROM tags WHERE tag_id = 'adhoc:digitalisierung-breit'"
    assert conn.execute(adhoc).fetchone() == (None,)

    updated = conn.execute("SELECT max(updated_at) FROM tags").fetchone()
    second = sync_registry(conn, registry, file_hash(FIXTURE))
    assert not second.changed
    assert conn.execute("SELECT max(updated_at) FROM tags").fetchone() == updated
    assert conn.execute("SELECT count(*) FROM registry_syncs").fetchone() == (1,)


def test_changed_file_needs_a_new_registry_version(conn, repo_root, tmp_path):
    migrate(conn, repo_root / "migrations")
    sync_registry(conn, load_registry(FIXTURE), file_hash(FIXTURE))
    path = tmp_path / "tags.yaml"
    text = FIXTURE.read_text(encoding="utf-8").replace("Breite Definition", "Neue Definition")
    path.write_text(text, encoding="utf-8")
    with pytest.raises(RegistryError, match="registry_version"):
        sync_registry(conn, load_registry(path), file_hash(path))

    path.write_text(text.replace('"2026-10-18.3"', '"2026-10-18.4"'), encoding="utf-8")
    result = sync_registry(conn, load_registry(path), file_hash(path))
    assert result.changed
    assert result.tags == 1
    version = "SELECT desc_de, registry_version FROM tags WHERE tag_id = %s"
    assert conn.execute(version, ("adhoc:digitalisierung-breit",)).fetchone() == (
        "Neue Definition (Testdaten)",
        "2026-10-18.4",
    )
    assert conn.execute(version, ("aps:6.1.9",)).fetchone()[1] == "2026-10-18.3"
