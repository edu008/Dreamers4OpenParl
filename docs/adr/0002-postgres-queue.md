# ADR 0002: PostgreSQL als Job-Queue statt Redis oder Celery

- Status: angenommen
- Datum: 18.10.2026
- Bezug: PRD 7.7, F18, F19, ARCHITEKTUR.md 3.2

## Kontext

Die Klassifikation braucht eine Warteschlange mit Status je Geschäft und Aufgabe, parallele Worker, Wiederaufnahme nach Abbruch und ein Protokoll. Der Betrieb muss air-gap-fähig und mit wenig Komponenten auskommen.

## Entscheid

Die Tabelle `classification_jobs` ist die Warteschlange. Worker übernehmen Jobs mit `SELECT … FOR UPDATE SKIP LOCKED`, erneuern einen Heartbeat und schreiben ihr Ergebnis in derselben Transaktion wie den Statuswechsel, abgesichert durch eine Besitzprüfung. Ein Postgres Advisory Lock verhindert zwei gleichzeitige Läufe derselben Aufgabe.

## Folgen

- Keine zusätzliche Komponente im Image und im Bundle.
- Status und Ergebnis sind transaktional konsistent: Ein Job ist genau dann `done`, wenn seine Labels geschrieben sind.
- Fortschritt und Fehler sind mit SQL abfragbar (`GET /v1/jobs/summary`).
- Der Durchsatz der Queue liegt weit über dem, was der LLM-Endpunkt verarbeitet; die Queue ist nicht der Engpass.

## Verworfene Alternativen

- **Redis mit RQ oder Celery:** eine weitere Komponente, Status und Ergebnis in zwei Systemen, Konsistenz nur mit Zusatzaufwand.
- **Nur asyncio im Prozess:** keine Wiederaufnahme nach Abbruch, keine mehreren Prozesse.
