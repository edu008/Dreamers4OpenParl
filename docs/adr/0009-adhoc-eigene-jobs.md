# ADR 0009: Ad-hoc-Themen als eigene Ja/Nein-Jobs

- Status: angenommen; ersetzt in [ADR 0004](0004-scheme-hash.md) die Folge «Aktive Ad-hoc-Tags laufen in Stufe 2 von `classify:aps` mit»
- Datum: 19.10.2026
- Bezug: PRD 7.3, 7.4, 7.7, F8, F12, F16, F17; ARCHITEKTUR 3.2, 3.7, 4.5

## Kontext

Aktive Ad-hoc-Themen liefen im APS-Prompt mit: Der Worker hängte sie an die Themenliste von `classify:aps` an. Das Modell wählt dort höchstens 3 Themen aus 166. Gemessen am 19.10.2026 auf der geteilten Datenbank: Von rund 820 mit `classify_single_v2` gelabelten Geschäften trug kein einziges `adhoc:digitalisierung-breit`. Das APS-Thema «Digitalisierung» verdrängt das breite Ad-hoc-Thema, und für einen zweiten, ähnlichen Tag bleibt kein Platz. Die DVS-Liste, der Validierungsfall der Challenge, blieb dadurch leer.

Eigene Jobs `classify:adhoc:<tag>` gab es nur beim Anlegen eines Themas und beim Annehmen eines Vorschlags. Für ein bestehendes Thema fehlte jeder Weg: `classify` verweigerte Ad-hoc-Aufgaben, das Freischalten öffnete keine Jobs, der tägliche Lauf kannte nur `classify:aps`. Die in ADR 0004 vorgesehene Nachklassifizierung `reclassify:<tag_id>` war nicht gebaut. Das DVS-Thema stand zudem fest im Code (Bericht und Export).

Ein Test mit dem neuen Ja/Nein-Prompt auf 30 Stichwort-Kandidaten und 10 Geschäften der Stichprobe (19.10.2026): 8B lieferte in 34 von 40 Fällen kein gültiges JSON. 70B lieferte 1 ungültige Antwort; von den Ja-Antworten waren von Hand geprüft rund 13 von 15 richtig, in der Stichprobe alle 10 Nein richtig. Fünfmal antwortete 70B «ja» mit Konfidenz 0.0, gemeint war nein.

## Entscheid

- **Ad-hoc-Themen stehen nicht mehr im APS-Prompt.** APS bleibt der feste Katalog mit höchstens 3 Themen je Geschäft.
- **Jedes Ad-hoc-Thema bekommt je Geschäft eine Ja/Nein-Frage:** Aufgabe `classify:adhoc:<tag>`, Prompt `classify_adhoc_v1` (ein Thema, Konfidenz-Anker, wörtlicher Beleg, keine Kurzzusammenfassung, keine Vorschläge), direkt mit 70B, ohne Eskalation. Ein «ja» unter 0.5, dem tiefsten Anker, zählt als nein.
- **Eine Funktion öffnet die Jobs, alles kommt aus Registry und Läufen** (`classify.adhoc.open_adhoc_jobs`):
  - Standard: Kandidaten aus der Volltextsuche und die 2 %-Stichprobe der übrigen Geschäfte (PRD 7.4). Die Stichwörter sind die übergebenen, sonst die des letzten Laufs dieser Aufgabe (`classification_runs.params`), sonst die Bezeichnungen des Tags (Name, Synonyme, versteckte Bezeichnungen, Name ohne Klammerzusatz).
  - `--all`: jedes Geschäft im Scope, für einen bewussten Volllauf.
  - Versionen: `classify_adhoc_v1` und der Hash des Tags. Ändern sich Beschreibung oder Synonyme, öffnet der nächste Lauf nur die Jobs dieses Themas.
- **Aufrufer:** Anlegen (`kind adhoc`), Freischalten (`kind reclassify`), `parltopics classify --task classify:adhoc:<tag> [--all] [--keywords-file]` und der tägliche Lauf je aktivem Ad-hoc-Tag nach APS. `reclassify` ist eine Lauf-Art, keine eigene Aufgabe.
- **Das DVS-Thema ist eine Einstellung,** `DVS_TOPIC`, für Export und Bericht. Fehlt die Seite, schreibt der Export keine DVS-Liste und warnt, statt den täglichen Lauf abzubrechen. Der Bericht zählt Labels des Tags aus jeder Aufgabe.

## Folgen

- Die DVS-Liste füllt sich unabhängig vom APS-Thema «Digitalisierung». Ein neues Thema braucht keinen Code: Registry-Eintrag, Freischalten, fertig.
- Kosten je Thema: ein 70B-Aufruf je Kandidat und je Geschäft der Stichprobe. Für `adhoc:digitalisierung-breit` über den ganzen Bestand rund 7'500 Kandidaten und 6'400 Geschäfte der Stichprobe (Messung vom 19.10.2026). Der tägliche Lauf prüft nur neue oder geänderte Kandidaten.
- Ad-hoc-Jobs liefern keine Kurzzusammenfassung mehr; sie kommt aus `classify:aps`.
- Der Wechsel auf den neuen Prompt öffnet beim ersten Lauf alle erledigten Ad-hoc-Jobs im Scope neu. Die Prompt-Texte `classify_single_v3` und `classify_topics_v2` bleiben unverändert, damit kein APS-Volllauf entsteht.
- Alte Ad-hoc-Labels aus APS-Läufen bleiben aktiv, bis ein Ja/Nein-Job für dasselbe Geschäft «ja» sagt oder APS das Geschäft neu klassifiziert.

## Verworfene Alternativen

- **Eigene Aufgabe `reclassify:<tag_id>`** (ADR 0004): je Tag zwei Job-Zeilen und zwei Label-Quellen mit eigenen Regeln zum Wiedereröffnen. Die Aufgabe bleibt `classify:adhoc:<tag>`, nur die Lauf-Art heisst `reclassify`.
- **Mitlaufen mit Zwangsregel im APS-Prompt** («nenne Ad-hoc-Themen immer zusätzlich»): konkurriert weiter um dieselben Plätze, und jede Änderung am Prompt öffnet alle APS-Jobs.
- **Ja/Nein mit 8B und Eskalation:** 8B hielt das JSON-Format im Test nicht.
- **Embeddings für die Kandidaten:** weiterhin zurückgestellt (ADR 0003); die Stichprobe misst, was die Stichwortsuche verpasst.
