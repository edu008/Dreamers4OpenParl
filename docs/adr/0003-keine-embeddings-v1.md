# ADR 0003: Keine Embeddings in Version 1

- Status: angenommen
- Datum: 18.10.2026
- Bezug: PRD 3 (Nicht-Ziele), 7.4

## Kontext

Das Lösungskonzept „Hybrid“ sah Embeddings und Kandidaten per Vektorsuche vor. Das bedeutet ein zusätzliches Embedding-Modell, das auch im Air-Gap verfügbar sein muss, und einen weiteren Pfad, der kalibriert werden will.

## Entscheid

Version 1 kommt ohne Embeddings aus. Die Registry mit Beschreibungen ersetzt die Themenvektoren. Kandidaten für Ad-hoc-Themen kommen aus der PostgreSQL-Volltextsuche mit Stichwörtern, die Apertus 70B erzeugt, plus einer Zufallsstichprobe.

## Folgen

- Kein zweites Modell, kein Vektorindex, weniger Teile im Air-Gap-Bundle.
- Geschäfte ohne Stichworttreffer werden bei Ad-hoc-Themen erst beim nächsten Volllauf erfasst. Die Stichprobe misst, wie gross diese Lücke ist (Kandidaten-Recall).
- `pgvector` ist im Datenbank-Image vorhanden und als Extension angelegt, damit der Umstieg später keine Infrastruktur-Änderung braucht.

## Wann neu entscheiden

Wenn der Kandidaten-Recall unter 0.95 fällt oder die Registry für den Prompt zu gross wird.
