"""Lexikalisches Hybrid-Routing für die Themenklassifikation (PRD 7.3, ADR 0007).

Scannt den Vorstosstext vor Stufe 2 deterministisch gegen die Bezeichnungen (pref_label,
alt_labels) aller 165 APS-Themen. Gefundene Themen werden direkt zur Kandidatenmenge ergänzt.
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from parltopics.registry.models import Tag

# Allgemeine Parlaments- und Sprach-Stoppwörter, die nicht isoliert als Thema matchen dürfen
STOPWORDS = {
    "bund",
    "bundesrat",
    "regierungsrat",
    "stadtrat",
    "gemeinderat",
    "kantonsrat",
    "grosser rat",
    "landrat",
    "stadtparlament",
    "exekutive",
    "verwaltung",
    "kommission",
    "schweiz",
    "schweizer",
    "schweizerische",
    "kanton",
    "kantone",
    "kantonal",
    "gemeinde",
    "gemeinden",
    "gesetz",
    "gesetze",
    "änderung",
    "revision",
    "bericht",
    "motion",
    "postulat",
    "interpellation",
    "parlament",
    "politik",
    "massnahme",
    "massnahmen",
    "förderung",
    "stärkung",
    "fragen",
    "problem",
    "probleme",
    "allgemein",
    "suisse",
    "confédération",
    "conseil fédéral",
    "conseil d'etat",
    "grand conseil",
    "conseil communal",
    "conseil municipal",
    "canton",
    "cantons",
    "commune",
    "communes",
    "loi",
    "politique",
    "svizzera",
    "consiglio federale",
    "consiglio di stato",
    "gran consiglio",
    "cantone",
    "comune",
    "legge",
}

SHORT_ALLOWLIST = {
    "kvg",
    "lamal",
    "ivg",
    "ai",
    "svg",
    "uvg",
    "laa",
    "bvg",
    "lpp",
    "ahv",
    "avs",
    "alv",
    "ac",
    "stgb",
    "cp",
    "zgb",
    "cc",
    "co2",
    "öv",
    "tp",
    "sbb",
    "cff",
    "ffs",
    "e-id",
    "ki",
    "ia",
    "it",
    "ict",
}


def _clean_term(term: str) -> str:
    """Bereinigt einen Begriff von typografischen Sonderzeichen für den Matcher."""
    return term.strip(" «»\"'()[],.:;").lower()


class LexicalMatcher:
    """Sucht in Texten nach Fachbegriffen der APS-Themen."""

    def __init__(self, tags: list[Tag]) -> None:
        term_to_tags: dict[str, list[Tag]] = defaultdict(list)
        for tag in tags:
            terms: set[str] = set()
            for label in (tag.pref_label.de, tag.pref_label.fr, tag.pref_label.it):
                if label:
                    terms.add(label)
            terms.update(tag.alt_labels.all())

            for raw in terms:
                cleaned = _clean_term(raw)
                if not cleaned:
                    continue
                if len(cleaned) < 3 and cleaned not in SHORT_ALLOWLIST:
                    continue
                if cleaned in STOPWORDS:
                    continue
                term_to_tags[cleaned].append(tag)

        # Nach Länge absteigend sortieren, damit längere Phrasen Vorrang haben
        sorted_terms = sorted(term_to_tags.keys(), key=lambda t: len(t), reverse=True)
        self._term_to_tags = term_to_tags
        long_terms = [t for t in sorted_terms if len(t) >= 4]
        short_terms = [t for t in sorted_terms if len(t) < 4]
        patterns = []
        if long_terms:
            alt_long = "|".join(re.escape(t) for t in long_terms)
            patterns.append(rf"(?<!\w)({alt_long})(?:e[snmr]?|s)?(?!\w)")
        if short_terms:
            alt_short = "|".join(re.escape(t) for t in short_terms)
            patterns.append(rf"(?<!\w)({alt_short})(?:s)?(?!\w)")
        if patterns:
            pattern = "|".join(patterns)
            self._pattern: re.Pattern | None = re.compile(pattern, re.IGNORECASE)
        else:
            self._pattern = None

    def match(self, text: str) -> list[Tag]:
        """Gibt alle Themen zurück, deren Fachbegriffe im Text vorkommen."""
        if not text or not self._pattern:
            return []
        matched_tags: dict[str, Tag] = {}
        for match in self._pattern.finditer(text):
            found = next((m for m in match.groups() if m is not None), None)
            if not found:
                continue
            found_term = _clean_term(found)
            for tag in self._term_to_tags.get(found_term, []):
                matched_tags[tag.tag_id] = tag
        return list(matched_tags.values())
