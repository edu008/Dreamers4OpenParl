"""APS-Schema aus aps_topics.xlsx in die Registry übernehmen (PRD F4, F27, Anhang A).

Felder nach SKOS (ADR 0007): `pref_label` und `definition` je Sprache, `broader` mit dem
Eltern-Code und ein fester `slug` als Teil des Dateinamens der Tag-Seite (PRD 7.9).
"""

from __future__ import annotations

import copy
import datetime as dt
import re
import unicodedata
from pathlib import Path
from typing import Any

import yaml

from parltopics.registry.loader import RegistryError

HEADER = (
    "# ParlTopics Tag-Registry: einzige Quelle aller Tags, ausgerichtet an SKOS"
    " (PRD 7.2, Anhang A, ADR 0007).\n"
    "# APS-Einträge erzeugt `parltopics registry import-aps <aps_topics.xlsx>`.\n"
    "# Jede inhaltliche Änderung erhöht registry_version."
    " Neue Tags nur über Vorschläge und Review.\n"
    "# Tag-Seiten im ParlWiki werden aus der Datenbank erzeugt und sind keine zweite Registry.\n"
    "# Schreibt ein Werkzeug die Datei neu, gehen diese Kommentare verloren (ADR 0001).\n"
)

SHEETS = {
    "Domains": ("code", "domain_de", "domain_fr"),
    "Chapters": ("code", "chapter_de", "chapter_fr"),
    "Topics": ("code", "topic_de", "topic_fr"),
}

# Füllwörter fallen aus dem slug: „Verkehr und Kommunikation“ → verkehr-kommunikation.
STOPWORDS = frozenset(
    [
        "am",
        "an",
        "auf",
        "aus",
        "bei",
        "das",
        "dem",
        "den",
        "der",
        "des",
        "die",
        "fuer",
        "im",
        "in",
        "mit",
        "oder",
        "sowie",
        "ueber",
        "und",
        "vom",
        "von",
        "zum",
        "zur",
    ]
)
SLUG_MAX = 48


def aps_slug(name: str) -> str:
    """Fester, lesbarer Teil des Dateinamens aus dem deutschen Namen.

    Er muss nicht eindeutig sein, weil der Dateiname auch die Tag-ID enthält.
    """
    text = name.lower()
    for umlaut, ascii_text in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        text = text.replace(umlaut, ascii_text)
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    words = [word for word in re.split(r"[^a-z0-9]+", text) if word and word not in STOPWORDS]
    slug = ""
    for word in words:
        candidate = f"{slug}-{word}" if slug else word
        if slug and len(candidate) > SLUG_MAX:
            break
        slug = candidate
    return slug or "thema"


def _rows(path: Path) -> dict[str, list[dict[str, str]]]:
    from openpyxl import load_workbook  # nur beim Import der Tabelle, nicht in der API

    workbook = load_workbook(path, read_only=True, data_only=True)
    result: dict[str, list[dict[str, str]]] = {}
    for sheet, columns in SHEETS.items():
        if sheet not in workbook.sheetnames:
            raise RegistryError(f"{path}: Blatt {sheet!r} fehlt")
        iterator = workbook[sheet].iter_rows(values_only=True)
        header = [str(cell) if cell is not None else "" for cell in next(iterator)]
        missing = [column for column in columns if column not in header]
        if missing:
            raise RegistryError(f"{path}: Blatt {sheet!r} ohne Spalten {', '.join(missing)}")
        rows = []
        for values in iterator:
            row = {
                key: ("" if value is None else str(value).strip())
                for key, value in zip(header, values, strict=False)
            }
            if row["code"]:
                rows.append(row)
        result[sheet] = rows
    return result


def _parent(code: str) -> str | None:
    return f"aps:{code.rsplit('.', 1)[0]}" if "." in code else None


def _description(path: list[tuple[str, str | None]], lang: str) -> str | None:
    """Definition aus dem APS-Pfad. APS selbst liefert keine Beschreibungstexte."""
    names = [name for name, _ in path] if lang == "de" else [fr for _, fr in path]
    if any(name is None for name in names):
        return None
    if lang == "de":
        return f"Geschäfte zum APS-Thema «{names[-1]}» (Pfad: {' > '.join(names)})."
    return f"Objets relatifs au thème APS « {names[-1]} » (chemin : {' > '.join(names)})."


def _children_note(names: list[str], lang: str) -> str:
    """Kapitel und Bereiche haben in APS keinen Text: die Namen der Unterthemen ersetzen ihn."""
    joined = "; ".join(names)
    return f" Umfasst: {joined}." if lang == "de" else f" Comprend : {joined}."


def aps_entry(code: str, de: str, fr: str, path: list[tuple[str, str | None]]) -> dict[str, Any]:
    """Ein APS-Eintrag im SKOS-Format, ohne die Liste der Unterthemen."""
    tag: dict[str, Any] = {
        "tag_id": f"aps:{code}",
        "scheme": "aps",
        "status": "active",
        "slug": aps_slug(de),
        "pref_label": {"de": de, **({"fr": fr} if fr else {})},
    }
    definition = {"de": _description(path, "de")}
    if all(fr_name for _, fr_name in path):
        definition["fr"] = _description(path, "fr")
    tag["definition"] = definition
    parent = _parent(code)
    if parent:
        tag["broader"] = [parent]
    return tag


