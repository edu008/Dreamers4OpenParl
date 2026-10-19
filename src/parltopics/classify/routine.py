"""Deterministische Regeln für Routinegeschäfte ohne LLM-Aufruf (Vorschlag B).

Rund 8 % aller Parlamentsgeschäfte sind formale Routineakte:
- Vereidigungen / Amtsgelöbnisse -> aps:1.2.4 (Parlament)
- Einbürgerungen -> aps:7.1.5 (Staatsangehörigkeit)
- Routine-Wahlen in Kommissionen/Ratsorgane & Rücktritte -> aps:1.2.4 (Parlament)
  bzw. Richter-/Staatsanwaltswahlen -> aps:1.2.6 (Judikative)
- Reine Jahresrechnungen, Staatsrechnungen und Voranschläge -> aps:8.2.1 (Budget)

Politische Vorstösse (Motion, Postulat, Interpellation, Parlamentarische Initiative,
Anfrage, Fragestunde, Gesetz) über diese Themen werden NICHT per Regel abgekürzt,
damit das LLM deren inhaltliche Forderung normal klassifiziert.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from parltopics.classify.queue import Job, Label, Pass
from parltopics.classify.schemas import Stage2Output, TagAssignment, _shorten

if TYPE_CHECKING:
    from parltopics.registry.models import Tag

ROUTINE_MODEL = "rule:routine-v1"

# Vorstoss-Typen und Stichworte, die auf ein materielles politisches Geschäft hinweisen
_POLICY_INTERVENTION_RE = re.compile(
    r"\b(?:"
    r"Motion|Postulat|Interpellation|Anfrage|Fragestunde|Anzug|Auftrag|Petition|"
    r"Parlamentarische\s+Initiative|Volksinitiative|Standesinitiative|Vernehmlassung|"
    r"Gesetzesänderung|Änderung\s+des|Revision\s+des|Totalrevision|Teilrevision"
    r")\b",
    re.IGNORECASE,
)

# 1. Vereidigung / Gelöbnis -> aps:1.2.4 (Parlament)
_OATH_RE = re.compile(
    r"^(?:\d+[\.\s\-:]+)?(?:"
    r"Vereidigung(?:en)?|Inpflichtnahme(?:n)?|Amtsgelöbnis(?:se)?|Gelöbnis(?:se)?|"
    r"Assermentation(?:s)?|Prestation\s+de\s+serment|Giuramento"
    r")\b",
    re.IGNORECASE,
)

# 2. Einbürgerung -> aps:7.1.5 (Staatsangehörigkeit)
_NATURALISATION_META_RE = re.compile(
    r"\[Metadaten:[^\]]*Typ:\s*(?:Naturalisation|Einbürgerung)\b",
    re.IGNORECASE,
)
_NATURALISATION_TITLE_RE = re.compile(
    r"^(?:\d+[\.\s\-:]+)?(?:"
    r"(?:\d+\s+)?Aufnahme(?:n)?\s+in\s+das\s+(?:Kantons-|Gemeinde-|Stadt-)?Bürgerrecht|"
    r"Erteilung\s+des\s+(?:Kantons-|Gemeinde-|Stadt-)?Bürgerrechts|"
    r"Einbürgerungsgesuch(?:e)?\b|Einbürgerung(?:en)?\s+(?:von|in|der|des)\b|"
    r"Naturalisation(?:s)?\s+(?:de|d')|Concessione\s+della\s+cittadinanza"
    r")",
    re.IGNORECASE,
)

# 3. Routine-Wahlen & Rücktritte -> aps:1.2.4 (Parlament) oder aps:1.2.6 (Judikative)
_ELECTION_TITLE_RE = re.compile(
    r"^(?:\d+[\.\s\-:]+)?(?:"
    r"Ersatzwahl(?:en)?\b|"
    r"Wahl(?:en)?\s+(?:eines\s+Mitglieds|einer\s+Person|der\s+Mitglieder|des\s+Präsidiums|"
    r"des\s+Büros|in\s+die\s+Kommission|in\s+den\s+|für\s+den\s+Rest\s+der\s+Amtsdauer)|"
    r"Rücktritt\s+(?:von|aus\s+dem|als)\b|Demission\s+(?:von|aus)\b|"
    r"Élection\s+complémentaire\b|Démission\s+de\b"
    r")",
    re.IGNORECASE,
)
_JUDICIARY_RE = re.compile(
    r"\b(?:"
    r"Gericht\w*|Richter\w*|Obergericht\w*|Bundesgericht\w*|Verwaltungsgericht\w*|"
    r"Bezirksgericht\w*|Zwangsmassnahmengericht\w*| Jugendgericht\w*|Staatsanwalt\w*|"
    r"Tribunal\w*|Juge\w*|Procureur\w*|Tribunale|Giudic\w*|Procuratore"
    r")\b",
    re.IGNORECASE,
)

# 4. Reines Jahresbudget / Voranschlag / Staatsrechnung -> aps:8.2.1 (Budget)
_BUDGET_TITLE_RE = re.compile(
    r"^(?:\d+[\.\s\-:]+)?(?:"
    r"Voranschlag\s+20\d{2}\b|Budget\s+20\d{2}\b|"
    r"Staatsrechnung\s+20\d{2}\b|Jahresrechnung\s+20\d{2}\b|"
    r"Geschäftsbericht\s+und\s+Jahresrechnung\s+20\d{2}\b|"
    r"Jahresbericht\s+und\s+Jahresrechnung\s+20\d{2}\b|"
    r"Nachtrag(?:skredit)?\s+(?:I+|1|2|3)\s+zum\s+(?:Voranschlag|Budget)\s+20\d{2}\b|"
    r"Compte(?:s)?\s+d'État\s+20\d{2}\b|Budget\s+de\s+l'État\s+20\d{2}\b|"
    r"Consuntivo\s+20\d{2}\b|Preventivo\s+20\d{2}\b"
    r")",
    re.IGNORECASE,
)


def _split_meta_and_title(text: str) -> tuple[str, str]:
    """Trennt eine allfällige [Metadaten: ...]-Zeile vom eigentlichen Titel/Text."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return "", ""
    if lines[0].startswith("[Metadaten:") and len(lines) >= 2:
        return lines[0], lines[1]
    return "", lines[0]


