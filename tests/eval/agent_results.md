# Agent: Testfragen F21

Abnahme nach PRD F21 und Abschnitt 13: Bei 20 Testfragen (DE/FR) zitieren alle Antworten nur IDs aus Werkzeug-Ergebnissen, keine Antwort kommt ohne Treffer, kein Lauf braucht mehr als 6 Werkzeugaufrufe, und `propose_adhoc_topic` legt ohne Bestätigung nichts an.

- Fragen: [agent_questions.yaml](agent_questions.yaml), je zehn auf Deutsch und Französisch: Thema, Zählung je Parlament, Ebene oder Jahr, Kanton oder Zeitraum, Überblick, ein einzelnes Geschäft, eine Frage ohne Treffer, ein Ad-hoc-Thema.
- Lauf: `scripts/agent_eval.py` ruft `loop.run` mit `Tools` auf einer schreibgeschützten Verbindung auf (`default_transaction_read_only`), ohne Zeilen in `agent_runs` und `search_runs`. Antworten und Werkzeug-Ergebnisse liegen in `data/eval/` und nicht im Repo.
- Daten: geteilte Datenbank am 19.10.2026 mit 326'396 Geschäften. 985 davon haben aktive Labels (2'489), alle aus 2026, denn der Klassifikationslauf lief noch. Zählungen nach Thema decken nur diese Geschäfte ab. In allen Läufen unten war der Stand gleich.
- Modell: `apertus-v1-5-70b` über Keera, Temperatur 0. Lauf 1 nutzt den Prompt `agent_system_v1+fa962d6a` (Stand von PR #43), Lauf 6 den Prompt `agent_system_v1+94e1e3ad` mit dem Code von PR #52. Die Läufe 2 bis 5 dienten der Fehlersuche. Die Läufe 7 bis 9 nutzen denselben Prompt und prüfen die Suche über Sprachgrenzen: 7 und 9 mit der Auffüllung in `search_affairs` (unten), 8 am selben Morgen ohne sie, sonst mit demselben Code.

## Ergebnis

| Kriterium | Lauf 1 (vorher) | Lauf 6 | Lauf 8 (ohne Auffüllung) | Lauf 7 | Lauf 9 |
|---|---|---|---|---|---|
| Zitierte IDs nur aus Werkzeug-Ergebnissen | 20 von 20 | 20 von 20 | 20 von 20 | 20 von 20 | 20 von 20 |
| Keine Antwort ohne Treffer | 20 von 20 | 20 von 20 | 20 von 20 | 20 von 20 | 20 von 20 |
| Höchstens 6 Werkzeugaufrufe | 20 von 20 (höchstens 5) | 20 von 20 (höchstens 6) | 20 von 20 (höchstens 3) | 20 von 20 (höchstens 6) | 20 von 20 (höchstens 6) |
| `propose_adhoc_topic` legt nichts an | ja | ja | ja | ja | ja |
| Zahl einem falschen Thema oder Parlament zugeschrieben | 2 (Fragen 11, 16) | 0 | 0 | 0 | 0 |
| Zahl aus Suchtreffern statt aus `count_affairs` | – | 0 | 1 (16) | 2 (10, 16) | 1 (16) |
| Fragen über Sprachgrenzen (5, 12, 14) mit zitierten Treffern | 0 von 3 | 0 von 3 | 0 von 3 | 3 von 3 | 3 von 3 |
| Status `ok` / `no_results` | 14 / 6 | 16 / 4 | 16 / 4 | 19 / 1 | 18 / 2 |
| Inhaltlich richtig / teilweise / falsch | 7 / 7 / 6 | 12 / 3 / 5 | 11 / 3 / 6 | 11 / 7 / 2 | 13 / 5 / 2 |
| Mittlere Dauer | 5,0 s (höchstens 11,5 s) | 5,5 s (höchstens 11,6 s) | 7,3 s (höchstens 18,8 s) | 8,0 s (höchstens 14,6 s) | 8,5 s (höchstens 26,2 s) |

Die Abnahme ist in allen Läufen erfüllt. «Inhaltlich richtig» ist eine Durchsicht von Hand: Beantwortet die Antwort die Frage, in ihrer Sprache und mit den richtigen Filtern?

## Suche über Sprachgrenzen (Läufe 7 bis 9)

Ursache: Der Volltext eines Geschäfts ist in seiner Sprache indexiert (`search_documents`), Titel anderer Sprachen kommen nur dazu, wo die Quelle sie hat, also meist beim Bund. In Genf sind 18'802 von 18'820 Dokumenten französisch, im Tessin 19'672 von 19'722 italienisch. «Raumplanung» findet in GE seit 2023 kein Geschäft, «aménagement du territoire» 106; «Gewässerschutz» findet in TI 2022 bis 2024 keines, «protezione delle acque» 35. Frage 5 scheiterte an der Anfrage «Hochwasser protection prévention des dangers naturels»: ohne «or» müssen alle Wörter im selben Text stehen, das ergibt auch ohne Filter null Treffer. Regel 6 verlangt Begriffe in der Sprache des Parlaments und «or»; 70B befolgt sie nicht.

`navigate_tree` findet aus zwei Gründen nichts: Der Baum führt über aktive Labels, und die gibt es nur für 985 Geschäfte aus 2026 (für TI 2022 bis 2024 also keines). Der Volltext-Rückfall sucht dann mit der ganzen Frage, deren Wörter alle im Text stehen müssen, in der Sprache der Frage.

Änderung: Findet `search_affairs` mit den Wörtern der Anfrage weniger Geschäfte als `limit`, sucht es ein zweites Mal mit den Bezeichnungen in DE, FR und IT (bevorzugt, alternativ, versteckt) des aktiven Tags, das die Anfrage am besten trifft, und füllt damit auf. «Am besten» heisst: die längsten Bezeichnungen, die als ganze Wörter in der Anfrage stehen, je Teil zwischen «or»; bei gleicher Länge gewinnt eine bevorzugte Bezeichnung. Prompt und Werkzeugbeschreibungen bleiben gleich, der erste Schritt des Modells also auch.

- Eine Erweiterung in jedem Fall wäre zu breit: In Frage 1 trifft «Verwaltung» das Thema Verwaltung, in Frage 5 «prévention» die Gesundheitspolitik, in Frage 6 «cybersécurité» auch das Sammelthema «Digitalisierung (breit)». Darum nur auffüllen, nur das beste Tag und die bevorzugte Bezeichnung vor der alternativen.
- Die Auffüllung griff in Lauf 9 bei 5 von 14 Suchen (Fragen 2, 5, 12, 14, 15). Alle übrigen Suchen und alle Zählungen lieferten dasselbe wie in Lauf 8.
- Eine Suche mit Auffüllung dauert 0,4 bis 3,2 s statt 0,1 bis 0,3 s, weil `ts_rank_cd` über die lange ODER-Anfrage rechnet. Nach Datum sortiert wären es 0,1 s, aber die Treffer passten nicht mehr (Frage 5: Hitzesommer 2026 und MeteoSchweiz, Frage 15: Gewalt an Demonstrationen).
- Fragen 7 und 16 unterscheiden sich schon im ersten Aufruf des Modells, also vor jedem Werkzeug-Ergebnis. Frage 16 sucht heute auch in Lauf 8 ohne Auffüllung, statt zu zählen; in Lauf 6 zählte sie richtig. Das ist Streuung des Modells bei gleichem Prompt, nicht die Änderung.

## Je Frage (Lauf 9)

Befund zu Lauf 9; r, t, f: richtig, teilweise, falsch in den Läufen 6, 8 und 7.

| # | Sprache | Art | Status | Werkzeugaufrufe | Schritte | s | Zitate | 6 | 8 | 7 | Befund Lauf 9 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | de | Thema | ok | search_affairs | 2 | 8,2 | 8 | r | r | r | richtig; IDs als «ID: n» im Text |
| 2 | fr | Thema | ok | list_tags ×2, search_affairs | 5 | 26,2 | 9 | r | r | r | richtig, französisch; Auffüllung im Tag Klimapolitik; eine unbekannte ID nach Rückfrage korrigiert |
| 3 | de | Thema | ok | search_affairs | 2 | 6,3 | 6 | r | r | r | richtig |
| 4 | fr | Thema | ok | search_affairs | 2 | 8,8 | 10 | r | r | r | richtig, französisch |
| 5 | de | Thema | ok | search_affairs | 2 | 9,0 | 8 | f | f | t | teilweise: acht passende Geschäfte zu Hochwasser und Naturgefahren über die Auffüllung, aber ungefragt nur CHE; Begriffe aus zwei Sprachen ohne «or» |
| 6 | fr | Thema | ok | search_affairs | 2 | 14,3 | 10 | r | r | r | richtig, französisch |
| 7 | de | Zählung | ok | count_affairs ×2, list_tags | 4 | 7,3 | 0 | r | r | t | richtig: Bund 40, Kantone und Gemeinden getrennt; erste Tag-ID erfunden, abgewiesen. Lauf 7: eigene Summe falsch |
| 8 | fr | Zählung | ok | count_affairs ×5, list_tags | 8 | 6,4 | 0 | t | f | t | teilweise: 68 Geschäfte 2026 stimmt, Antwort deutsch; drei Aufrufe mit falschen Argumenten. Lauf 8 zählte alle Geschäfte |
| 9 | de | Zählung | ok | count_affairs ×2, list_tags | 4 | 6,2 | 0 | f | t | t | richtig: alle Parlamente mit ihren Zahlen, ohne eigene Summen |
| 10 | fr | Zählung | no_results | count_affairs, list_tags, search_affairs | 4 | 4,8 | 0 | f | f | f | falsch: zählt nicht, die Werkzeuge könnten nicht je Parlament zählen |
| 11 | de | Zählung | ok | count_affairs ×2, list_tags | 4 | 4,6 | 0 | t | t | t | teilweise: BS und Zahlen richtig, aber year_to 2025, 2021 und 2023 fehlen, eigener Durchschnitt |
| 12 | de | Filter | ok | search_affairs | 2 | 6,2 | 1 | f | f | t | teilweise: [193800] aus GE von 2024 über die Auffüllung; year_from 2023 fehlt, die übrigen Treffer sind älter, darum «keine weiteren» |
| 13 | fr | Filter | ok | search_affairs | 2 | 5,6 | 5 | r | r | r | richtig |
| 14 | de | Filter | ok | search_affairs | 2 | 10,3 | 8 | f | f | r | richtig: acht Geschäfte aus TI 2022 bis 2024 über die Auffüllung (Trinkwasser, Abwasser, PFAS) |
| 15 | fr | Filter | ok | search_affairs | 2 | 13,3 | 7 | r | r | r | richtig: CHE 2025; die Auffüllung bringt 10 statt 4 Treffer |
| 16 | fr | Zählung | ok | search_affairs | 2 | 4,6 | 7 | r | f | f | falsch: zählt 7 Suchtreffer statt count_affairs mit dem Tag, ebenso Lauf 8 ohne Auffüllung |
| 17 | de | Überblick | ok | list_tags ×2, search_affairs | 4 | 5,9 | 10 | r | r | r | richtig, aus 10 Treffern; read_page nicht genutzt |
| 18 | fr | einzeln | ok | get_affair | 3 | 5,8 | 1 | r | r | r | richtig |
| 19 | fr | leer | no_results | search_affairs | 3 | 2,2 | 0 | r | r | r | richtig: keine Treffer, französisch |
| 20 | de | Ad-hoc | ok | generate_keywords, propose_adhoc_topic | 3 | 14,3 | 0 | t | t | t | teilweise: Entwurf ohne Anlage, aber Stichwörter nur deutsch und zu allgemein (41'036 Kandidaten) |

## Fehler aus den Läufen und Änderungen

| Fehler | Lauf, Fragen | Änderung | Danach |
|---|---|---|---|
| Zählung aller Geschäfte als Antwort auf eine Themenfrage | 1: 16 | `count_affairs` ohne Tags nur mit `all_affairs: true`, sonst Fehler mit Hinweis auf `list_tags` | Lauf 6: 16 richtig |
| Falsches Parlament: 261 (Stadt Zürich) für Basel-Stadt; «Tessin» statt TI ergab still null Treffer | 1: 11, 14 | `body_keys` beschrieben (CHE, Kantonskürzel, BFS-Nummer); unbekannte Parlamente gehen mit passenden Namen als Fehler zurück; Zählungen nennen Parlamente mit Name und Ebene | Lauf 6: 11 zählt BS, 14 nutzt TI |
| Kantone und Gemeinden verwechselt | 1: 7, 9 | Gruppen nach Parlament tragen die Ebene; `group_by` ist erklärt | Lauf 6: 7 richtig, 9 richtig getrennt |
| Französische Fragen deutsch beantwortet | 1: 2, 4, 8, 10 | Regel 1 steht zuerst | Lauf 6: 2 und 4 französisch, 8 noch deutsch |
| IDs als «ID: n» statt [n] | 1: 3, 4, 13 | Regel 3; die Zitatprüfung zählt auch «ID n» | Lauf 6: 1 schreibt noch «ID: n», geprüft |
| Ungefragte Filter (Typ, year_to 2024) | 1: 11, 15 | Regel 5 mit heutigem Datum | Lauf 6: 15 richtig, 11 noch year_to 2025 |
| Status `no_results` trotz Entwurf | 1: 20 | Ein Entwurf belegt die Antwort | Lauf 6: ok |
| Erfundenes Werkzeug-Ergebnis im ersten Schritt, danach Suche nach dem Erfundenen | 3 und 5: 18, 19 | Unbrauchbare und unbelegte Antworten streicht die Schleife aus dem Gespräch | Lauf 6: 18 richtig |
| Curia-Geschäftsnummer aus der URL als ID zitiert, danach aufgegeben | 5: 18 | Regel 3 nennt `affair_id`; die Rückfrage nennt die gelieferten IDs | Lauf 6: 18 richtig |
| Nur CHE gefiltert, obwohl die Frage kein Parlament nennt | 2: 1, 2, 4, 5 | Regel 5: ohne Parlament in der Frage keine `body_keys` | Lauf 6: nur noch 5 |
| Deutscher Begriff findet in GE oder TI nichts; Begriffe aus drei Sprachen ohne «or» | 6: 5, 12, 14 | `search_affairs` füllt mit den Bezeichnungen DE/FR/IT des passenden Tags auf (oben) | Läufe 7 und 9: alle drei mit Zitaten, 14 richtig |

Ein Hinweis im leeren Suchergebnis («versuche es auf Französisch») half in Lauf 3 nicht: Regel 10 lässt das Modell Werkzeug-Ergebnisse als Daten lesen, nicht als Anweisung. Er ist wieder entfernt.

## Verbleibende Fehler

1. Suche über Sprachgrenzen: Übersetzt werden nur Begriffe, die als Bezeichnung eines Tags in der Registry stehen; andere bleiben in ihrer Sprache. `navigate_tree` hat das Problem weiter (siehe oben): Sein Volltext-Rückfall sucht mit der ganzen Frage und ohne Übersetzung.
2. Ungefragte oder fehlende Filter: 5 (nur CHE), 11 (year_to 2025, obwohl die Frage «seit 2020» lautet), 12 (year_from 2023 fehlt, darum vor allem ältere Treffer).
3. Eigene Summen und Durchschnitte trotz Regel 4: 11, in Lauf 7 auch 7. Die Einzelzahlen stammen aus `count_affairs`.
4. Zählfragen ohne Zählung: 16 zählt Suchtreffer (Läufe 7 bis 9), 10 zählt gar nicht. Zählungen schlagen fehl, wenn 70B Argumente erfindet (`query`, `limit` und `year_from: 0` bei `count_affairs`): 8 braucht sechs Aufrufe. Die Prüfung weist jede erfundene Tag-ID und jedes falsche Argument ab, das kostet aber Aufrufe.
5. Streuung: Bei gleichem Prompt und Temperatur 0 wählt 70B in einzelnen Fragen einen anderen ersten Aufruf (7, 16) oder schreibt eine andere Antwort aus denselben Ergebnissen (9, 11). Eine einzelne Frage ist darum kein Beleg; die Läufe 7 bis 9 zeigen die Spannweite.
6. Ad-hoc: Die Stichwörter sind nur deutsch und zu allgemein, denn `propose_adhoc_topic` nimmt eine Liste für alle Sprachen. Vor `POST /v1/adhoc` prüft ein Mensch den Entwurf.
7. Zahlen nach Thema decken nur die klassifizierten Geschäfte ab (985, alle 2026). Nach dem Volllauf neu messen.
8. Die Zitatprüfung erkennt `[n]`, `cited_ids` und «ID n», nicht aber andere Formen wie «l'affaire 340680». In allen Läufen standen solche IDs auch in `cited_ids`.
9. `navigate_tree` nutzte der Agent in keinem Lauf, obwohl Regel 8 sie zuerst nennt.
