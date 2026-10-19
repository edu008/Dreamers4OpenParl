# Agent: Testfragen F21

Abnahme nach PRD F21 und Abschnitt 13: Bei 20 Testfragen (DE/FR) zitieren alle Antworten nur IDs aus Werkzeug-Ergebnissen, keine Antwort kommt ohne Treffer, kein Lauf braucht mehr als 6 Werkzeugaufrufe, und `propose_adhoc_topic` legt ohne Bestätigung nichts an.

- Fragen: [agent_questions.yaml](agent_questions.yaml), je zehn auf Deutsch und Französisch: Thema, Zählung je Parlament, Ebene oder Jahr, Kanton oder Zeitraum, Überblick, ein einzelnes Geschäft, eine Frage ohne Treffer, ein Ad-hoc-Thema.
- Lauf: `scripts/agent_eval.py` ruft `loop.run` mit `Tools` auf einer schreibgeschützten Verbindung auf (`default_transaction_read_only`), ohne Zeilen in `agent_runs` und `search_runs`. Antworten und Werkzeug-Ergebnisse liegen in `data/eval/` und nicht im Repo.
- Daten: geteilte Datenbank am 19.10.2026 mit 326'396 Geschäften. Rund 1'000 davon haben aktive Labels, alle aus 2026, denn der Klassifikationslauf lief noch. Zählungen nach Thema decken nur diese Geschäfte ab.
- Modell: `apertus-v1-5-70b` über Keera, Temperatur 0. Lauf 1 nutzt den Prompt `agent_system_v1+fa962d6a` (Stand von PR #43), Lauf 6 den Prompt `agent_system_v1+94e1e3ad` mit dem Code dieses Branches. Die Läufe 2 bis 5 dienten der Fehlersuche.

## Ergebnis

| Kriterium | Lauf 1 (vorher) | Lauf 6 (nachher) |
|---|---|---|
| Zitierte IDs nur aus Werkzeug-Ergebnissen | 20 von 20 | 20 von 20 |
| Keine Antwort ohne Treffer | 20 von 20 | 20 von 20 |
| Höchstens 6 Werkzeugaufrufe | 20 von 20 (höchstens 5) | 20 von 20 (höchstens 6) |
| `propose_adhoc_topic` legt nichts an | ja | ja |
| Zahl einem falschen Thema oder Parlament zugeschrieben | 2 (Fragen 11, 16) | 0 |
| Status `ok` / `no_results` | 14 / 6 | 16 / 4 |
| Inhaltlich richtig / teilweise / falsch | 7 / 7 / 6 | 12 / 3 / 5 |
| Mittlere Dauer | 5,0 s (höchstens 11,5 s) | 5,5 s (höchstens 11,6 s) |

Die Abnahme ist in beiden Läufen erfüllt. «Inhaltlich richtig» ist eine Durchsicht von Hand: Beantwortet die Antwort die Frage, in ihrer Sprache und mit den richtigen Filtern?

## Je Frage (Lauf 6)

| # | Sprache | Art | Status | Werkzeugaufrufe | Schritte | s | Zitate | Befund |
|---|---|---|---|---|---|---|---|---|
| 1 | de | Thema | ok | search_affairs | 2 | 7,5 | 7 | richtig; IDs als «ID: n» im Text |
| 2 | fr | Thema | ok | list_tags ×2, search_affairs | 4 | 8,6 | 7 | richtig, französisch; mit Tag nur Geschäfte aus 2026 |
| 3 | de | Thema | ok | search_affairs | 2 | 6,4 | 6 | richtig |
| 4 | fr | Thema | ok | search_affairs | 2 | 3,4 | 5 | richtig, französisch |
| 5 | de | Thema | no_results | search_affairs | 2 | 1,6 | 0 | falsch: nur CHE, ungefragt; Begriffe aus drei Sprachen ohne «or» |
| 6 | fr | Thema | ok | search_affairs | 2 | 11,6 | 10 | richtig, französisch |
| 7 | de | Zählung | ok | count_affairs ×2, list_tags | 4 | 5,6 | 0 | richtig: Bund 40, Kantone und Gemeinden getrennt; erste Tag-ID erfunden, abgewiesen |
| 8 | fr | Zählung | ok | count_affairs ×5, list_tags | 8 | 6,0 | 0 | teilweise: 68 Geschäfte 2026 stimmt, Antwort deutsch; drei Aufrufe mit falschen Argumenten |
| 9 | de | Zählung | ok | count_affairs ×2, list_tags | 4 | 5,6 | 0 | falsch: Einzelzahlen richtig, eigene Summen falsch (Kantone 7 statt 11, Gemeinden 24 statt 38) |
| 10 | fr | Zählung | ok | count_affairs, list_tags, search_affairs | 4 | 5,2 | 10 | falsch: zählt nicht, nennt Treffer der Volltextsuche |
| 11 | de | Zählung | ok | count_affairs ×2, list_tags | 4 | 4,9 | 0 | teilweise: BS und Zahlen richtig, aber year_to 2025, 2021 und 2023 fehlen, eigener Durchschnitt |
| 12 | de | Filter | no_results | search_affairs | 2 | 1,7 | 0 | falsch: «Raumplanung» findet in GE nichts, keine zweite Suche auf Französisch |
| 13 | fr | Filter | ok | search_affairs | 2 | 4,9 | 5 | richtig |
| 14 | de | Filter | no_results | search_affairs | 2 | 2,0 | 0 | falsch: «Gewässerschutz» findet in TI nichts, keine zweite Suche auf Italienisch |
| 15 | fr | Filter | ok | search_affairs | 2 | 4,9 | 4 | richtig: CHE 2025 |
| 16 | fr | Zählung | ok | count_affairs ×2, list_tags | 4 | 3,2 | 0 | richtig: 4 Geschäfte mit dem Tag; die Zählung ohne Tag wurde abgewiesen |
| 17 | de | Überblick | ok | list_tags ×2, search_affairs | 4 | 6,5 | 10 | richtig, aus 10 Treffern; read_page nicht genutzt |
| 18 | fr | einzeln | ok | get_affair | 3 | 8,3 | 1 | richtig |
| 19 | fr | leer | no_results | search_affairs | 3 | 2,2 | 0 | richtig: keine Treffer, französisch |
| 20 | de | Ad-hoc | ok | generate_keywords, propose_adhoc_topic | 3 | 10,0 | 0 | teilweise: Entwurf ohne Anlage, aber Stichwörter nur deutsch und zu allgemein (28'854 Kandidaten) |

## Fehler aus den Läufen und Änderungen

| Fehler | Lauf, Fragen | Änderung | Lauf 6 |
|---|---|---|---|
| Zählung aller Geschäfte als Antwort auf eine Themenfrage | 1: 16 | `count_affairs` ohne Tags nur mit `all_affairs: true`, sonst Fehler mit Hinweis auf `list_tags` | 16 richtig |
| Falsches Parlament: 261 (Stadt Zürich) für Basel-Stadt; «Tessin» statt TI ergab still null Treffer | 1: 11, 14 | `body_keys` beschrieben (CHE, Kantonskürzel, BFS-Nummer); unbekannte Parlamente gehen mit passenden Namen als Fehler zurück; Zählungen nennen Parlamente mit Name und Ebene | 11 zählt BS, 14 nutzt TI |
| Kantone und Gemeinden verwechselt | 1: 7, 9 | Gruppen nach Parlament tragen die Ebene; `group_by` ist erklärt | 7 richtig, 9 richtig getrennt |
| Französische Fragen deutsch beantwortet | 1: 2, 4, 8, 10 | Regel 1 steht zuerst | 2 und 4 französisch, 8 noch deutsch |
| IDs als «ID: n» statt [n] | 1: 3, 4, 13 | Regel 3; die Zitatprüfung zählt auch «ID n» | 1 schreibt noch «ID: n», geprüft |
| Ungefragte Filter (Typ, year_to 2024) | 1: 11, 15 | Regel 5 mit heutigem Datum | 15 richtig, 11 noch year_to 2025 |
| Status `no_results` trotz Entwurf | 1: 20 | Ein Entwurf belegt die Antwort | ok |
| Erfundenes Werkzeug-Ergebnis im ersten Schritt, danach Suche nach dem Erfundenen | 3 und 5: 18, 19 | Unbrauchbare und unbelegte Antworten streicht die Schleife aus dem Gespräch | 18 richtig |
| Curia-Geschäftsnummer aus der URL als ID zitiert, danach aufgegeben | 5: 18 | Regel 3 nennt `affair_id`; die Rückfrage nennt die gelieferten IDs | 18 richtig |
| Nur CHE gefiltert, obwohl die Frage kein Parlament nennt | 2: 1, 2, 4, 5 | Regel 5: ohne Parlament in der Frage keine `body_keys` | nur noch 5 |

Ein Hinweis im leeren Suchergebnis («versuche es auf Französisch») half in Lauf 3 nicht: Regel 10 lässt das Modell Werkzeug-Ergebnisse als Daten lesen, nicht als Anweisung. Er ist wieder entfernt.

## Verbleibende Fehler

1. Suche über Sprachgrenzen: Ein deutscher Begriff findet in GE oder TI nichts (12, 14). 70B sucht kein zweites Mal auf Französisch oder Italienisch, obwohl Regel 6 das verlangt, und verbindet Sprachen ohne «or» (5). Vorschlag: `search_affairs` erweitert die Suchbegriffe über die Labels der Registry (DE/FR/IT).
2. Ungefragte Filter: 5 (nur CHE), 11 (year_to 2025, obwohl die Frage «seit 2020» lautet).
3. Eigene Summen und Durchschnitte trotz Regel 4: 9 (falsch), 11. Die Einzelzahlen stammen aus `count_affairs`.
4. Zählungen schlagen fehl, wenn 70B Argumente erfindet (`query`, `limit` und `year_from: 0` bei `count_affairs`): 10 gab auf, 8 brauchte sechs Aufrufe. Die Prüfung weist jede erfundene Tag-ID und jedes falsche Argument ab, das kostet aber Aufrufe.
5. Ad-hoc: Die Stichwörter sind nur deutsch und zu allgemein, denn `propose_adhoc_topic` nimmt eine Liste für alle Sprachen. Vor `POST /v1/adhoc` prüft ein Mensch den Entwurf.
6. Zahlen nach Thema decken nur die klassifizierten Geschäfte ab (rund 1'000, alle 2026). Nach dem Volllauf neu messen.
7. Die Zitatprüfung erkennt `[n]`, `cited_ids` und «ID n», nicht aber andere Formen wie «l'affaire 340680». In allen sechs Läufen standen solche IDs auch in `cited_ids`.
8. `navigate_tree` nutzte der Agent in keinem Lauf, obwohl Regel 8 sie zuerst nennt.