def _verbatim_quote(line: str, max_len: int = 200) -> str:
    """Liefert ein wörtliches Teilzitat ohne angehängte Ellipse, damit pg_trgm exakt matcht."""
    if len(line) <= max_len:
        return line
    cut = line[:max_len].rsplit(" ", 1)[0]
    return cut or line[:max_len]


def match_routine(job: Job, known: dict[str, Tag]) -> tuple[Pass, Stage2Output] | None:
    """Prüft, ob ein APS-Job ein eindeutiges Routinegeschäft ist.

    Gibt bei einem Treffer (Pass, Stage2Output) zurück, sonst None.
    """
    if job.task != "classify:aps" or not job.text:
        return None

    meta, first_line = _split_meta_and_title(job.text)
    if not first_line:
        return None

    # Politische Vorstösse (Motion, Postulat, Interpellation, Gesetzesänderung etc.)
    # werden nie per Routine-Regel abgekürzt.
    if _POLICY_INTERVENTION_RE.search(meta) or _POLICY_INTERVENTION_RE.search(first_line):
        return None

    tag_id: str | None = None
    if _OATH_RE.search(first_line):
        tag_id = "aps:1.2.4"
    elif _NATURALISATION_META_RE.search(meta) or _NATURALISATION_TITLE_RE.search(first_line):
        tag_id = "aps:7.1.5"
    elif _ELECTION_TITLE_RE.search(first_line):
        if _JUDICIARY_RE.search(first_line) and "aps:1.2.6" in known:
            tag_id = "aps:1.2.6"
        else:
            tag_id = "aps:1.2.4"
    elif _BUDGET_TITLE_RE.search(first_line):
        tag_id = "aps:8.2.1"

    if tag_id is None or tag_id not in known:
        return None

    quote = _verbatim_quote(first_line)
    summary = _shorten(first_line, 300)
    lang = job.language if job.language in ("de", "fr", "it", "rm") else "de"
    assignment = TagAssignment(
        evidence=quote,
        fit="kern_explizit",
        tag_id=tag_id,
        confidence=0.90,
    )
    output = Stage2Output(
        affair_id=job.affair_id,
        language=lang,  # type: ignore[arg-type]
        summary_de=summary,
        tags=[assignment],
        institution_tags=[],
        proposed_tags=[],
    )
    routine_pass = Pass(
        stage="8b",
        model_version=ROUTINE_MODEL,
        labels=[
            Label(
                tag_id=tag_id,
                confidence=0.90,
                evidence=quote,
                evidence_verified=True,
            )
        ],
    )
    return routine_pass, output
