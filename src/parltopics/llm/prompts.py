"""Versionierte Prompt-Dateien aus prompts/ laden und rendern (prompts/README.md, PRD 7.3).

prompt_version ist der Dateiname ohne Endung plus die ersten 8 Zeichen des SHA-256 über den
Inhalt, z. B. classify_topics_v1+3f2a9c1d. Gehasht wird der eingelesene Text: read_text wandelt
Windows-Zeilenenden (CRLF) in LF, ein Checkout unter Windows ergibt also dieselbe Version.
"""

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from jinja2 import Environment, StrictUndefined, Template

ENV = Environment(undefined=StrictUndefined, keep_trailing_newline=True)
_SECTION = re.compile(r"^## (system|user)\s*$", re.MULTILINE)


def split_prompt(text: str) -> tuple[dict[str, Any], dict[str, str]]:
    """Kopf (YAML zwischen ---) und die Abschnitte system und user einer Prompt-Datei."""
    _, header, body = text.split("---", 2)
    parts = _SECTION.split(body)
    return yaml.safe_load(header), dict(zip(parts[1::2], parts[2::2], strict=True))


@dataclass(frozen=True)
class Prompt:
    name: str
    version: str
    system: Template
    user: Template

    def messages(self, system: dict[str, Any], user: dict[str, Any]) -> list[dict[str, str]]:
        """Gleichbleibende Teile in der System-Nachricht, das Geschäft in der User-Nachricht."""
        return [
            {"role": "system", "content": self.system.render(**system).strip()},
            {"role": "user", "content": self.user.render(**user).strip()},
        ]


def load_prompt(prompts_dir: Path, name: str) -> Prompt:
    text = (prompts_dir / f"{name}.md").read_text(encoding="utf-8")
    _, sections = split_prompt(text)
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:8]
    return Prompt(
        name=name,
        version=f"{name}+{digest}",
        system=ENV.from_string(sections["system"]),
        user=ENV.from_string(sections["user"]),
    )
