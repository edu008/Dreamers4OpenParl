"""Regeln für Routinegeschäfte: Thema aus dem Titel, ohne Modellaufruf (Vorschlag B, 19.10.2026).

Vereidigungen, Rücktritte, Einbürgerungen, Budgets und Rechnungen haben ein eindeutiges Thema. Die
Muster gelten nur am Anfang der ersten Zeile des Klassifikationstexts (Titel, inputs.compose) und
sind bewusst eng: lieber das LLM entscheiden lassen als eine Regel falsch anwenden. Labels tragen
die Stufe `rule`.
"""

import re
from dataclasses import dataclass

RULES_VERSION = "regeln-v1"
CONFIDENCE = 0.95

_JUDICIARY = re.compile(
    r"richter|juge|giudic|tribunal|gericht|staatsanwalt|procureur|procuratore", re.I
)
_YEAR = r"( der [\wäöüÄÖÜ .]+| de la [\w .]+| de l.[\w .]+)?\s*20\d\d"
_PATTERNS: list[tuple[str, str, re.Pattern[str]]] = [
    (
        "vereidigung",
        "aps:1.2.4",  # Parlament
        re.compile(
            r"^\s*(vereidigung|inpflichtnahme|prestation de serment|assermentation|giuramento)",
            re.I,
        ),
    ),
    (
        "ruecktritt",
        "aps:1.2.4",
        re.compile(r"^\s*(rücktritt|démission|dimission|dimissioni)\b", re.I),
    ),
    (
        "einbuergerung",
        "aps:7.1.5",  # Staatsangehörigkeit
        re.compile(
            r"^\s*(liste\s+(der|des)\s+)?"
            r"(einbürgerung|einbürgerungsgesuch|naturalisation|naturalizzazion)",
            re.I,
        ),
    ),
    ("budget", "aps:8.2.1", re.compile(r"^\s*(budget|voranschlag|preventivo)" + _YEAR, re.I)),
    (
        "rechnung",
        "aps:8.2.2",  # Staatsrechnung
        re.compile(
            r"^\s*(jahresrechnung|staatsrechnung|gemeinderechnung|rechnung|comptes|consuntivo)"
            + _YEAR,
            re.I,
        ),
    ),
]


@dataclass(frozen=True)
class RuleMatch:
    rule: str
    tag_id: str
    evidence: str  # die Titelzeile, auf die die Regel passte


def match_rule(text: str | None) -> RuleMatch | None:
    """Thema eines Routinegeschäfts aus der Titelzeile, sonst None (dann entscheidet das LLM)."""
    title = (text or "").split("\n", 1)[0].strip()
    for rule, tag_id, pattern in _PATTERNS:
        if pattern.search(title):
            if rule in ("vereidigung", "ruecktritt") and _JUDICIARY.search(title):
                tag_id = "aps:1.2.6"  # Judikative: Richterinnen und Richter, Staatsanwaltschaft
            return RuleMatch(rule, tag_id, title[:300])
    return None
