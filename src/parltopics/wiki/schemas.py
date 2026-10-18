"""Ausgabe der Seitenzusammenfassungen mit Belegpflicht (PRD 7.9, Anhang B).

Jede Aussage nennt Geschäfte oder Unterseiten, auf die sie sich stützt. Zahlen dürfen nur aus den
mitgelieferten Kennzahlen stammen. Unbelegte Aussagen werden verworfen; bleibt keine übrig, ist
die Seite `failed`.
"""

import re

from pydantic import BaseModel, ConfigDict, Field

NUMBER = re.compile(r"\d+(?:['’.,]\d+)*")


class SummaryError(ValueError):
    """Keine belegte Aussage übrig."""


class _Output(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Statement(_Output):
    text: str = Field(min_length=1, max_length=600)
    affair_ids: list[int] = Field(default_factory=list)
    page_ids: list[str] = Field(default_factory=list)


class PageSummaryOutput(_Output):
    summary_short: str = Field(min_length=1, max_length=200)
    statements: list[Statement] = Field(min_length=1)


def numbers_in(text: str) -> set[str]:
    return {re.sub(r"['’]", "", match) for match in NUMBER.findall(text)}


def parse_page_summary(
    data: dict,
    *,
    allowed_affairs: set[int],
    allowed_pages: set[str],
    allowed_numbers: set[str],
) -> tuple[PageSummaryOutput, list[Statement]]:
    """Prüft jede Aussage. Gibt die bereinigte Ausgabe und die verworfenen Aussagen zurück.

    allowed_numbers: Kennzahlen, Jahre und Länge des Zeitfensters. Die IDs der angebotenen
    Geschäfte und die Codes der angebotenen Seiten zählen automatisch dazu. SummaryError heisst:
    die Seite einmal neu anfordern, danach failed (PRD 7.9, Regel 4).
    """
    output = PageSummaryOutput.model_validate(data)
    numbers = set(allowed_numbers) | {str(affair_id) for affair_id in allowed_affairs}
    for page_id in allowed_pages:
        numbers |= numbers_in(page_id)

    def supported(statement: Statement) -> bool:
        cited = bool(statement.affair_ids or statement.page_ids)
        known = set(statement.affair_ids) <= allowed_affairs and set(statement.page_ids) <= (
            allowed_pages
        )
        return cited and known and numbers_in(statement.text) <= numbers

    kept = [s for s in output.statements if supported(s)]
    dropped = [s for s in output.statements if not supported(s)]
    if not kept:
        raise SummaryError("Keine belegte Aussage")
    if not numbers_in(output.summary_short) <= numbers:
        raise SummaryError("Kurzzusammenfassung enthält Zahlen ohne Kennzahl")
    return output.model_copy(update={"statements": kept}), dropped
