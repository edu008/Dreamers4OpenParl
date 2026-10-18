"""JSON aus Modellantworten lösen: Codeblöcke, Text davor oder danach (PRD 7.3)."""

import json
import re
from typing import Any

_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


class JSONExtractionError(ValueError):
    """Die Antwort enthält kein JSON-Objekt."""


def _first_object(text: str) -> Any:
    decoder = json.JSONDecoder(strict=False)
    for index, char in enumerate(text):
        if char != "{":
            continue
        try:
            value, _ = decoder.raw_decode(text, index)
        except json.JSONDecodeError:
            continue
        return value
    return None


def extract_json(text: str) -> dict[str, Any]:
    """Gibt das erste JSON-Objekt der Antwort zurück, sonst JSONExtractionError.

    Steuerzeichen in Strings sind erlaubt (strict=False): 70B schreibt gelegentlich NUL statt
    eines Umlauts (Lauf 6, 19.10.2026). NUL fällt weg, PostgreSQL lehnt es in text ohnehin ab.
    """
    text = text.replace("\x00", "")
    candidates = [match.group(1) for match in _FENCE.finditer(text)]
    candidates.append(text)
    for candidate in candidates:
        candidate = candidate.strip()
        try:
            value = json.loads(candidate, strict=False)
        except json.JSONDecodeError:
            value = _first_object(candidate)
        if isinstance(value, dict):
            return value
    raise JSONExtractionError("Kein JSON-Objekt in der Antwort gefunden")
