"""Ad-hoc-Tags in der Registry anlegen, freischalten und zurückziehen (PRD 7.4, F7, F8, F10).

Wie `registry import-aps` schreibt das die ganze Datei kanonisch neu (write_registry) und erhöht
registry_version. Die neue Fassung muss sich laden lassen, sonst bleibt die alte: Sie entsteht
daneben und ersetzt die Datei erst nach der Prüfung. Danach gehört sie mit sync_registry in die
Datenbank. Jeder Statuswechsel nach dem Anlegen steht mit Name und Zeit unter changes.
"""

import datetime as dt
import os
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml

from parltopics.registry.aps_import import aps_slug, next_version, write_registry
from parltopics.registry.loader import RegistryError, load_registry
from parltopics.registry.models import Registry

_LOCK = threading.Lock()  # Änderungen aus mehreren Threads der API nacheinander


class TagExists(RegistryError):
    """Das Tag steht schon in der Registry."""


def adhoc_id(name: str) -> str:
    """adhoc:<name> aus dem deutschen Namen, umgeschrieben wie die APS-slugs."""
    return f"adhoc:{aps_slug(name)}"


def add_adhoc_tag(
    path: Path,
    *,
    name_de: str,
    definition_de: str,
    by: str,
    broader: list[str] | None = None,
    proposal: dict[str, Any] | None = None,
    today: dt.date | None = None,
) -> tuple[str, Registry]:
    """Legt ein Ad-hoc-Tag mit Status proposed an; gibt die Tag-ID und die neue Registry zurück.

    Ein zurückgezogenes Tag gleicher ID kommt mit dem neuen Inhalt als proposed zurück.
    """
    tag_id = adhoc_id(name_de)
    entry: dict[str, Any] = {
        "tag_id": tag_id,
        "scheme": "adhoc",
        "status": "proposed",
        "pref_label": {"de": name_de},
        "definition": {"de": definition_de},
        "broader": broader or [],
        "created": {"at": (today or dt.date.today()).isoformat(), "by": by},
    }
    if proposal:
        entry["proposal"] = proposal

    def change(data: dict[str, Any]) -> None:
        old = next((tag for tag in data["tags"] if tag.get("tag_id") == tag_id), None)
        if old is None:
            data["tags"].append(entry)
            return
        if old.get("status") != "retired":
            raise TagExists(f"{tag_id} gibt es schon in der Registry")
        old["pref_label"]["de"] = name_de
        old["definition"]["de"] = definition_de
        old["broader"] = entry["broader"]
        if proposal:
            old["proposal"] = proposal
        _step(old, by, "proposed")

    return tag_id, _edit(path, change, today)


def set_status(
    path: Path, tag_id: str, status: str, *, by: str, today: dt.date | None = None
) -> Registry:
    """Setzt den Status eines Ad-hoc-Tags, etwa proposed → active, wenn es sich bewährt hat."""

    def change(data: dict[str, Any]) -> None:
        tag = next((tag for tag in data["tags"] if tag.get("tag_id") == tag_id), None)
        if tag is None or tag.get("scheme") != "adhoc":
            raise RegistryError(f"{tag_id} ist kein Ad-hoc-Tag der Registry")
        _step(tag, by, status)

    return _edit(path, change, today)


def _step(tag: dict[str, Any], by: str, status: str) -> None:
    tag["status"] = status
    at = dt.datetime.now().astimezone().isoformat(timespec="seconds")
    tag.setdefault("changes", []).append({"at": at, "by": by, "status": status})


def _edit(path: Path, change: Callable[[dict[str, Any]], None], today: dt.date | None) -> Registry:
    with _LOCK:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        change(data)
        data["registry_version"] = next_version(
            str(data["registry_version"]), today or dt.date.today()
        )
        draft = path.with_name(f".{path.name}.new")
        write_registry(data, draft)
        try:
            registry = load_registry(draft)
        except RegistryError:
            draft.unlink(missing_ok=True)
            raise
        os.replace(draft, path)
        return registry
