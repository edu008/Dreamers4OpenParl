"""Werkzeuge des Agenten: Argument-Modelle und Tool-Definitionen (PRD 7.8, ARCHITEKTUR 4.3).

Alle Werkzeuge lesen nur. `propose_adhoc_topic` liefert einen Entwurf; angelegt wird ein Thema
erst, wenn ein Mensch in der Web-App bestätigt (POST /v1/adhoc). Umgesetzt sind sie in `execute`.
"""

import json
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

MAX_TOOL_CALLS = 6
TIMEOUT_SECONDS = 60
TAGS = "Tag-IDs aus list_tags, z. B. aps:6.1.9; nur Geschäfte mit einem dieser Themen"


class ToolArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SearchAffairsArgs(ToolArgs):
    """Volltextsuche über Titel und Klassifikationstext mit Filtern; liefert IDs und Ausschnitte."""

    query: str = Field(min_length=1, max_length=300, description="Suchbegriffe in DE, FR oder IT")
    tags: list[str] = Field(default_factory=list, max_length=10, description=TAGS)
    body_keys: list[str] = Field(
        default_factory=list, max_length=30, description="Parlamente, z. B. CHE, ZH oder 261"
    )
    year_from: int | None = Field(None, ge=1990, le=2100)
    year_to: int | None = Field(None, ge=1990, le=2100)
    affair_type: str | None = Field(None, max_length=60, description="harmonisierter Typ")
    limit: int = Field(10, ge=1, le=20)


class ListTagsArgs(ToolArgs):
    """Passende Tags in der Registry finden (Name, Alias, Beschreibung)."""

    query: str = Field(min_length=1, max_length=100)
    scheme: Literal["aps", "adhoc"] | None = None
    limit: int = Field(10, ge=1, le=20)


class GetAffairArgs(ToolArgs):
    """Ein Geschäft mit gekürztem Text, Tags, Konfidenz, Beleg und Quelle."""

    affair_id: int = Field(ge=1)


class CountAffairsArgs(ToolArgs):
    """Geschäfte zählen, gruppiert nach Parlament, Ebene oder Jahr."""

    group_by: Literal["body_key", "level", "year"]
    tags: list[str] = Field(default_factory=list, max_length=10, description=TAGS)
    body_keys: list[str] = Field(default_factory=list, max_length=30)
    year_from: int | None = Field(None, ge=1990, le=2100)
    year_to: int | None = Field(None, ge=1990, le=2100)


class GenerateKeywordsArgs(ToolArgs):
    """Stichwörter und Phrasen in DE, FR und IT für ein Ad-hoc-Thema erzeugen."""

    name: str = Field(min_length=2, max_length=120)
    description: str = Field(min_length=10, max_length=2000)


class NavigateTreeArgs(ToolArgs):
    """Navigationssuche durch den Seitenbaum (Heart bis Geschäfte); liefert Suchweg und Treffer."""

    query: str = Field(min_length=1, max_length=300)


class ReadPageArgs(ToolArgs):
    """Eine Wiki-Seite lesen: Kurzzusammenfassung, Aussagen mit Belegen, Kennzahlen, Unterseiten."""

    page_id: str = Field(min_length=1, max_length=120, description="heart oder eine Tag-ID")


class ProposeAdhocTopicArgs(ToolArgs):
    """Entwurf eines Ad-hoc-Themas. Legt nichts an; die Web-App fragt einen Menschen."""

    name: str = Field(min_length=2, max_length=120)
    description: str = Field(min_length=10, max_length=2000)
    keywords: list[str] = Field(min_length=1, max_length=60)


@dataclass(frozen=True)
class ToolSpec:
    name: str
    args: type[ToolArgs]
    writes: bool = False


TOOLS: tuple[ToolSpec, ...] = (
    ToolSpec("search_affairs", SearchAffairsArgs),
    ToolSpec("list_tags", ListTagsArgs),
    ToolSpec("get_affair", GetAffairArgs),
    ToolSpec("count_affairs", CountAffairsArgs),
    ToolSpec("navigate_tree", NavigateTreeArgs),
    ToolSpec("read_page", ReadPageArgs),
    ToolSpec("generate_keywords", GenerateKeywordsArgs),
    ToolSpec("propose_adhoc_topic", ProposeAdhocTopicArgs),
)


class UnknownToolError(ValueError):
    """Das Modell hat ein Werkzeug verlangt, das es nicht gibt."""


class ToolError(ValueError):
    """Ein Werkzeug lehnt die Argumente ab; die Meldung geht an das Modell zurück."""


def tool_definitions() -> list[dict[str, Any]]:
    """Tool-Liste im OpenAI-Format für chat.completions(tools=...)."""
    return [
        {
            "type": "function",
            "function": {
                "name": spec.name,
                "description": (spec.args.__doc__ or "").strip(),
                "parameters": spec.args.model_json_schema(),
            },
        }
        for spec in TOOLS
    ]


def parse_tool_call(name: str, arguments: str | dict[str, Any]) -> ToolArgs:
    """Werkzeugaufruf des Modells validieren. Ungültige Argumente lösen ValidationError aus."""
    spec = next((spec for spec in TOOLS if spec.name == name), None)
    if spec is None:
        raise UnknownToolError(f"Unbekanntes Werkzeug: {name}")
    data = json.loads(arguments) if isinstance(arguments, str) else arguments
    return spec.args.model_validate(data)