def build_aps_tags(xlsx: Path) -> list[dict[str, Any]]:
    """Alle APS-Einträge (Bereich, Kapitel, Thema) als Registry-Dicts, sortiert nach Code."""
    sheets = _rows(xlsx)
    domains = {r["code"]: (r["domain_de"], r["domain_fr"]) for r in sheets["Domains"]}
    chapters = {r["code"]: (r["chapter_de"], r["chapter_fr"]) for r in sheets["Chapters"]}
    topics = {r["code"]: (r["topic_de"], r["topic_fr"]) for r in sheets["Topics"]}

    def sort_key(code: str) -> list[int]:
        return [int(part) for part in code.split(".")]

    result = []
    for code in sorted([*domains, *chapters, *topics], key=sort_key):
        parts = code.split(".")
        path = [domains[parts[0]]]
        if len(parts) > 1:
            path.append(chapters[".".join(parts[:2])])
        if len(parts) > 2:
            path.append(topics[code])
        names = {1: domains, 2: chapters, 3: topics}[len(parts)][code]
        tag = aps_entry(code, names[0], names[1], path)
        if len(parts) < 3:
            children = {1: chapters, 2: topics}[len(parts)]
            kids = [v for c, v in children.items() if c.startswith(f"{code}.")]
            for index, lang in enumerate(("de", "fr")):
                if lang in tag["definition"]:
                    tag["definition"][lang] += _children_note([k[index] for k in kids], lang)
        result.append(tag)
    return result


def next_version(current: str, today: dt.date) -> str:
    """registry_version: am selben Tag zählt die Nummer hoch, sonst beginnt der Tag mit 1."""
    day, _, counter = current.partition(".")
    return f"{today.isoformat()}.{int(counter) + 1 if day == today.isoformat() else 1}"


def write_registry(data: dict[str, Any], registry_path: Path) -> None:
    body = yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=100)
    registry_path.write_text(HEADER + body, encoding="utf-8", newline="\n")


DESCRIPTIONS = "aps_descriptions.yaml"


def load_descriptions(registry_path: Path) -> dict[str, Any]:
    """Eigene Beschreibungen und Synonyme neben der Registry; fehlt die Datei, keine."""
    path = registry_path.with_name(DESCRIPTIONS)
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def apply_descriptions(
    tags: list[dict[str, Any]], descriptions: dict[str, Any]
) -> list[dict[str, Any]]:
    """Name IT, Beschreibung DE und Synonyme aus aps_descriptions.yaml über die APS-Einträge legen.

    APS selbst liefert nur Namen auf DE und FR. Bei Kapiteln und Bereichen bleibt „Umfasst: …“
    angehängt.
    """
    for tag in tags:
        entry = descriptions.get(tag["tag_id"])
        if not entry:
            continue
        if entry.get("it"):
            tag["pref_label"]["it"] = entry["it"]
        if entry.get("de"):
            children = tag["definition"]["de"].partition(" Umfasst: ")[2]
            tag["definition"]["de"] = entry["de"] + (f" Umfasst: {children}" if children else "")
        alt = {lang: labels for lang, labels in (entry.get("alt") or {}).items() if labels}
        if alt:
            tag["alt_labels"] = alt
        for field in ("close_match", "broad_match"):  # Curia-Vista-Sachbereiche (ADR 0007)
            if entry.get(field):
                tag[field] = entry[field]
    return tags


def _read(registry_path: Path) -> dict[str, Any]:
    data = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RegistryError(f"{registry_path}: erwartet ein YAML-Objekt auf oberster Ebene")
    return data


def refresh_descriptions(registry_path: Path) -> tuple[int, str]:
    """aps_descriptions.yaml auf die vorhandenen APS-Einträge anwenden, ohne aps_topics.xlsx."""
    data = _read(registry_path)
    aps = [copy.deepcopy(tag) for tag in data.get("tags", []) if tag.get("scheme") == "aps"]
    return _save_aps(data, apply_descriptions(aps, load_descriptions(registry_path)), registry_path)


def import_aps(xlsx: Path, registry_path: Path) -> tuple[int, str]:
    """APS-Tags in die Registry schreiben, andere Schemas bleiben unverändert.

    Gibt (Anzahl APS-Tags, registry_version) zurück. Die Version steigt nur bei Änderung.
    """
    data = _read(registry_path)
    aps_tags = apply_descriptions(build_aps_tags(xlsx), load_descriptions(registry_path))
    return _save_aps(data, aps_tags, registry_path)


def _save_aps(
    data: dict[str, Any], aps_tags: list[dict[str, Any]], registry_path: Path
) -> tuple[int, str]:
    others = [tag for tag in data.get("tags", []) if tag.get("scheme") != "aps"]
    old_aps = [tag for tag in data.get("tags", []) if tag.get("scheme") == "aps"]
    if old_aps == aps_tags:
        return len(aps_tags), data["registry_version"]

    data["registry_version"] = next_version(data["registry_version"], dt.date.today())
    data["tags"] = [*aps_tags, *others]
    write_registry(data, registry_path)
    return len(aps_tags), data["registry_version"]
