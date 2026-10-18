"""Laden von registry/tags.yaml und Berechnung der Hashes (PRD 7.2, ADR 0004)."""

import hashlib
import json
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from parltopics.registry.models import Registry, Scheme, Tag


class RegistryError(ValueError):
    """Die Registry-Datei ist kein gültiges YAML oder verletzt das Modell."""


def load_registry(path: Path) -> Registry:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise RegistryError(f"{path}: nicht lesbar: {error}") from error
    except yaml.YAMLError as error:
        raise RegistryError(f"{path}: kein gültiges YAML: {error}") from error
    if not isinstance(data, dict):
        raise RegistryError(f"{path}: erwartet ein YAML-Objekt auf oberster Ebene")
    try:
        return Registry.model_validate(data)
    except ValidationError as error:
        raise RegistryError(f"{path}: {error}") from error


def canonical_tag(tag: Tag) -> dict[str, Any]:
    """Die Felder, die eine Klassifikation beeinflussen. Metadaten zählen nicht.

    Die Reihenfolge der Aliasse zählt nicht; Prompts geben sie ebenfalls sortiert aus.
    """
    return {
        "tag_id": tag.tag_id,
        "parent": tag.parent,
        "names": tag.names.model_dump(exclude_none=True),
        "descriptions": tag.descriptions.model_dump(exclude_none=True),
        "aliases": sorted(tag.aliases),
    }


def _digest(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def tag_hash(tag: Tag) -> str:
    """scheme_hash für Aufgaben, die nur ein Tag nutzen (classify:adhoc:<tag>, reclassify)."""
    return _digest(canonical_tag(tag))


def scheme_hash(registry: Registry, scheme: Scheme) -> str:
    """SHA-256 über alle aktiven Einträge eines Schemas, sortiert nach tag_id."""
    tags = sorted(registry.active(scheme), key=lambda tag: tag.tag_id)
    return _digest([canonical_tag(tag) for tag in tags])


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
