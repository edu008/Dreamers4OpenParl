"""Registry in die Datenbank spiegeln: tags, tag_labels, tag_relations, tag_mappings (PRD 7.2, F4).

registry/tags.yaml bleibt die einzige Quelle. Ein Sync schreibt nur Tags, deren Inhalt sich
geändert hat, und lehnt eine geänderte Datei mit unveränderter registry_version ab. Jobs öffnet er
nicht: Ein Lauf arbeitet mit dem Stand von seinem Start, ein neuer scheme_hash öffnet die Jobs erst
beim nächsten Lauf (PRD 7.7, `parltopics classify`).
"""

from dataclasses import dataclass

import psycopg
from psycopg.types.json import Jsonb

from parltopics.registry.loader import RegistryError, scheme_hash, tag_hash
from parltopics.registry.models import Registry, Tag

COLUMNS = (
    "tag_id",
    "scheme",
    "status",
    "parent_id",
    "merged_into",
    "name_de",
    "name_fr",
    "name_it",
    "name_rm",
    "desc_de",
    "desc_fr",
    "desc_it",
    "aliases",
    "unreviewed_translations",
    "match_text",
    "content_hash",
    "registry_version",
)


@dataclass(frozen=True)
class SyncResult:
    changed: bool  # False: gleiche Datei und Version wie beim letzten Sync, nichts geschrieben
    tags: int  # neue oder geänderte Tags
    scheme_hashes: dict[str, str]


def tag_row(tag: Tag, registry_version: str) -> dict:
    """Spalten von tags (Zuordnung im Kopf von 0003_wiki_skos.sql)."""
    pref, definition = tag.pref_label, tag.definition
    names = [name for name in (pref.de, pref.fr, pref.it, pref.rm) if name]
    return {
        "tag_id": tag.tag_id,
        "scheme": tag.scheme,
        "status": tag.status,
        "parent_id": tag.broader[0] if tag.scheme == "aps" and tag.broader else None,
        "merged_into": tag.merged_into,
        "name_de": pref.de,
        "name_fr": pref.fr,
        "name_it": pref.it,
        "name_rm": pref.rm,
        "desc_de": definition.de,
        "desc_fr": definition.fr,
        "desc_it": definition.it,
        "aliases": tag.alt_labels.all(),
        "unreviewed_translations": list(tag.unreviewed_translations),
        "match_text": "\n".join(dict.fromkeys([*names, *tag.alt_labels.all(), *tag.hidden_labels])),
        "content_hash": tag_hash(tag),
        "registry_version": registry_version,
    }


def label_rows(tag: Tag) -> list[tuple[str, str, str | None, str]]:
    pref = tag.pref_label.model_dump(exclude_none=True)
    rows = [(tag.tag_id, "pref", lang, label) for lang, label in pref.items()]
    rows += [
        (tag.tag_id, "alt", lang, label)
        for lang, labels in tag.alt_labels.model_dump().items()
        for label in labels
    ]
    rows += [(tag.tag_id, "hidden", None, label) for label in tag.hidden_labels]
    return [row for row in dict.fromkeys(rows) if row[3]]


def synced_version(conn: psycopg.Connection) -> str | None:
    """registry_version des letzten Syncs. Labels verweisen auf tags: vor jedem Lauf prüfen."""
    row = conn.execute(
        "SELECT registry_version FROM registry_syncs ORDER BY id DESC LIMIT 1"
    ).fetchone()
    return row[0] if row else None


def sync_registry(conn: psycopg.Connection, registry: Registry, digest: str) -> SyncResult:
    """Spiegelt die Registry in einer Transaktion. digest ist file_hash(registry/tags.yaml)."""
    version = registry.registry_version
    hashes = {scheme: scheme_hash(registry, scheme) for scheme in registry.schemes}
    # registry_version allein zählt nicht als Änderung: unveränderte Tags behalten ihre Version.
    content = COLUMNS[1:-1]
    upsert = (
        f"INSERT INTO tags AS t ({', '.join(COLUMNS)})"
        f" VALUES ({', '.join(f'%({column})s' for column in COLUMNS)})"
        " ON CONFLICT (tag_id) DO UPDATE SET "
        + ", ".join(f"{column} = EXCLUDED.{column}" for column in COLUMNS[1:])
        + ", updated_at = now()"
        f" WHERE ROW({', '.join(f't.{column}' for column in content)})"
        f" IS DISTINCT FROM ROW({', '.join(f'EXCLUDED.{column}' for column in content)})"
    )
    ids = [tag.tag_id for tag in registry.tags]
    with conn.transaction():
        last = conn.execute(
            "SELECT registry_version, file_hash FROM registry_syncs ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if last == (version, digest):
            return SyncResult(changed=False, tags=0, scheme_hashes=hashes)
        if last and last[0] == version:
            raise RegistryError(
                f"registry/tags.yaml hat sich geändert, registry_version {version} aber nicht"
            )
        cursor = conn.cursor()
        cursor.executemany(upsert, [tag_row(tag, version) for tag in registry.tags])
        changed = cursor.rowcount
        for table in ("tag_labels", "tag_relations", "tag_mappings"):
            conn.execute(f"DELETE FROM {table} WHERE tag_id = ANY(%s)", (ids,))
        cursor.executemany(
            "INSERT INTO tag_labels (tag_id, kind, language, label) VALUES (%s, %s, %s, %s)",
            [row for tag in registry.tags for row in label_rows(tag)],
        )
        cursor.executemany(
            "INSERT INTO tag_relations (tag_id, target_id, relation) VALUES (%s, %s, %s)",
            [
                (tag.tag_id, target, relation)
                for tag in registry.tags
                for relation, targets in (("broader", tag.broader), ("related", tag.related))
                for target in targets
            ],
        )
        cursor.executemany(
            "INSERT INTO tag_mappings (tag_id, target, match_type) VALUES (%s, %s, %s)",
            [
                (tag.tag_id, target, match_type)
                for tag in registry.tags
                for match_type, targets in (
                    ("exact", tag.exact_match),
                    ("close", tag.close_match),
                    ("broad", tag.broad_match),
                )
                for target in targets
            ],
        )
        conn.execute(
            "INSERT INTO registry_syncs (registry_version, file_hash, scheme_hashes)"
            " VALUES (%s, %s, %s)",
            (version, digest, Jsonb(hashes)),
        )
    return SyncResult(changed=True, tags=changed, scheme_hashes=hashes)
