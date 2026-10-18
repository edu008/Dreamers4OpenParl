"""Erzeugt docs/architecture/src/07-datenmodell.json aus den SQL-Migrationen.

Aufruf: uv run python scripts/erd_from_sql.py, danach make diagrams.

Ausgewertet werden die CREATE-TABLE-Anweisungen aller Dateien in migrations/. ALTER TABLE wird
nicht ausgewertet; das Skript bricht dann mit einem Hinweis ab. Neue Tabellen brauchen einen
Platz in LAYOUT (Zeile, Spalte, Domäne), gezeichnete Beziehungen stehen in DRAWN.
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "migrations"
OUTPUT = ROOT / "docs" / "architecture" / "src" / "07-datenmodell.json"
STOP_WORDS = {"NOT", "NULL", "PRIMARY", "REFERENCES", "UNIQUE", "DEFAULT", "CHECK", "DEFERRABLE"}

# Tabelle: (Zeile, Spalte, Domäne). Eine Domäne füllt ein Rechteck im Raster (Archify-Regel).
LAYOUT = {
    "classification_jobs": (0, 0, "Steuerung"),
    "classification_runs": (1, 0, "Steuerung"),
    "job_events": (2, 0, "Steuerung"),
    "affairs": (0, 1, "Geschäft"),
    "affair_inputs": (1, 1, "Geschäft"),
    "search_documents": (2, 1, "Geschäft"),
    "affair_tags": (0, 2, "Labels und Review"),
    "affair_summaries": (1, 2, "Labels und Review"),
    "reviews": (2, 2, "Labels und Review"),
    "tag_proposals": (3, 2, "Vorschläge"),
    "tag_proposal_raw": (4, 2, "Vorschläge"),
    "tag_proposal_affairs": (5, 2, "Vorschläge"),
    "tags": (0, 3, "Registry"),
    "tag_labels": (1, 3, "Registry"),
    "tag_relations": (2, 3, "Registry"),
    "tag_mappings": (3, 3, "Registry"),
    "registry_syncs": (4, 3, "Registry"),
    "wiki_pages": (0, 4, "Wiki"),
    "wiki_page_events": (1, 4, "Wiki"),
    "search_runs": (2, 4, "Suche und Agent"),
    "agent_runs": (3, 4, "Suche und Agent"),
    "bodies": (0, 5, "Quelldaten"),
    "affair_texts": (1, 5, "Quelldaten"),
    "affair_docs": (2, 5, "Quelldaten"),
}

# Gezeichnete Beziehungen (Kind-Tabelle, Fremdschlüssel). run_id-Verweise und Selbstverweise
# bleiben ohne Linie, damit das Diagramm lesbar bleibt (siehe Karte "Lesehilfe").
DRAWN = [
    ("classification_jobs", "affair_id"),
    ("classification_jobs", "run_id"),
    ("affair_inputs", "affair_id"),
    ("search_documents", "affair_id"),
    ("affair_tags", "affair_id"),
    ("affair_tags", "tag_id"),
    ("affair_summaries", "affair_id"),
    ("reviews", "affair_tag_id"),
    ("reviews", "affair_id"),
    ("reviews", "new_tag_id"),
    ("tag_proposals", "related_tag_id"),
    ("tag_proposal_raw", "proposal_id"),
    ("tag_proposal_raw", "affair_id"),
    ("tag_proposal_affairs", "proposal_id"),
    ("tag_proposal_affairs", "affair_id"),
    ("tag_labels", "tag_id"),
    ("tag_relations", "tag_id"),
    ("tag_mappings", "tag_id"),
    ("wiki_pages", "tag_id"),
    ("search_runs", "agent_run_id"),
]

CARDS = [
    {
        "dot": "cyan",
        "title": "Lesehilfe",
        "items": [
            "Erzeugt aus migrations/ mit scripts/erd_from_sql.py; verbindlich sind die Migrationen",
            "Quelltabellen haben keine Fremdschlüssel: affair_texts.affair_id und "
            "affair_docs.parent_id verweisen fachlich auf affairs",
            "run_id in affair_tags, affair_summaries, tag_proposals und tag_proposal_raw verweist "
            "auf classification_runs; die Linien sind weggelassen",
            "Ohne Linie: tags.parent_id, tags.merged_into und tag_relations.target_id verweisen "
            "auf tags, wiki_pages.parent_id und redirect_to auf wiki_pages",
            "wiki_page_events.page_id verweist fachlich auf wiki_pages (Protokoll wie job_events)",
        ],
    },
    {
        "dot": "amber",
        "title": "Regeln",
        "items": [
            "Pro Geschäft, Tag, input_hash und prompt_version höchstens ein aktives Label; "
            "pro Geschäft und Sprache höchstens eine aktive Kurzzusammenfassung",
            "Labels und Kurzzusammenfassungen werden nie gelöscht, nur auf superseded oder "
            "rejected gesetzt",
            "Ein Job oder eine Seite im Status pending trägt immer worker_id und locked_at",
            "Genau eine Seite heart ohne Tag und ohne Eltern; jede andere Seite gehört zu "
            "genau einem Tag",
            "Pro Tag-Paar nur broader oder related",
            "Eine Suche ohne Treffer speichert keine Antwort",
        ],
    },
    {
        "dot": "emerald",
        "title": "Gestrichelte Linien",
        "items": [
            "Gestrichelt: nicht identifizierende Beziehung, der Fremdschlüssel ist nicht Teil "
            "des Primärschlüssels",
            "Durchgezogen: identifizierend, z. B. classification_jobs (affair_id, task)",
        ],
    },
]


def parse_tables(sql: str) -> dict[str, list[dict]]:
    tables = {}
    for name, body in re.findall(r"CREATE TABLE (\w+) \((.*?)\n\);", sql, flags=re.DOTALL):
        columns, table_pk = [], []
        for raw in body.split("\n"):
            line = raw.split("--")[0].strip().rstrip(",")
            if not line:
                continue
            if line.startswith("PRIMARY KEY"):
                inner = re.search(r"\((.*)\)", line).group(1)
                table_pk = [c.strip() for c in inner.split(",")]
                continue
            if line.startswith(("CHECK", "UNIQUE (")):
                continue
            tokens = line.split()
            type_tokens = []
            for token in tokens[1:]:
                if token in STOP_WORDS:
                    break
                type_tokens.append(token)
            keys, reference = [], None
            if "PRIMARY KEY" in line:
                keys.append("pk")
            if re.search(r"\bUNIQUE\b", line):
                keys.append("uk")
            match = re.search(r"REFERENCES (\w+) \((\w+)\)", line)
            if match:
                keys.append("fk")
                reference = f"{match.group(1)}.{match.group(2)}"
            columns.append(
                {
                    "name": tokens[0],
                    "type": re.sub(r",\s+", ",", " ".join(type_tokens)),
                    "keys": keys,
                    "ref": reference,
                    "not_null": "NOT NULL" in line or "PRIMARY KEY" in line,
                }
            )
        for column in columns:
            if column["name"] in table_pk:
                column["keys"].insert(0, "pk")
                column["not_null"] = True
        tables[name] = columns
    return tables


def build(tables: dict[str, list[dict]]) -> dict:
    entities = []
    for name, columns in tables.items():
        row, col, tag = LAYOUT[name]
        attributes = []
        for column in columns:
            attribute = {"name": column["name"], "type": column["type"]}
            if column["keys"]:
                keys = column["keys"]
                attribute["key"] = keys[0] if len(keys) == 1 else keys
            if column["ref"]:
                attribute["references"] = column["ref"]
            attributes.append(attribute)
        entity = {"id": name, "label": name, "tag": tag, "row": row, "col": col}
        longest = max(len(c["name"]) + len(c["type"]) for c in columns)
        if longest > 24:
            entity["width"] = int(min(300, 120 + longest * 6.2))
        entity["attributes"] = attributes
        entities.append(entity)
    entities.sort(key=lambda e: (e["col"], e["row"]))

    relationships = []
    for table, column_name in DRAWN:
        column = next(c for c in tables[table] if c["name"] == column_name)
        parent = column["ref"].split(".")[0]
        pk_columns = sum("pk" in c["keys"] for c in tables[table])
        one_to_one = column["keys"][:1] == ["pk"] and pk_columns == 1
        relationship = {
            "id": f"{table}_{column_name}",
            "from": table,
            "to": parent,
            "fromCardinality": "one" if one_to_one else "many",
            "fromOptional": True,
            "toCardinality": "one",
        }
        if not column["not_null"]:
            relationship["toOptional"] = True
        if "pk" not in column["keys"]:
            relationship["identifying"] = False
        relationships.append(relationship)

    return {
        "schema_version": 1,
        "diagram_type": "erd",
        "meta": {
            "title": "ParlTopics – Datenmodell",
            "output": "docs/architecture/07-datenmodell.html",
            "quality_profile": "standard",
        },
        "layout": {"mode": "grid", "gapX": 80, "gapY": 44},
        "entities": entities,
        "relationships": relationships,
        "cards": CARDS,
    }


def compact_json(value, indent: int = 0) -> str:
    """JSON mit flachen Objekten auf einer Zeile, damit Diffs lesbar bleiben."""
    pad = "  " * indent
    flat = json.dumps(value, ensure_ascii=False)

    def scalar(item) -> bool:
        return not isinstance(item, dict | list) or (
            isinstance(item, list) and all(not isinstance(x, dict | list) for x in item)
        )

    if isinstance(value, dict):
        if all(scalar(item) for item in value.values()) and len(flat) <= 150:
            return flat
        items = [
            f"{pad}  {json.dumps(key, ensure_ascii=False)}: {compact_json(item, indent + 1)}"
            for key, item in value.items()
        ]
        return "{\n" + ",\n".join(items) + "\n" + pad + "}"
    if isinstance(value, list):
        if all(not isinstance(item, dict | list) for item in value) and len(flat) <= 150:
            return flat
        items = [f"{pad}  {compact_json(item, indent + 1)}" for item in value]
        return "[\n" + ",\n".join(items) + "\n" + pad + "]"
    return flat


def main() -> int:
    sql = "\n".join(p.read_text(encoding="utf-8") for p in sorted(MIGRATIONS.glob("*.sql")))
    if re.search(r"\bALTER TABLE\b", sql):
        print("ALTER TABLE gefunden: bitte das Skript erweitern oder das ERD von Hand anpassen.")
        return 1
    tables = parse_tables(sql)
    missing = sorted(set(tables) - set(LAYOUT))
    if missing:
        print(f"Ohne Platz in LAYOUT: {', '.join(missing)}")
        return 1
    OUTPUT.write_text(compact_json(build(tables)) + "\n", encoding="utf-8")
    print(f"{OUTPUT.relative_to(ROOT)}: {len(tables)} Tabellen, {len(DRAWN)} Beziehungen")
    return 0


if __name__ == "__main__":
    sys.exit(main())
