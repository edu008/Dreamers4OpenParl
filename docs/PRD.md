# PRD: ParlTopics – Klassifikations-Motor, ParlWiki und OpenParlData-Add-in

| | |
|---|---|
| Stand | 18.10.2026 |
| Version | 0.3 |
| Status | Entwurf zur Abnahme |
| Änderungen | 0.2: Status je Geschäft und parallele Verarbeitung (7.7, F18, F19). 0.3: siehe „Änderungen in 0.3“ |
| Basis | Lösungskonzept „Hybrid“ vom 18.10.2026, 12:30; Datenanalyse files.openparldata.ch vom 18.10.2026 |
| Zielgruppe | Hack-Team, OpenParlData-Betreiber, DVS als Nutzer der Digitalisierungsliste |
| Begleitdokumente | [Architektur: Worker, Agent, Pipeline](ARCHITEKTUR.md) · [Air-Gap-Betrieb](AIRGAP.md) · [Entwicklung](ENTWICKLUNG.md) · [Entscheide (ADR)](adr/) · [Diagramme](architecture/README.md) |

**Änderungen in 0.3**

- Phasen: Der Umfang bleibt vollständig, der Hack ist Phase 1 (12, 16).
- Registry als YAML-Datei `registry/tags.yaml` statt `tags.md` (7.2, Anhang A, ADR 0001).
- Jobs hängen am `scheme_hash` ihres Registry-Ausschnitts statt an der globalen `registry_version`. Ein neues Ad-hoc-Tag löst keinen APS-Volllauf mehr aus (7.2, 7.7, ADR 0004).
- Zweistufiger Prompt (Kapitel → Themen) ist Vorgabe, einstufig nur noch Vergleich (7.3).
- Beleg-Prüfung unscharf statt wörtlich, Konfidenzschwelle wird kalibriert (7.3, Anhang B).
- Worker: Besitzprüfung beim Schreiben, Heartbeat, präzisierte Versuchszählung, adaptive Drosselung, Ad-hoc-Jobs nur für Kandidaten (7.7).
- Menschliche Entscheidungen haben Vorrang vor Neuklassifikation (7.3, F9).
- Datenmodell: partieller Unique-Index für aktive Labels, Rohvorschläge in `tag_proposal_raw`, Verknüpfung `tag_proposal_affairs`, Agent-Protokoll `agent_runs` (Anhang C).
- ParlWiki: Review direkt auf Geschäfts- und Themenseite, Graph-Ansicht, Markdown-Export nur für Themen und Parlamente (7.5, F13, F14, F20).
- Neu: Suche und Ad-hoc-Dialog als Tool-Calling-Agent mit Apertus 70B (7.8, F15, F21, ADR 0005).
- Air-Gap als Zielarchitektur mit Bundle, Offline-Test und den Umgebungsvariablen des Hack-Templates (5, 9, 10.3, F22).
- Metriken: Recall-Ziel je Pfad, Mapping APS ↔ Curia Vista vor der Messung abgenommen, Kalibrierung, Agent (13).
- Projektstruktur als Monorepo (Anhang D), Diagramme (Anhang E).

## 1. Zusammenfassung

ParlTopics labelt alle Geschäfte in OpenParlData (326'396 Geschäfte aus 97 Parlamenten) mit Themen. Grundlage ist eine zentrale Tag-Registry (`registry/tags.yaml`) mit dem festen Schema der Année Politique Suisse (APS) und Ad-hoc-Themen. Apertus v1.5 (8B, bei Unsicherheit 70B) ordnet jedem Geschäft passende Tags zu, mit Konfidenz und Textstelle als Beleg. Fehlt ein passendes Thema, schlägt Apertus einen neuen Tag vor. Er wird auf Duplikate geprüft und erst nach menschlicher Freigabe registriert.

ParlTopics nutzt zwei Arten von KI-Komponenten. Deterministische **Worker** klassifizieren den Bestand Geschäft für Geschäft. Der Code steuert Reihenfolge und Status, Apertus bekommt immer genau ein Geschäft. Ein **Agent** mit Apertus 70B beantwortet Suchanfragen und hilft beim Anlegen von Ad-hoc-Themen. Er ruft nur lesende Werkzeuge auf und belegt jede Aussage mit Geschäfts-IDs.

Drei Nutzungen: Themenfilter in OpenParlData (Sidecar-API und Export), ParlWiki mit Themen- und Geschäftsseiten, Review direkt auf der Seite und Graph der Verlinkungen, automatische DVS-Liste zu Digitalisierung.

Das Tool ist self-hosted (Python, PostgreSQL, Docker) und air-gap-fähig. Zur Laufzeit braucht es nur den LLM-Endpunkt aus `LLM_BASE_URL`. Im Hack ist das die OpenAI-kompatible API von Keera, im Air-Gap-Betrieb ein Apertus-Endpunkt im selben Netz.

## 2. Problem und Hintergrund

- OpenParlData harmonisiert Geschäfte, Personen, Dokumente usw. aus Bund, 26 Kantonen, 61 Städten, 8 Gemeinden und Liechtenstein. Ein **einheitliches Thema über alle Ebenen gibt es nicht.**
- Themen liegen nur verstreut vor: Bund hat 28 Curia-Vista-Sachbereiche (ca. 2 pro Geschäft, ab 2000) und bis 2014 Deskriptoren; vier Parlamente (SG, TG, Stadt Zug, ZH) publizieren eigene, untereinander inkompatible Schemata. Alle anderen Parlamente haben nichts.
- Listen wie die DVS-Liste „Politische Geschäfte Digitalisierung“ entstehen heute redaktionell (PolitMonitor) und sind nicht reproduzierbar.
- Texte sind mehrsprachig (DE/FR/IT, teils RM), enthalten HTML, und auf Kantons-/Gemeindeebene steckt der Inhalt meist in PDFs statt in Textfeldern.

## 3. Ziele und Nicht-Ziele

**Ziele**

- G1 Jedes Geschäft trägt Themen aus einem festen Schema (APS) – über alle Ebenen und Sprachen.
- G2 Ad-hoc-Themen (z. B. „Digitalisierung“) lassen sich definieren und über den gesamten Bestand auswerten; bewährte Ad-hoc-Themen werden fix übernommen.
- G3 Labels sind nachvollziehbar: Konfidenz, Textstelle als Beleg, Modell-, Prompt- und Registry-Version, Korrekturmöglichkeit direkt in der Oberfläche.
- G4 Ergebnisse sind für OpenParlData nutzbar (API, Exportdatei) und im ParlWiki sichtbar.
- G5 Qualität ist gemessen (Präzision/Recall nach Sprache und Ebene) gegen Gold-Set und Keyword-Baseline.
- G6 Vollständig self-hosted und air-gap-fähig; einzige Laufzeit-Abhängigkeit ist der LLM-Endpunkt (`LLM_BASE_URL`).
- G7 Menschliche Entscheidungen haben Vorrang: Reviewer sehen Text, Beleg und Verlinkungen, korrigieren direkt in der Web-App, und Korrekturen fliessen ins Gold-Set.

**Nicht-Ziele**

- Kein Schreiben in die Datenbank von OpenParlData; der Portal-Filter (Stufe 3) wird vom OpenParlData-Team umgesetzt.
- Kein Training oder Fine-Tuning. ParlTopics betreibt Apertus nicht selbst: Im Hack stellt Keera das Modell bereit, im Air-Gap-Betrieb stellt der Betreiber einen OpenAI-kompatiblen Apertus-Endpunkt im internen Netz (Vorlage in [AIRGAP.md](AIRGAP.md)).
- Keine Embeddings/Vektorsuche in der ersten Version (7.4, ADR 0003).
- Keine Klassifikation von Reden, News oder Abstimmungen (nur Geschäfte).
- Keine öffentliche Instanz im Hack; Nutzungsbedingungen von OpenParlData sind vorher zu klären.
- Der Agent schreibt nichts selbständig. Er schlägt vor, ein Mensch bestätigt.

## 4. Nutzer und Anwendungsfälle

| Nutzer | Anwendungsfall |
|---|---|
| OpenParlData-Portal / API-Nutzer | Geschäfte nach Thema filtern, ebenenübergreifend (Sidecar-API, später Portal-Filter) |
| DVS (Digitale Verwaltung Schweiz) | Aktuelle Liste der Digitalisierungsgeschäfte Bund + Kantone, automatisch, täglich |
| Journalisten, Forschung, Verwaltung | ParlWiki-Themenseite lesen: Zusammenfassung, Geschäfte nach Ebene/Kanton/Jahr; über den Graphen verwandte Themen und Geschäfte finden |
| Alle | Suche in natürlicher Sprache („Vorstösse zu KI in der Verwaltung seit 2024“) mit Trefferliste und belegter Kurzantwort (Agent) |
| Redaktion / Reviewer | Auf der Geschäftsseite Text, Beleg und Tags sehen und Labels direkt bestätigen, verwerfen, ersetzen oder ergänzen; Tag-Vorschläge annehmen, zusammenlegen oder ablehnen; Ad-hoc-Thema im Dialog mit dem Agenten anlegen |
| Betreiber | Täglicher Lauf, Statusübersicht, Export, Air-Gap-Bundle einspielen |

## 5. Rahmenbedingungen

| Bereich | Vorgabe |
|---|---|
| Sprache | Python 3.11+ (Container-Image: 3.12) |
| LLM | Apertus v1.5, 8B und 70B, über eine OpenAI-kompatible API (`/v1/chat/completions`). Im Hack von Keera bereitgestellt, unlimitierte Nutzung; im Air-Gap-Betrieb ein interner Endpunkt. Kein anderes LLM. |
| Konfiguration | Umgebungsvariablen nach Hack-Template: `LLM_NAME` (8B), `LLM_BASE_URL`, `LLM_API_KEY`, ergänzt um `LLM_NAME_LARGE` (70B). Vollständige Liste in `.env.example`. |
| Repository | Hack-Apertus-Template: `README.md`, `technical_report.md`, `LICENSE` (Apache-2.0) und `src/` bleiben an ihrem Ort. Monorepo nach Anhang D. Abgabe: öffentliches Repo, technischer Bericht als PDF (max. 6 Seiten), Demo-Video (max. 2 min). |
| Betrieb | Self-hosted auf einem Server (Linux, Docker Compose). Alle Komponenten Open Source und im Image enthalten. |
| Offline | Die Anwendung läuft ohne Internet. Erlaubter Netzwerkzugriff zur Laufzeit: nur der Host aus `LLM_BASE_URL` (Allowlist im HTTP-Client). Keine CDNs, Web-Fonts, Telemetrie, Paket- oder Modell-Downloads zur Laufzeit. Build und Datendownload laufen getrennt auf einem Rechner mit Internet (10.3). |
| Datenimport | Download der OpenParlData-Exporte ist ein separater Schritt (eigenes Kommando, kann auf einem anderen Rechner laufen). Die Anwendung liest ein lokales Import-Bündel. |
| Daten | OpenParlData-Exporte (`files.openparldata.ch/exports`), Hack-Datensatz (`/hackapertus`), APS-Schema (`aps_topics.xlsx`). Quelle für Bund: Parlamentsdienste (Curia Vista) via OpenParlData. |
| Lizenzen | Code: Apache-2.0 (Template). Technischer Bericht: CC-BY-4.0 (Template). Apertus: Apache 2.0. OpenParlData: Nutzungsbedingungen klären (offene Frage). APS-Schema: Quelle nennen. Fremdkomponenten im Repo: Archify (MIT, nur Dokumentation); vorgesehen für die Graph-Ansicht: force-graph (MIT). |

## 6. Datengrundlage (Stand 18.10.2026)

**Nächtlicher Export** (`/exports/`, ca. 01:38 UTC, 14 min, atomarer Austausch, `index.json` mit Dateiliste und Zeilenzahlen):

| Datei | Zeilen | Nutzung in ParlTopics |
|---|---|---|
| `affairs.ndjson.gz` | 326'396 | Grundgesamtheit: ID, `body_key`, Nummer, Titel DE/FR/IT/RM, harmonisierter Typ, Datum, Quelle-URL |
| `texts/texts_{body}.ndjson.gz` | 226'078 (19 Parlamente, CHE 237 MB) | Eingereichter Text, Begründung, Antwort BR (Bund); wenige Kantone |
| `docs/docs_{body}.ndjson.gz` | 910'298, 5.5 GB, 90.4 % mit extrahiertem Text | Input für Kantone/Gemeinden: erstes Dokument eines Geschäfts |
| `bodies.ndjson.gz` | 2'411 (97 indexiert) | Parlamente, Ebene, Sprache |

Felder: `id` = OpenParlData-ID (auch in `api.openparldata.ch/v1/affairs/{id}`), `external_id` = ID im Quellsystem, `body_key` = `CHE`, Kantonskürzel oder BFS-Nummer (z. B. `261` Stadt Zürich). Texte enthalten HTML (`<p>`, `<span style>`), auch bei `format = text`.

**Hack-Datensatz** (`/hackapertus/`, Snapshot 18.10.2026):

| Datei | Inhalt | Rolle |
|---|---|---|
| `che_affairs_keywords.*` | 70'008 Bundesgeschäfte mit Curia-Vista-Sachbereichen (28, ca. 2 pro Geschäft, 98 % ab 2000) und Deskriptoren (1996–2014) | Vergleichsdaten Bund |
| `che_affair_texts.ndjson.gz` | 210'437 Texte DE/FR/IT | Input Bund |
| `cantonal_*` | SG 6'792 (10 Sachgebiete), TG 2'382 (118 mit Code), Stadt Zug 1'343 (37 Departemente), ZH 225 Vernehmlassungen (724 freie Keywords) | Vergleichsdaten Kantone (je eigenes Schema) |
| `politmonitor_digitalisierung.csv` | 3'433 Geschäfte aus 35 Parlamenten mit Redaktions-Tag „Digitalisierung“ (CHE 1'448; 98 % 2018–2026); nur Positive | Gold-Set Recall Digitalisierung |
| `dvs_digitalisierung.csv` | 30 aktuelle Geschäfte der DVS-Liste | Abgleich DVS-Liste |
| `aps_topics.xlsx` | APS-Schema: 8 Bereiche, 22 Kapitel, 165 Themen, DE/FR; `code` = Bereich.Kapitel.Thema | Festes Schema in der Registry |

Hinweis aus dem README: Für APS existieren keine Gold-Labels; die Curia-Vista-Sachbereiche dienen als grobe Kontrolle (Mapping nötig).

## 7. Lösungsansatz

### 7.1 Pipeline

```
Download (separat, online)      → Import-Bündel (NDJSON.gz, CSV, XLSX)
        │ offline übertragbar
        ▼
1 Ingest         affairs, texts, docs, bodies → PostgreSQL; inkrementell über index.json / updated_at
        ▼
2 Input          pro Geschäft ein Klassifikationstext: Bund = Titel + eingereichter Text (+ Begründung);
                 Kantone/Gemeinden = Titel + Anfang des ersten Dokuments; HTML entfernt, Sprache erkannt
        ▼
3 Registry       registry/tags.yaml laden und validieren → Tabelle tags; scheme_hash je Schema
        ▼
4 Jobs           classification_jobs je Geschäft und Aufgabe auf open setzen (neu, geändert, neuer Hash)
        ▼
5 Klassifikation Worker: Apertus 8B zweistufig (Kapitel → Themen) → Tags, Konfidenz, Beleg, ggf. Vorschlag;
                 Apertus 70B für unsichere Fälle; Ergebnis mit Besitzprüfung schreiben
        ▼
6 Speicher       affair_tags, tag_proposal_raw → tag_proposals, job_events, classification_runs
        ▼
7 Review         in der Web-App bestätigen / verwerfen / ersetzen / ergänzen; Korrekturen → Gold-Set
        ▼
8 Ausgabe        Sidecar-API, Exportdatei im OpenParlData-Stil, ParlWiki (Web-App + Markdown), Agent-Suche
```

Änderung gegenüber dem Konzept: Embeddings und Kandidaten per Vektorsuche entfallen (ADR 0003). Die Registry übernimmt die Rolle der Themenbeschreibungen; Kandidaten für Ad-hoc-Themen kommen aus der Volltextsuche (7.4). Diagramm: [02-pipeline](architecture/02-pipeline.html).

### 7.2 Tag-Registry `registry/tags.yaml`

- Eine versionierte YAML-Datei ist die **einzige Quelle** für Tags. Git hält ihre Historie, die Datenbank spiegelt sie. YAML statt Markdown, weil Pydantic die Datei direkt validiert und kein eigener Parser nötig ist (ADR 0001).
- Tags stehen als Liste, nicht als Mapping. Doppelte IDs fallen so bei der Validierung auf, statt beim Einlesen still überschrieben zu werden.
- Ein Tag hat: `tag_id` (stabil, z. B. `aps:6.1.9`, `adhoc:digitalisierung-breit`), Namen DE/FR/IT (RM optional), Beschreibung DE/FR/IT, Aliasse, Schema (`aps` | `adhoc`), Status (`proposed`, `active`, `merged`, `retired`; bei `merged` zusätzlich `merged_into`), Eltern (APS-Hierarchie), Herkunft (erstellt von/am oder Vorschlag), Liste ungeprüfter Übersetzungen.
- APS-Themen werden einmal aus `aps_topics.xlsx` erzeugt (`parltopics registry import-aps`). IT-Beschreibungen fehlen bei APS. Sie werden mit Apertus 70B vorübersetzt und als ungeprüft markiert.
- Neue Tags entstehen nur über Vorschläge (7.3) oder den Ad-hoc-Ablauf (7.4). Aktiv wird ein Tag nur durch einen Reviewer. Nichts wird automatisch aktiv.
- **Schreibweg:** Nur Aktionen eines Menschen schreiben die Datei: Freigabe oder Zusammenlegen im Review und das bestätigte Anlegen eines Ad-hoc-Themas (Web-App, Agent-Dialog oder CLI). Die App schreibt atomar (temporäre Datei, dann Umbenennen), unter Dateisperre und mit erhöhter `registry_version`. Worker und Agent schreiben nie. Im Container liegt die Datei als Bind-Mount; ein Mensch prüft die Änderung (`git diff registry/tags.yaml`) und committet sie.
- **Versionen:**
  - `registry_version` (Feld in der Datei, Format `JJJJ-MM-TT.N`) steigt bei jeder inhaltlichen Änderung. `registry sync` lehnt eine geänderte Datei mit unveränderter Version ab. Jedes Label speichert die Version als Protokollfeld.
  - `scheme_hash` (berechnet, nicht in der Datei) ist der SHA-256 über die kanonische Form aller aktiven Einträge, die eine Aufgabe nutzt: für `classify:aps` alle aktiven APS-Einträge, für `classify:adhoc:<tag>` und `reclassify:<tag_id>` nur dieses eine Tag. Jobs hängen am `scheme_hash`, nicht an der `registry_version` (ADR 0004). Ein neues oder geändertes Ad-hoc-Tag öffnet also nur seine eigenen Jobs, nie den APS-Volllauf.

Format siehe Anhang A.

### 7.3 Klassifikation mit Apertus (Worker)

- **Zweistufig (Vorgabe):**
  - Stufe 1: Systemprompt + 22 APS-Kapitel (ID, Namen DE/FR/IT, Kurzbeschreibung) + Klassifikationstext → 1 bis 3 Kapitel mit Konfidenz.
  - Stufe 2: Systemprompt + Themen der gewählten Kapitel + alle aktiven Ad-hoc-Tags (kompakt: ID, Namen, Beschreibung DE, Aliasse) + Klassifikationstext → Tags mit Konfidenz und Beleg, optional Vorschläge.
  - Begründung: Die volle Registry (165 Themen mit Beschreibungen in drei Sprachen) ergäbe pro Anfrage grob 15'000–25'000 Tokens. Das wäre nur mit Prefix-Caching bei Keera tragbar, und ob es das gibt, ist offen (15). Zweistufig bleiben beide Anfragen klein. Einstufig läuft nur noch als Vergleich in der Evaluation (F16).
- **Aufbau der Nachrichten:** Systemprompt und Registry-Ausschnitt stehen in der System-Nachricht, der Geschäftstext in der User-Nachricht. So bleibt der Anfang über viele Anfragen gleich und Prefix-Caching kann greifen, falls vorhanden.
- **Ausgabe (JSON, Anhang B):** Stufe 2 liefert Tags mit `confidence` (0–1) und `evidence` (Textstelle, max. 300 Zeichen), optional `proposed_tags` mit Name, Beschreibung, Begründung. Ungültiges JSON wird einmal mit Fehlerhinweis wiederholt, dann an 70B eskaliert, dann als `failed` markiert (7.7). `response_format` bzw. JSON-Schema werden genutzt, falls der Endpunkt sie unterstützt.
- **Validierung:** nur `tag_id`s aus dem angebotenen Registry-Ausschnitt; Konfidenz in [0, 1]; höchstens 5 Tags und 2 Vorschläge. Der Beleg wird unscharf geprüft: Trigramm-Ähnlichkeit (`word_similarity` aus `pg_trgm`) zum Klassifikationstext ≥ 0.9. Darunter wird die Konfidenz halbiert und das Label mit `evidence_verified = false` markiert. Ein wörtlicher Abgleich wäre zu streng, weil Modelle Anführungszeichen, Umlaute und Leerzeichen normalisieren.
- **Konfidenz:** Die selbstberichtete Konfidenz eines 8B-Modells ist schwach kalibriert. Die Schwelle 0.6 ist ein Startwert. Die Evaluation misst die Präzision je Konfidenzband, und die Schwelle wird so gesetzt, dass das Präzisionsziel (13) hält. Liefert der Endpunkt Logprobs, ersetzen sie die selbstberichtete Konfidenz.
- **Eskalation an 70B:** Konfidenz unter Schwelle, Tag-Vorschlag vorhanden, Text ohne erkennbare Sprache oder länger als Limit, sowie eine Zufallsstichprobe (2 %) zur Qualitätskontrolle und Kalibrierung. Das 70B-Ergebnis ersetzt das 8B-Ergebnis; beide werden gespeichert (8B als `superseded`).
- **Tag-Vorschläge:** Worker schreiben Rohvorschläge in `tag_proposal_raw`. Nach dem Lauf werden sie gruppiert und in zwei Stufen geprüft: (1) Namens-/Alias-Abgleich normalisiert (Kleinschreibung, Akzente, Trigramm-Ähnlichkeit in `pg_trgm`), (2) Apertus 70B beurteilt mit der Registry im Kontext, ob die Gruppe ein bestehendes Tag dupliziert oder spezialisiert. Ergebnis ist ein Eintrag in `tag_proposals` mit Empfehlung (`new`, `duplicate_of`, `child_of`) und der Liste der betroffenen Geschäfte (`tag_proposal_affairs`).
- **Menschliche Entscheidungen haben Vorrang:** Ein im Review verworfenes Tag wird bei einer Neuklassifikation desselben Geschäfts nicht wieder aktiv, solange sich der Text (`input_hash`) nicht ändert. Es wird als `rejected` gespeichert und im Review angezeigt. Von Hand bestätigte oder ergänzte Tags bleiben aktiv, auch wenn das Modell sie nicht mehr vergibt.
- **Prompts** liegen als Dateien in `prompts/`. `prompt_version` = Dateiname mit Versionsnummer plus kurzer Hash des Inhalts (z. B. `classify_topics_v1+3f2a9c1d`). So fällt eine Änderung ohne Versionssprung auf.
- **Fix vs. Ad-hoc:** APS einmal über den Bestand, danach täglich nur neue oder geänderte Geschäfte. Ad-hoc-Themen laufen bei Bedarf (7.4). Bewährte Ad-hoc-Tags werden auf `active` gesetzt und laufen dann in Stufe 2 des täglichen Laufs mit.

Ablauf eines Workers im Detail: [ARCHITEKTUR.md, Abschnitt 3](ARCHITEKTUR.md#3-worker-massenklassifikation).

### 7.4 Ad-hoc-Themen ohne Embeddings

Ein neues Ad-hoc-Thema (Name + Beschreibung) soll zeitnah über 326k Geschäfte ausgewertet werden. Ohne Vektorsuche:

1. Apertus 70B erzeugt aus der Beschreibung eine Suchdefinition: Stichwörter und Phrasen in DE/FR/IT. Im Dialog übernimmt das der Agent (7.8) mit dem Werkzeug `generate_keywords`; die Redaktion prüft die Liste vor dem Start.
2. PostgreSQL-Volltextsuche liefert Kandidaten (Titel + Text, Trigramm für Schreibvarianten).
3. Für jeden Kandidaten und für eine Zufallsstichprobe von 2 % der übrigen Geschäfte entsteht ein Job `classify:adhoc:<tag>`. Apertus 8B prüft jedes Geschäft gegen das Thema (Label, Konfidenz, Beleg). Nicht-Treffer werden protokolliert, damit die Stichwortliste lernt.
4. Ergebnisse sind sofort als vorläufige Treffer sichtbar (Tag-Status `proposed`, Labels markiert). Bewährt sich das Thema, aktiviert ein Reviewer es; danach läuft es in Stufe 2 des täglichen Laufs mit.

Die Stichprobe ausserhalb der Kandidaten schätzt, wie viele Treffer die Stichwortsuche verpasst (Kandidaten-Recall, 13). Geschäfte ohne Stichworttreffer werden sonst erst beim nächsten Volllauf erfasst. Embeddings (pgvector ist vorbereitet) sind der spätere Weg, falls das nicht reicht oder die Registry zu gross für den Prompt wird. Diagramm: [06-adhoc-thema](architecture/06-adhoc-thema.html).

### 7.5 ParlWiki

- **Web-App:** FastAPI, Jinja2, serverseitig gerendert, eigenes CSS, keine externen Assets. JavaScript nur für Graph und kleine Interaktionen, lokal ausgeliefert. Seiten: Geschäft, Thema, Parlament, Suche, Review-Warteschlange, Graph, Statusübersicht.
- **Geschäftsseite:** Titel, Metadaten, Klassifikationstext mit hervorgehobenen Belegstellen, Link zur Quelle (`url_external`) und zu `api.openparldata.ch`. Tags mit Konfidenz, Beleg, Modell-, Prompt- und Registry-Version; jedes Tag verlinkt auf seine Themenseite. Verwandte Geschäfte über gemeinsame Tags. Verlauf früherer Labels (`superseded`, `rejected`).
- **Themenseite:** Beschreibung, von Apertus erzeugte Zusammenfassung der letzten 12 Monate (mit Verweis auf die zitierten Geschäfte), Filter nach Ebene/Kanton/Jahr/Typ/Konfidenz, Liste der Geschäfte mit Konfidenz und Beleg, verwandte Themen (gemeinsames Vorkommen), Link in den Graphen.
- **Review direkt auf der Seite:** Auf Geschäfts- und Themenseite kann ein angemeldeter Reviewer jedes Label bestätigen, verwerfen, durch ein anderes Tag ersetzen oder ein Tag ergänzen. Jede Aktion schreibt `reviews` mit Benutzer und Zeit und ist sofort in API und Wiki sichtbar. Die Review-Warteschlange sortiert offene Fälle: niedrige Konfidenz, ungeprüfter Beleg, Tag-Vorschläge, Stichprobe.
- **Graph-Ansicht:** drei Sichten, nie der Vollgraph: (1) ein Thema und seine Geschäfte (höchstens 200 Knoten, nach Konfidenz), (2) ein Geschäft und seine Nachbarn über gemeinsame Tags (höchstens 50), (3) Themen untereinander, Kantengewicht = Anzahl gemeinsamer Geschäfte, mit Schwelle. Ein Klick auf einen Knoten öffnet die Seite. Daten kommen als JSON aus `GET /v1/graph/...`; die Bibliothek (vorgesehen: force-graph, MIT) liegt lokal unter `static/vendor/`.
- **Markdown-Export** nur für Themen- und Parlamentsseiten (`wiki/themen/*.md`, `wiki/parlamente/*.md`) mit Frontmatter und Links auf die Geschäfte in Web-App und OpenParlData. Idempotent, jederzeit aus der DB neu erzeugbar, geeignet für Obsidian. Keine Datei pro Geschäft: Bei Zehntausenden gelabelten Geschäften würden Git, Obsidian und der Export unbrauchbar langsam. Einzelne Geschäfte lassen sich bei Bedarf exportieren (`parltopics wiki --affair <id>`).

### 7.6 Suche

- Volltext: PostgreSQL `tsvector` mit Konfigurationen `german`, `french`, `italian`, `simple`, über Titel und Klassifikationstext; Filter Tag, Ebene, Parlament, Jahr, Typ. Funktioniert ohne LLM.
- Natürlichsprachige Anfragen beantwortet der Agent (7.8). Er leitet Tags, Filter und Suchbegriffe ab, ruft die Suche auf und fasst die Treffer zu einer Kurzantwort mit Verweisen (OpenParlData-ID) zusammen. Keine Antwort ohne Treffer als Beleg.

### 7.7 Status und parallele Verarbeitung

Die Klassifikation läuft mit vielen parallelen Anfragen an den LLM-Endpunkt, und mehrere Läufe können sich überschneiden (täglicher Lauf, Ad-hoc-Thema, Nachklassifizierung). Damit jederzeit klar ist, was erledigt ist und was als Nächstes kommt, hat jedes Geschäft pro Aufgabe einen Status. Den Status führt der Pipeline-Code, nicht Apertus: Der Code entscheidet anhand des Status, welches Geschäft als Nächstes bearbeitet wird, und Apertus erhält immer genau ein Geschäft.

**Aufgaben (`task`)** je Geschäft:

- `classify:aps`: APS zweistufig; Stufe 2 enthält alle aktiven Ad-hoc-Tags.
- `classify:adhoc:<tag>`: Prüfung für ein Ad-hoc-Thema, nur Kandidaten und Stichprobe (7.4).
- `reclassify:<tag_id>`: Nachklassifizierung nach Freigabe eines neuen Tags, ebenfalls über Kandidaten und Stichprobe.

| Status | Bedeutung | Wird gesetzt, wenn |
|---|---|---|
| `open` | Muss bearbeitet werden | Geschäft neu importiert; Text geändert (`input_hash`); neue `prompt_version` oder neuer `scheme_hash` der Aufgabe; ein neu freigegebenes Tag betrifft das Geschäft; Job nach Timeout freigegeben; manuell „neu klassifizieren“ |
| `pending` | Ein Worker bearbeitet es gerade | Worker übernimmt den Job (`worker_id`, `locked_at`, `attempts + 1`) |
| `done` | Ergebnis gespeichert, gültig für `input_hash` + `prompt_version` + `scheme_hash` | Labels und Vorschläge mit Besitzprüfung geschrieben |
| `failed` | Nicht klassifizierbar, mit Fehlergrund | Sofort bei dauerhaften Fehlern (leerer Text, ungültiges JSON auch nach 70B); beim 3. Versuch bei vorübergehenden Fehlern (Timeout, 5xx nach allen Wiederholungen, Absturz) |

`failed` ergänzt die drei Grundstatus, damit Fehler weder endlos wiederholt noch fälschlich als `done` gezählt werden. Zurück auf `open` geht ein `failed`-Job nur manuell oder mit neuer Prompt- oder Modellversion.

**Regeln**

- **Übernahme:** Worker übernehmen nur Jobs mit `open`, sortiert nach Priorität (Ad-hoc und Nachklassifizierung vor Volllauf), dann neueste Geschäfte zuerst. Die Übernahme geschieht mit `SELECT … FOR UPDATE SKIP LOCKED`, damit kein Geschäft doppelt bearbeitet wird – auch bei mehreren Prozessen oder Servern.
- **Versuche:** `attempts` zählt Übernahmen. Die JSON-Wiederholung und die Eskalation an 70B gehören zum selben Versuch und zählen nicht extra.
- **Heartbeat und Timeout:** Ein Worker erneuert `locked_at` alle 2 Minuten. Ein Job, dessen `locked_at` älter als der Timeout ist (Start: 10 min), geht zurück auf `open`. So trifft der Timeout nur abgestürzte Worker, nicht langsame.
- **Besitzprüfung:** Ein Worker schreibt sein Ergebnis nur, wenn der Job in derselben Transaktion noch `pending` ist und seine `worker_id` trägt. Sonst verwirft er das Ergebnis und protokolliert `lost_lock`. Ein Worker, dessen Job schon neu vergeben wurde, kann so nichts doppelt schreiben.
- **Eskalation** an 70B bleibt im selben Job: Status `pending`, Feld `stage` wechselt von `8b` auf `70b`.
- **Eingefrorene Registry:** Ein Lauf speichert beim Start `registry_version` und `scheme_hash`, und alle Worker arbeiten mit diesem Stand. Eine Änderung an `tags.yaml` während des Laufs setzt die betroffenen Jobs erst für den nächsten Lauf auf `open`.
- Worker schreiben nie in `tags.yaml` (7.2).
- **Vorschläge:** Tag-Vorschläge paralleler Worker landen roh in `tag_proposal_raw` und werden nach dem Lauf gruppiert (normalisierter Name, `pg_trgm`, Prüfung der ganzen Gruppe durch 70B). Ergebnis ist ein Vorschlag mit der Liste der betroffenen Geschäfte. Vorschläge durchlaufen denselben Ablauf: `open` → `pending` (in Prüfung) → `done` mit Entscheid `accepted`, `merged` oder `rejected`.
- **Lauf-Lock:** Pro Aufgabe läuft höchstens ein Lauf gleichzeitig (Postgres Advisory Lock). Verschiedene Läufe dürfen parallel laufen.
- **Drosselung:** Die Parallelität ist getrennt für 8B und 70B konfigurierbar (`PARALLEL_8B`, `PARALLEL_70B`). Bei 429 oder Timeout halbiert der Client die aktuelle Grenze (mindestens 1). Nach 50 fehlerfreien Antworten erhöht er sie um 1 bis zum konfigurierten Maximum. Sonst bliebe ein Volllauf nach dem ersten Fehler dauerhaft gebremst.
- **Protokoll:** Jeder Statuswechsel wird in `job_events` protokolliert. Der Fortschritt eines Laufs ist die Zählung nach Status; ein Lauf ist fertig, wenn keiner seiner Jobs mehr auf `open` oder `pending` steht.

Diagramme: [03-job-lifecycle](architecture/03-job-lifecycle.html), [04-worker-sequenz](architecture/04-worker-sequenz.html).

### 7.8 Suche und Ad-hoc-Themen als Tool-Calling-Agent

Massenklassifikation und Dialog stellen verschiedene Anforderungen (ADR 0005). Die Worker (7.3, 7.7) sind deterministisch, günstig pro Geschäft und reproduzierbar. Suche und das Anlegen von Ad-hoc-Themen brauchen dagegen mehrere Schritte, deren Reihenfolge von der Anfrage abhängt. Das übernimmt ein Agent mit Apertus 70B, der Werkzeuge über Tool-Calling aufruft. Er läuft im Prozess der Web-App.

- **Schleife:** Anfrage → Modell wählt ein Werkzeug → Ergebnis zurück ans Modell → … → Antwort. Höchstens 6 Werkzeugaufrufe; danach erzwingt der Code eine Antwort aus den bisherigen Ergebnissen. Gesamt-Timeout 60 s.
- **Werkzeuge** (Argumente als Pydantic-Modelle in `src/parltopics/agent/tools.py`):

| Werkzeug | Zweck | Wirkung |
|---|---|---|
| `search_affairs(query, tags, body_keys, year_from, year_to, affair_type, limit)` | Volltextsuche mit Filtern | lesend |
| `list_tags(query, scheme, limit)` | passende Tags in der Registry finden | lesend |
| `get_affair(affair_id)` | Titel, gekürzter Text, Tags mit Konfidenz und Beleg | lesend |
| `count_affairs(tags, group_by, body_keys, year_from, year_to)` | Zahlen nach Parlament, Ebene oder Jahr | lesend |
| `generate_keywords(name, description)` | Stichwörter DE/FR/IT für ein Ad-hoc-Thema | lesend (interner 70B-Aufruf) |
| `propose_adhoc_topic(name, description, keywords)` | Entwurf eines neuen Ad-hoc-Themas | erzeugt nur einen Entwurf; angelegt wird erst nach Bestätigung im UI |

- **Antwortregeln:** Der Agent antwortet nur aus Werkzeug-Ergebnissen und belegt jede Aussage mit OpenParlData-IDs. Der Code prüft vor der Ausgabe, dass jede zitierte ID in einem Werkzeug-Ergebnis dieser Sitzung vorkam. Sonst wird die Antwort verworfen und einmal neu angefordert. Ohne Treffer lautet die Antwort „Keine passenden Geschäfte gefunden“, mit den verwendeten Filtern.
- **Sicherheit:** Werkzeug-Ergebnisse und Geschäftstexte sind Daten, keine Anweisungen, und stehen im Prompt klar abgegrenzt. Argumente werden validiert, SQL ist parametrisiert, Ergebnisgrössen sind begrenzt. Der Agent hat keinen Schreibzugriff.
- **Fallback:** Unterstützt der Endpunkt kein Tool-Calling, nutzt die Schleife ein Prompt-Protokoll. Das Modell antwortet mit `{"action": "<werkzeug>", "args": {...}}` oder `{"answer": "...", "cited_ids": [...]}`; Pydantic validiert jeden Schritt.
- **Protokoll:** Jede Sitzung wird in `agent_runs` gespeichert: Anfrage, Werkzeugaufrufe, Antwort, zitierte IDs, Modell- und Prompt-Version, Dauer, Status.
- **Warum 70B:** Werkzeugwahl über mehrere Schritte ist für 8B unzuverlässig. Die Zahl der Dialoganfragen ist klein, die Kosten fallen nicht ins Gewicht.

Diagramme: [05-agent-suche](architecture/05-agent-suche.html), [06-adhoc-thema](architecture/06-adhoc-thema.html). Details: [ARCHITEKTUR.md, Abschnitt 4](ARCHITEKTUR.md#4-agent-suche-und-ad-hoc-dialog).

## 8. Funktionale Anforderungen

Jede Anforderung hat eine prüfbare Abnahme.

| ID | Anforderung | Abnahme |
|---|---|---|
| F1 | **Download** (`parltopics download`) lädt `index.json` und ausgewählte Exportdateien (affairs, bodies, texts/docs für gewählte `body_key`s, hackapertus) in ein Import-Bündel; nur geänderte Dateien (Grösse/Datum aus index.json). | Zweiter Lauf lädt nur geänderte Dateien; Bündel ist ein Verzeichnis, offline kopierbar. |
| F2 | **Ingest** liest das Bündel in PostgreSQL (affairs, bodies, texts, docs-Text), inkrementell über `updated_at`, Zeilenzahlen gegen index.json geprüft. | Zeilenzahlen stimmen mit index.json überein; erneuter Lauf ändert nichts. |
| F3 | **Input-Aufbereitung** baut pro Geschäft einen Klassifikationstext (Regel Bund/Kantone, HTML entfernt, Längenlimit, Sprache erkannt) und speichert `input_hash`. | Stichprobe von 50 Geschäften: kein HTML, Sprache korrekt, Länge innerhalb Limit. |
| F4 | **Registry**: `registry/tags.yaml` wird geladen, validiert (eindeutige IDs, Pflichtfelder, gültige Verweise auf `parent` und `merged_into`, ID-Präfix passt zum Schema, `registry_version` bei Inhaltsänderung erhöht) und in die Tabelle `tags` synchronisiert; `scheme_hash` je Schema berechnet; APS aus `aps_topics.xlsx` erzeugbar. | Validierung schlägt bei doppelter ID und bei geänderter Datei ohne neue Version fehl; Sync ist idempotent; 165 APS-Themen vorhanden; gleicher Inhalt ergibt gleichen `scheme_hash`. |
| F5 | **Klassifikation**: Worker rufen Apertus 8B zweistufig über die OpenAI-kompatible API auf (7.3), validieren die Ausgabe und speichern Tags mit Konfidenz, Beleg, `model_version`, `prompt_version`, `registry_version`, `input_hash`; parallelisiert und wiederaufnehmbar über den Status je Geschäft (7.7), Fehler protokolliert. | Lauf über CHE 2024–2026 vollständig; Abbruch und Neustart führt kein Geschäft doppelt aus; JSON-Fehlerquote < 1 %. |
| F6 | **Eskalation** an 70B nach Regeln in 7.3; das 70B-Label ist aktiv, das 8B-Label bleibt als `superseded` gespeichert. | Fälle unter Schwelle erscheinen mit `model_version` 70B; das 8B-Label ist abrufbar. |
| F7 | **Tag-Vorschläge** werden roh erfasst, nach dem Lauf gruppiert, auf Duplikate geprüft (Trigramm + 70B) und mit Empfehlung und betroffenen Geschäften gespeichert. Annahme im Review schreibt das Tag in `tags.yaml` (neue Version). | Vorschlag „E-Government“ wird als Duplikat/Kind von „Digitalisierung“ erkannt; angenommener Vorschlag erscheint in `tags.yaml`. |
| F8 | **Ad-hoc-Thema** per CLI, Web-App oder Agent-Dialog anlegen; Pipeline nach 7.4 läuft nur über Kandidaten und Stichprobe und zeigt vorläufige Treffer. | Thema „Digitalisierung (breit)“ liefert Treffer; Kandidatenzahl und Laufzeit protokolliert; Kandidaten-Recall aus der Stichprobe ausgewiesen. |
| F9 | **Review** direkt auf Geschäfts- und Themenseite und in der Warteschlange: Label bestätigen/verwerfen, Tag ersetzen oder ergänzen, Vorschlag annehmen/zusammenlegen/ablehnen; mit Benutzer und Zeit; Korrekturen exportierbar als Gold-Set; verworfene Tags kehren ohne Textänderung nicht zurück (7.3). | Korrigiertes Label ist in API und Wiki sichtbar und im Gold-Set-Export enthalten; nach Neuklassifikation bleibt ein verworfenes Tag verworfen. |
| F10 | **Sidecar-API**, JSON, paginiert. Lesend: `GET /v1/affairs/{id}/topics`, `GET /v1/topics`, `GET /v1/topics/{id}/affairs?body_key=&from=&to=&min_confidence=`, `GET /v1/search?q=&topic=&body_key=`, `GET /v1/graph/topics/{id}`, `GET /v1/graph/affairs/{id}`, `GET /v1/graph/topics`, `GET /v1/jobs/summary`. Agent (mit Rate-Limit): `POST /v1/agent/search`. Schreibend (mit Anmeldung): `POST /v1/topics/proposals`, `POST /v1/reviews`, `POST /v1/adhoc`. | Antworten < 200 ms bei Filterabfragen auf 326k Geschäften (Index); OpenAPI-Schema vorhanden; schreibende Endpunkte ohne Anmeldung abgewiesen. |
| F11 | **Export** `affair_topics.ndjson.gz` im OpenParlData-Stil (snake_case, `id`, `affair_id`, `body_key`, `topic_external_id`, `topic_de/fr/it/rm`, `scheme`, `confidence`, `model_version`, `updated_at`) plus `index.json`-Eintrag. | Datei validiert gegen Schema; Zeilenzahl = aktive Labels. |
| F12 | **DVS-Liste**: Sicht „Digitalisierung, Bund + Kantone, laufende Geschäfte“ als API-Abfrage, Wiki-Seite und CSV. | Enthält ≥ 29 der 30 Geschäfte aus `dvs_digitalisierung.csv`. |
| F13 | **ParlWiki Web-App** nach 7.5: Geschäft, Thema, Parlament, Suche, Review-Warteschlange, Graph, Statusübersicht. | Geschäftsseite zeigt Text mit hervorgehobenem Beleg und verlinkten Tags; Themenseite zeigt Zusammenfassung mit Verweisen; alle Assets lokal (Netzwerk-Log ohne externe Hosts). |
| F14 | **Markdown-Export** nach 7.5, nur Themen und Parlamente. | Export läuft zweimal ohne Diff; Frontmatter enthält `tag_id`, `scheme`, `registry_version` und die Zahl der Geschäfte; keine Datei pro Geschäft. |
| F15 | **Suche** nach 7.6: Volltext mit Filtern ohne LLM; natürlichsprachige Anfrage über den Agenten (7.8). | Anfrage in DE und FR liefert Treffer mit Kurzantwort und Verweisen; ohne Treffer keine erfundene Antwort. |
| F16 | **Evaluation** als Kommando: Präzision/Recall gegen Gold-Set, nach Sprache und Ebene; Baseline Keyword-Suche; Präzision je Konfidenzband; Vergleich einstufig/zweistufig; bei Ad-hoc Kandidaten-Recall und Klassifikator-Recall getrennt; Bericht als Markdown. | Bericht enthält Tabellen je Sprache/Ebene, Baseline-Vergleich, Konfidenzbänder und beide Prompt-Varianten. |
| F17 | **Täglicher Lauf**: ein Kommando führt Ingest → Input → Klassifikation (nur neu/geändert) → Export → Wiki aus; Laufprotokoll in `classification_runs`. | Lauf mit Tagesdelta < 1 h; Protokoll zeigt Anzahl neu/geändert/fehlgeschlagen. |
| F18 | **Status pro Geschäft und Aufgabe** (`open`, `pending`, `done`, `failed`) nach 7.7, inkl. automatischem Zurücksetzen auf `open` bei geändertem Text, neuer Prompt-Version, neuem `scheme_hash` der Aufgabe oder neu freigegebenem Tag; Statusübersicht in API (`GET /v1/jobs/summary`) und Web-App. | Geändertes Geschäft im Tagesimport steht danach auf `open`, nach dem Lauf auf `done`; Job eines abgebrochenen Workers steht nach dem Timeout wieder auf `open`; ein neues Ad-hoc-Tag öffnet keinen `classify:aps`-Job; Übersicht zeigt die Zählung je Status. |
| F19 | **Parallele Verarbeitung** mit Job-Übernahme per `SKIP LOCKED`, Heartbeat, Besitzprüfung beim Schreiben, Lauf-Lock pro Aufgabe, adaptiver Drosselung und Gruppierung paralleler Tag-Vorschläge nach 7.7. | Zwei gleichzeitig gestartete Worker-Prozesse bearbeiten kein Geschäft doppelt; ein Worker, dessen Job nach Timeout neu vergeben wurde, schreibt nichts; ein zweiter Start desselben Laufs wird abgelehnt; derselbe Vorschlag aus 5 Workern ergibt einen Eintrag mit 5 Geschäften. |
| F20 | **Graph-Ansicht** nach 7.5: Thema mit Geschäften, Geschäft mit Nachbarn, Themen untereinander; Klick öffnet die Seite. | Jede Sicht bleibt unter ihrer Knotengrenze und lädt in < 1 s; Bibliothek lokal ausgeliefert. |
| F21 | **Agent** für Suche und Ad-hoc-Dialog nach 7.8, mit Werkzeugliste, Schrittgrenze, Zitatprüfung und Protokoll in `agent_runs`. | Bei 20 Testfragen zitieren alle Antworten nur IDs aus Werkzeug-Ergebnissen; keine Antwort ohne Treffer; kein Lauf mit mehr als 6 Werkzeugaufrufen; `propose_adhoc_topic` legt ohne Bestätigung nichts an. |
| F22 | **Air-Gap-Bundle**: Skripte bauen online ein Bundle (Images, Wheels, Prüfsummen) und spielen es offline ein (10.3, [AIRGAP.md](AIRGAP.md)); ein Offline-Test prüft den Betrieb in einem Netz ohne Internet. | Offline-Test in CI grün: Container ohne Internetzugang starten, Migration, Registry-Prüfung und ein LLM-Aufruf gegen einen Mock laufen; ein Aufruf ins Internet scheitert. |

## 9. Nicht-funktionale Anforderungen

| Bereich | Anforderung |
|---|---|
| Offline / Air-Gap | Startet und arbeitet ohne Internet. Einziger erlaubter Netzwerkzugriff: der Host aus `LLM_BASE_URL`; der HTTP-Client verweigert alle anderen Hosts (Allowlist im Code, Unit-Test). Docker-Images enthalten alle Abhängigkeiten und werden aus mitgelieferten Wheels gebaut. Spracherkennung mit `lingua-language-detector` (Modelle im Wheel). Graph-Bibliothek und CSS lokal, Systemschriften statt Web-Fonts. Keine Telemetrie. |
| Reproduzierbarkeit | Jedes Label trägt `model_version` (Modellname + Antwort des Endpunkts), `prompt_version` (mit Inhalts-Hash), `registry_version`, `input_hash`. Prompts liegen als Dateien im Repo. Temperatur 0. Abhängigkeiten über `uv.lock` gepinnt. |
| Leistung | Volllauf APS über 326k Geschäfte mit 8B < 24 h. Annahme: ≥ 16 parallele Anfragen; zweistufig sind es rund 2 Anfragen je Geschäft. Am ersten Tag mit 200 Anfragen messen, ob das hält. Tagesdelta < 1 h. Ad-hoc-Thema: Kandidaten < 1 min, Prüfung von 10k Kandidaten < 1 h. Agent-Antwort: Dauer wird protokolliert, Ziel < 30 s. |
| Robustheit | Wiederaufnahme nach Abbruch über den Status je Geschäft (Heartbeat, Timeout, Besitzprüfung); Retry mit Backoff bei 429/5xx; adaptive Drosselung; Fehlerfälle als `failed` mit Grund gespeichert, nicht verworfen. |
| Sprachen | DE/FR/IT vollständig; RM-Titel werden mitgeführt. Tags und UI mindestens DE, Tag-Namen DE/FR/IT. |
| Datenschutz | Nur öffentliche Parlamentsdaten. Keine Personendaten in Prompts ausser den im Geschäftstext enthaltenen. Review-Benutzer lokal verwaltet. |
| Sicherheit | API hinter Reverse-Proxy; Ports im Compose nur an `127.0.0.1` gebunden; schreibende Endpunkte mit Authentifizierung (Basic Auth oder lokaler Token); Agent-Endpunkt mit Rate-Limit. Keine Secrets im Repo (`.env`). **Prompt-Injection:** Geschäftstexte und Werkzeug-Ergebnisse sind Daten, keine Anweisungen, und im Prompt abgegrenzt. Die Ausgabe der Worker akzeptiert nur Registry-IDs. Vorschläge sind auf 2 je Geschäft und auf Name, Beschreibung und Begründung begrenzt und werden nie automatisch aktiv. Der Agent hat nur lesende Werkzeuge. |
| Betrieb | Docker Compose: `db` (PostgreSQL 16 mit pgvector und pg_trgm), `api`, `worker`. Logs strukturiert auf stdout, Docker schreibt sie in Dateien. Backup = `pg_dump` + `registry/tags.yaml` in Git. |

## 10. Architektur und Tech-Stack

### 10.1 Komponenten

| Komponente | Technik | Aufgabe |
|---|---|---|
| `download` | Python, httpx | Online-Schritt, erzeugt Import-Bündel |
| `ingest` | Python, psycopg 3, COPY | Bündel → PostgreSQL |
| `inputs` | Python, lingua | Klassifikationstext, HTML-Bereinigung, Sprache, `input_hash` |
| `registry` | Python, PyYAML, Pydantic | `tags.yaml` ↔ Tabelle `tags`, Validierung, `scheme_hash`, Versionierung |
| `classify` | Python, asyncio, `openai`-SDK | Job-Queue, Worker, Validierung, Eskalation, Vorschläge |
| `agent` | Python, `openai`-SDK (Tool-Calling) | Suche und Ad-hoc-Dialog mit lesenden Werkzeugen |
| `llm` | Python, httpx, `openai`-SDK | Gemeinsamer Client: Allowlist, Retry, adaptive Drosselung |
| `api` + `wiki` | FastAPI, Jinja2, eigenes CSS, Graph-Bibliothek lokal | Sidecar-API, Web-App mit Review und Graph, Markdown-Export |
| `export` | Python | NDJSON.gz, CSV |
| `search` | PostgreSQL FTS + pg_trgm | Volltext, Filter, Kandidaten |
| `evaluation` | Python | Gold-Set, Metriken, Bericht |
| DB | PostgreSQL 16, Extensions `pg_trgm`, `vector` (ungenutzt, für später) | Daten, Labels, Jobs, Suche |
| Doku | Archify (MIT, nur Build-Zeit) | Architektur-Diagramme als HTML |

**Datenmodell** (SQL-Skizze in Anhang C, verbindlich ist `migrations/0001_init.sql`; Diagramm [07-datenmodell](architecture/07-datenmodell.html)): `bodies`, `affairs`, `affair_texts`, `affair_docs`, `affair_inputs`, `search_documents`, `tags`, `registry_syncs`, `affair_tags`, `reviews`, `classification_runs`, `classification_jobs`, `job_events`, `tag_proposal_raw`, `tag_proposals`, `tag_proposal_affairs`, `agent_runs`.

### 10.2 LLM-Anbindung

OpenAI-kompatibler Client mit `LLM_BASE_URL` und `LLM_API_KEY` aus `.env`; Modellnamen `LLM_NAME` (8B) und `LLM_NAME_LARGE` (70B). `response_format` und Tool-Calling werden genutzt, falls der Endpunkt sie unterstützt (offene Frage 1); sonst Prompt-basiertes JSON mit Pydantic-Validierung. `parltopics llm check` prüft Erreichbarkeit, Modellnamen und Antwortzeit.

### 10.3 Zielarchitektur und Air-Gap

Das Hack-Template verlangt eine von drei Zielarchitekturen. ParlTopics ist für **b) Air-gapped** ausgelegt und erfüllt damit auch a) On-Premise und c) Sovereign Swiss Cloud.

| Phase | Ort | Externe Abhängigkeiten |
|---|---|---|
| Build | Rechner mit Internet | PyPI (Wheels nach `uv.lock`), Docker Hub (`python:3.12-slim`, `pgvector/pgvector:pg16`) |
| Datendownload | Rechner mit Internet | `files.openparldata.ch` (Exporte, Hack-Datensatz) |
| Transfer | Datenträger | Bundle mit Images, Wheels und Prüfsummen; Import-Bündel mit Daten |
| Laufzeit | Server ohne Internet | Nur der LLM-Endpunkt aus `LLM_BASE_URL` |

Im Hack zeigt `LLM_BASE_URL` auf Keera, das ist der einzige Weg nach aussen. Im Air-Gap-Betrieb zeigt dieselbe Variable auf einen Apertus-Endpunkt im internen Netz, zum Beispiel vLLM mit den Apache-2.0-Gewichten. Code und Images bleiben gleich. Ablauf, Skripte und Nachweis: [AIRGAP.md](AIRGAP.md), Diagramm [08-airgap-deployment](architecture/08-airgap-deployment.html).

### 10.4 Technische Leitplanken

- **Kommandos** (über `uv run` oder `make`): `make setup` · `make db` · `parltopics db migrate` · `parltopics download --bundle data/import --bodies CHE` · `parltopics ingest --bundle data/import` · `parltopics inputs` · `parltopics registry validate` · `parltopics registry sync` · `parltopics classify --task classify:aps --body CHE --since 2024-01-01` · `parltopics worker` · `parltopics adhoc "Digitalisierung (breit)" --description-file …` · `parltopics export` · `parltopics wiki --out wiki/` · `parltopics eval --gold data/gold` · `parltopics llm check` · `make api` · `make test` · `make lint` · `make diagrams`
- **Projektstruktur:** Monorepo nach Anhang D.
- **Code-Stil:** Typannotationen, Pydantic-Modelle für LLM-Ausgaben und Werkzeug-Argumente, kleine Funktionen, `ruff` als Linter/Formatter, deutschsprachige Fachbegriffe in Daten und Doku, englische Bezeichner im Code.
- **Tests:** `pytest`; Unit-Tests für Registry, HTML-Bereinigung, JSON-Parsing, Prompt-Aufbau und Agent-Schleife mit Mock-LLM, Allowlist; Integrationstests gegen PostgreSQL (Compose-Dienst `db` oder CI-Service); Offline-Test (F22); Evaluationslauf als Abnahmetest.
- **Grenzen:** **Immer** Allowlist für Hosts, Versionen an jedem Label, HTML entfernen, Tests vor Commit. **Vorher fragen** bei neuen Abhängigkeiten, Schemaänderungen, Änderungen an APS-Einträgen in `tags.yaml`, Änderungen am Exportformat. **Nie** in OpenParlData schreiben, Secrets committen, andere Hosts als `LLM_BASE_URL` aufrufen, Tag-Vorschläge ohne Review aktivieren, Labels löschen (nur Status ändern), dem Agenten schreibende Werkzeuge geben.

## 11. Integration OpenParlData

| Stufe | Was | Wann |
|---|---|---|
| 1 | Sidecar-API (F10) neben `api.openparldata.ch`, gleiche IDs | Phase 1 (Hack) |
| 2 | Exportdatei `affair_topics.ndjson.gz` im Stil der bestehenden Exporte, inkl. `index.json`-Eintrag (F11); regelmässige Lieferung ab Phase 2 | Phase 1 (Datei), Phase 2 (Lieferung) |
| 3 | Filter „Thema“ im Portal neben „Geschäftstyp (vereinheitlicht)“, gespeist aus Stufe 2 | Phase 3 (OpenParlData-Team) |

Abstimmung mit dem OpenParlData-Team zu Feldnamen, Lizenz und Übergabeweg ist offene Frage (Abschnitt 15).

## 12. Scope

Der Umfang dieses PRD bleibt vollständig. Er wird in drei Phasen umgesetzt, der Hack ist Phase 1.

**Phase 1 – Hack**

- Daten: CHE komplett (affairs, texts), hackapertus-Datensatz, bodies. Kantone nur als Stichprobe (politmonitor-Geschäfte mit erstem Dokument).
- Registry: APS (165) + Ad-hoc „Digitalisierung (breit)“ (Definition entlang PolitMonitor: E-Government, Cybersicherheit, KI, Datenschutz, digitale Medien, Breitband).
- Klassifikation: Worker mit Status, Parallelität und Eskalation (F5–F7, F18, F19). Digitalisierung über alle Geschäfte (Volllauf, falls Durchsatz reicht; sonst Kandidaten per FTS + Zufallsstichprobe); APS für CHE ab 2024 und Stichprobe anderer Ebenen.
- Web-App: Geschäfts- und Themenseiten mit Belegen und Verlinkungen, Review direkt auf der Seite, Graph-Ansicht, Suche mit Agent-Kurzantwort, Statusübersicht. 3–5 Themenseiten im Fokus (Digitalisierung plus z. B. Energie, Gesundheit, Migration, Verkehr).
- Ausgabe: Sidecar-API, Exportdatei, DVS-Sicht, Markdown-Export für Themen und Parlamente, Evaluationsbericht.
- Betrieb: Docker Compose, Air-Gap-Bundle und Offline-Test (F22).
- Abgabe: technischer Bericht (PDF, max. 6 Seiten), Demo-Video (max. 2 min), öffentliches Repo.

**Phase 2 – Betrieb**

- Alle Ebenen mit Dokumenttexten (docs-Export 5.5 GB), Regel „erstes Dokument“ verfeinern.
- APS-Volllauf 326k, täglicher Lauf (F17) im Dauerbetrieb, regelmässige Lieferung der Exportdatei an OpenParlData.
- Konfidenzschwellen anhand der Review-Daten nachkalibrieren.
- Interner Apertus-Endpunkt für echten Air-Gap-Betrieb.

**Phase 3 – Integration und Ausbau**

- Portal-Filter „Thema“ (Stufe 3, OpenParlData-Team).
- Embeddings für Tag-Ähnlichkeit und Ad-hoc-Kandidaten, wenn Registry oder Bestand es verlangen.
- Mehrsprachige UI, Benutzerverwaltung, Rechte.
- Automatischer Commit von Registry-Änderungen.

**Priorität innerhalb von Phase 1**, falls die Zeit knapp wird: Klassifikation und Evaluation zuerst (M0–M2), dann Geschäftsseite → Themenseite → Review → Agent-Suche → Graph (M3, M4). Jede Stufe ist für sich demo-fähig.

## 13. Erfolgskriterien und Metriken

| Metrik | Ziel Phase 1 | Messung |
|---|---|---|
| Recall Digitalisierung, Volllauf | ≥ 0.85 auf PolitMonitor-Positiven (CHE ab 2018) | F16 |
| Recall Digitalisierung, Kandidatenpfad | Gesamt ≥ 0.80. Getrennt ausgewiesen: Kandidaten-Recall der Stichwortsuche (Anteil der PolitMonitor-Positiven unter den Kandidaten, Ziel ≥ 0.95) und Recall des Klassifikators innerhalb der Kandidaten (Ziel ≥ 0.85) | F16 |
| Präzision Digitalisierung | ≥ 0.80 auf manueller Stichprobe von 100 Treffern, die nicht in PolitMonitor sind (untere Grenze, da PolitMonitor unvollständig) | Review-Stichprobe |
| DVS-Abgleich | ≥ 29/30 Geschäfte der DVS-Liste getroffen | F12 |
| APS vs. Curia Vista | ≥ 0.75 der CHE-Geschäfte 2024–2026 haben mindestens ein APS-Thema, dessen gemapptes Sachgebiet mit Curia Vista übereinstimmt. Das Mapping (`data/gold/aps_curia_mapping.csv`) prüft eine Person aus dem Team vor der Messung und friert es ein; ein ungeprüfter Apertus-Entwurf zählt nicht. | F16, Mapping-Tabelle |
| Kalibrierung | Präzision je Konfidenzband (0.6–0.7, 0.7–0.8, 0.8–0.9, ≥ 0.9) im Bericht; Schwelle so gewählt, dass die Präzision oberhalb ≥ 0.80 liegt | F16 |
| Baseline | Präzision und Recall besser als Keyword-Suche je Sprache | F16 |
| Agent | Bei 20 Testfragen (DE/FR) zitieren alle Antworten nur IDs aus Werkzeug-Ergebnissen; keine Antwort ohne Treffer | F21 |
| Air-Gap | Offline-Test grün | F22 |
| Technik | JSON-Fehlerquote < 1 %; Durchsatz gemessen und dokumentiert; Wiki ohne externe Hosts | Logs, Netzwerk-Log |
| Nachvollziehbarkeit | 100 % der Labels mit Beleg, Modell-, Prompt- und Registry-Version | DB-Abfrage |

## 14. Risiken und Gegenmassnahmen

| Risiko | Wirkung | Massnahme |
|---|---|---|
| Umfang von Phase 1 zu gross für die Hack-Dauer | Unfertige Demo | Priorität nach Abschnitt 12; Meilensteine der Reihe nach; jede Stufe demo-fähig |
| Durchsatz der Keera-API reicht für Volllauf nicht | Digitalisierung nicht über alle 326k im Hack | Tag 1 messen; Fallback FTS-Kandidaten + Stichprobe; Volllauf über Nacht |
| Kein Prefix-Caching beim Endpunkt | Langsamer, teurer Volllauf | Zweistufiger Prompt als Vorgabe; Durchsatz am ersten Tag messen |
| 8B liefert unzuverlässiges JSON oder erfindet Tag-IDs | Fehlerhafte Labels | Pydantic-Validierung, nur IDs aus dem angebotenen Ausschnitt, Retry, Eskalation 70B, `response_format` falls verfügbar |
| Endpunkt unterstützt kein Tool-Calling oder kein `response_format` | Agent und JSON-Ausgabe weniger robust | Prompt-Protokoll mit Pydantic-Validierung als Fallback (7.8); `parltopics llm check` am ersten Tag |
| Agent erfindet Aussagen oder IDs | Falsche Antworten mit scheinbaren Belegen | Antwort nur aus Werkzeug-Ergebnissen; Zitatprüfung im Code; Protokoll in `agent_runs` |
| Keine APS-Gold-Labels | Qualität APS nur indirekt messbar | Mapping APS ↔ Curia-Vista-Sachbereiche, vor der Messung geprüft; manuelle Stichprobe |
| Kantonale Inputs schwach (nur Titel, PDFs) | Schlechte Labels ausserhalb Bund | Erstes Dokument einbeziehen; Ebene in Metriken getrennt ausweisen |
| Tag-Wildwuchs durch Vorschläge | Inkonsistente Themen | Vorschläge nie automatisch aktiv; Gruppierung und Duplikatprüfung; Reviewer |
| Registry-Datei und Git laufen auseinander | Unklare Versionsstände | Schreiben nur durch Menschen-Aktionen mit Dateisperre und Versionssprung; `registry sync` lehnt geänderte Datei ohne Versionssprung ab; Commit durch Menschen |
| Langsame Worker schreiben nach Timeout doppelt | Doppelte oder widersprüchliche Labels | Heartbeat, Besitzprüfung beim Schreiben (7.7) |
| Parallele Worker bearbeiten Geschäfte doppelt oder erzeugen doppelte Vorschläge | Verschwendete Anfragen, inkonsistente Tags | Status je Geschäft mit `SKIP LOCKED`, Lauf-Lock, Gruppierung der Vorschläge nach dem Lauf (7.7) |
| Nutzungsbedingungen OpenParlData / PolitMonitor-Daten | Veröffentlichung blockiert | Vor Veröffentlichung klären; Hack-Instanz intern; Daten nicht ins Repo |
| Offline-Vorgabe wird durch Abhängigkeiten verletzt | Tool läuft später nicht | Allowlist im Client, Image aus Wheels, Offline-Test in CI, keine CDN-Assets |

## 15. Offene Fragen

1. Keera: Basis-URL, Authentifizierung, Modellnamen für 8B/70B, Limits (Parallelität, Rate), konfiguriertes Kontextfenster, Prefix-Caching, Unterstützung von `response_format`/JSON-Schema, Tool-Calling und Logprobs.
2. Server: CPU/RAM/Storage für PostgreSQL mit docs-Texten (unkomprimiert mehrere GB); GPU nicht nötig, ausser für einen internen Apertus-Endpunkt im Air-Gap-Betrieb.
3. Wer gibt Vorschläge frei und committet Registry-Änderungen (Rolle, Prozess)?
4. Beschreibungen der APS-Themen: eigene Formulierung oder aus APS-Seite; IT-Übersetzung per Apertus akzeptabel?
5. Mapping APS-Themen ↔ Curia-Vista-Sachbereiche: wer prüft den Entwurf (Vorschlag: Apertus 70B erzeugt ihn, eine Person aus dem Team prüft und friert ihn ein)?
6. Gold-Set: Umfang der manuellen Prüfung im Hack (Vorschlag: 100 Digitalisierung, 100 APS), wer labelt?
7. OpenParlData: Nutzungsbedingungen, gewünschtes Exportformat, Übergabe (Datei, Repo, API), Interesse an Stufe 3.
8. ~~Regel „erstes Dokument“ für Kantone/Gemeinden~~ Entschieden (18.10.2026): das älteste Dokument mit Text (`parent_type = affair`, kleinstes `doc_date`, bei Gleichstand kleinste `id`). Betrifft 126'719 Geschäfte mit mehreren Dokumenten.
9. Veröffentlichung der Hack-Ergebnisse (Instanz, Lizenz der Labels).
10. Teamname und Rollen für README und technischen Bericht.
11. „Laufende Geschäfte“ (F12, DVS-Liste): Der harmonisierte Status ist nur bei 278 von 326'396 Geschäften gefüllt, `end_date` bei 18 %. Wie wird „laufend“ bestimmt (Status-Texte je Parlament, Enddatum, Datum der letzten Aktivität)? Bis dahin bleiben Status und Enddatum nur in `raw`.
12. Dokumente ohne Geschäft (News, Traktanden, Sitzungen; 290'039 Dokumente, 3.6 GB) bleiben in `affair_docs` und sollen ebenfalls klassifiziert werden (Entscheid 18.10.2026). Offen: wie, denn Jobs und Labels hängen heute an `affair_id`.

## 16. Meilensteine

| Meilenstein | Inhalt | Abnahme |
|---|---|---|
| M0 Setup | Monorepo-Skelett, Docker Compose, Migrationen, Download-Bündel CHE + hackapertus, Ingest, Input, `tags.yaml` aus APS | F1–F4 |
| M1 Klassifikation | LLM-Client (Allowlist, Drosselung), `llm check`, zweistufige Prompts, Job-Queue mit parallelen Workern, Mock-LLM-Tests, Durchsatzmessung (200 Anfragen), Lauf CHE 2024–2026 APS | F5–F7, F18, F19 |
| M2 Digitalisierung | Ad-hoc-Thema, Lauf über Bestand (oder Kandidaten + Stichprobe), Evaluation gegen PolitMonitor und DVS | F8, F12, F16 |
| M3 Ausgabe und Review | Sidecar-API, Export, Web-App mit Geschäfts- und Themenseite, Review auf der Seite, Statusübersicht, Markdown-Export, täglicher Lauf | F9–F11, F13, F14, F17 |
| M4 Agent und Graph | Agent für Suche und Ad-hoc-Dialog, Graph-Ansicht | F15, F20, F21 |
| M5 Abgabe | Air-Gap-Bundle und Offline-Test, Evaluationsbericht, technischer Bericht (PDF), Demo-Video, Übergabe an OpenParlData (Stufe 1–2) | F22, Abschnitt 13 |
| Phase 2 | Alle Ebenen, Volllauf, täglicher Betrieb, Kalibrierung, interner Apertus-Endpunkt | – |
| Phase 3 | Portal-Filter (Stufe 3), Embeddings bei Bedarf, Rechte, mehrsprachige UI | – |

---

## Anhang A: Format `registry/tags.yaml`

```yaml
registry_version: "2026-10-18.1"

schemes:
  aps:
    label: "Année Politique Suisse"
    source: "aps_topics.xlsx (hackapertus, Stand 18.10.2026)"
    fixed: true
  adhoc:
    label: "Ad-hoc-Themen"
    source: "ParlTopics-Team"
    fixed: false

tags:
  - tag_id: "aps:6.1.9"
    scheme: aps
    status: active
    parent: "aps:6.1"
    names:
      de: "Digitalisierung"
      fr: "Numérisation"
      it: "Digitalizzazione"
    descriptions:
      de: "Geschäfte zur Digitalisierung von Verwaltung, Wirtschaft und Gesellschaft, inkl. …"
      fr: "Objets relatifs à la numérisation de l'administration, de l'économie et de la société …"
      it: "Oggetti relativi alla digitalizzazione …"
    aliases: ["Digitale Transformation", "E-Government", "digitale Verwaltung"]
    unreviewed_translations: [it]

  - tag_id: "adhoc:digitalisierung-breit"
    scheme: adhoc
    status: active
    names: {de: "Digitalisierung (breit)", fr: "Numérisation (large)", it: "Digitalizzazione (ampia)"}
    descriptions:
      de: "Breite Definition entlang PolitMonitor: E-Government, Cybersicherheit, künstliche Intelligenz, …"
    aliases: ["Cybersicherheit", "KI", "Datenschutz", "Breitband", "digitale Medien"]
    created: {at: "2026-10-18", by: "team"}

  - tag_id: "adhoc:ki-verwaltung"
    scheme: adhoc
    status: proposed
    names: {de: "KI in der Verwaltung", fr: "IA dans l'administration", it: "IA nell'amministrazione"}
    descriptions: {de: "…"}
    proposal: {by: "apertus-70b", run: "2026-10-18-07", recommendation: child_of, related_tag: "aps:6.1.9"}
```

Regeln:

- `tag_id` ist eindeutig und stabil, das Präfix entspricht dem Schema.
- APS-Bereiche (`aps:6`), -Kapitel (`aps:6.1`) und -Themen (`aps:6.1.9`) stehen alle in der Registry; die Ebene ergibt sich aus der ID. Stufe 1 bietet Kapitel an, Labels vergeben die Worker nur auf Themen-Ebene.
- Pflicht: `tag_id`, `scheme`, `status`, `names.de`, `descriptions.de`.
- `parent` und `merged_into` müssen auf vorhandene Tags zeigen; `status: merged` verlangt `merged_into`.
- Tags werden nie gelöscht, nur im Status geändert.
- Jede inhaltliche Änderung erhöht `registry_version`.
- `scheme_hash` steht nicht in der Datei. Er wird beim Laden über die kanonische Form der aktiven Einträge berechnet (`tag_id`, `parent`, `names`, `descriptions`, `aliases`).

Das Pydantic-Modell dazu liegt in `src/parltopics/registry/models.py`.

## Anhang B: Ausgabeschema Klassifikation (JSON)

**Stufe 1 (Kapitel):**

```json
{
  "affair_id": 70435,
  "language": "de",
  "chapters": [
    {"chapter_id": "aps:5.1", "confidence": 0.82}
  ]
}
```

**Stufe 2 (Themen):**

```json
{
  "affair_id": 70435,
  "language": "de",
  "tags": [
    {"tag_id": "aps:5.1.8", "confidence": 0.86, "evidence": "Der Bundesrat wird beauftragt, in einem Bericht darzulegen, wie ..."}
  ],
  "proposed_tags": [
    {"name_de": "Wiedereinstieg ins Erwerbsleben", "description_de": "...", "reason": "Kein aktives Tag deckt ... ab"}
  ]
}
```

Validierung:

- `affair_id` entspricht dem angefragten Geschäft; `language` ist `de`, `fr`, `it`, `rm` oder `other`.
- Stufe 1: 1 bis 3 Kapitel, nur IDs aus der angebotenen Kapitelliste.
- Stufe 2: höchstens 5 Tags und 2 Vorschläge; `tag_id` muss im angebotenen Ausschnitt aktiv sein; `confidence` in [0, 1]; `evidence` höchstens 300 Zeichen.
- Beleg: Trigramm-Ähnlichkeit zum Klassifikationstext ≥ 0.9, sonst Konfidenz halbieren und `evidence_verified = false` (7.3).

Die Pydantic-Modelle dazu liegen in `src/parltopics/classify/schemas.py`.

## Anhang C: Datenmodell (Skizze)

Verbindlich ist `migrations/0001_init.sql`. Die Skizze zeigt Schlüssel und die wichtigsten Felder.

```sql
-- Quelldaten (Ingest; ohne Fremdschlüssel, damit Bulk-Import robust bleibt; raw = Originaldatensatz)
bodies(id bigint pk, body_key text unique, name, level, languages text[], raw jsonb, updated_at)
affairs(id bigint pk, body_key, body_id, number, external_id, title_de, title_fr, title_it, title_rm,
        type_harmonized_en, begin_date date, url_external, raw jsonb, updated_at)
affair_texts(id bigint pk, affair_id, text_type, language, format, text, raw jsonb, updated_at)
affair_docs(id bigint pk, parent_type, parent_id, name, category, doc_date, language, text, raw jsonb, updated_at)

-- Aufbereitung
affair_inputs(affair_id pk → affairs, text, language, source, input_hash, built_at)
search_documents(affair_id pk → affairs, language, document tsvector, updated_at)

-- Registry (Spiegel von registry/tags.yaml)
tags(tag_id text pk, scheme, status, parent_id → tags, merged_into → tags, name_de/fr/it/rm, desc_de/fr/it,
     aliases text[], unreviewed_translations text[], match_text, content_hash, registry_version, updated_at)
registry_syncs(id pk, registry_version, file_hash, scheme_hashes jsonb, synced_at)

-- Steuerung
classification_runs(id pk, kind, task, params jsonb, registry_version, scheme_hash, prompt_version,
                    started_at, finished_at, n_total, n_done, n_failed, n_escalated)
classification_jobs(affair_id → affairs, task, status, priority, stage, input_hash, prompt_version, scheme_hash,
                    run_id → classification_runs, worker_id, locked_at, attempts, last_error, updated_at,
                    primary key (affair_id, task))
job_events(id pk, affair_id, task, from_status, to_status, reason, run_id, worker_id, created_at)

-- Labels und Review
affair_tags(id pk, affair_id → affairs, tag_id → tags, scheme, confidence numeric(4,3), evidence, evidence_verified,
            task, stage,                       -- 8b | 70b | human
            model_version, prompt_version, registry_version, input_hash, run_id → classification_runs,
            status,                            -- active | rejected | superseded
            review_status,                     -- null | confirmed | rejected | changed
            reviewed_by, reviewed_at, created_at)
  unique (affair_id, tag_id, input_hash, prompt_version) where status = 'active'
reviews(id pk, affair_id → affairs, affair_tag_id → affair_tags, action, new_tag_id → tags, comment, user_name, created_at)

-- Vorschläge
tag_proposal_raw(id pk, affair_id → affairs, run_id → classification_runs, name_de, desc_de, reason,
                 model_version, proposal_id → tag_proposals, created_at)
tag_proposals(id pk, group_key unique, name_de, desc_de, reason, recommendation, related_tag_id → tags,
              model_version, run_id → classification_runs, status, decision, decided_by, decided_at, created_at)
tag_proposal_affairs(proposal_id → tag_proposals, affair_id → affairs, primary key (proposal_id, affair_id))

-- Agent
agent_runs(id pk, kind, query, tool_calls jsonb, answer, cited_affair_ids bigint[], model_version,
           prompt_version, duration_ms, status, created_at)
```

Indizes: aktive Labels `affair_tags(tag_id, affair_id)`, `affairs(body_key, begin_date)`, Warteschlange `classification_jobs(task, status, priority)` und offene Jobs, hängende Jobs `classification_jobs(locked_at)`, GIN auf `search_documents.document`, GIN `pg_trgm` auf `tags.match_text` (Namen und Aliasse).

## Anhang D: Projektstruktur (Monorepo)

```
Dreamers4OpenParl/
├── README.md  technical_report.md  LICENSE   Template-Dateien, Ort fix
├── CLAUDE.md                                 Arbeitsregeln für Claude Code
├── Makefile                                  setup, db, migrate, api, test, lint, diagrams, wheels, image, offline-test, bundle
├── pyproject.toml  uv.lock  .python-version  ein Python-Paket „parltopics“, Abhängigkeiten gepinnt
├── .env.example  .pre-commit-config.yaml
├── .github/workflows/ci.yml                  Lint, Tests mit PostgreSQL, Diagramm-Check, Offline-Test
├── .claude/skills/archify/                   Archify (MIT) für die Diagramme
├── docs/
│   ├── PRD.md  ARCHITEKTUR.md  AIRGAP.md  ENTWICKLUNG.md
│   ├── adr/                                  Architektur-Entscheide
│   └── architecture/                         Diagramme: src/*.json (Quelle), *.html (erzeugt), manifest.json
├── registry/tags.yaml                        einzige Quelle der Tags
├── prompts/                                  versionierte Prompts (classify_chapters_v1.md, …)
├── migrations/                               SQL-Migrationen, nummeriert
├── src/parltopics/                           Code (Template verlangt src/)
│   ├── cli.py  config.py  db.py
│   ├── llm/  registry/  download/  ingest/  inputs/
│   ├── classify/  agent/  search/  export/  evaluation/  wiki/
│   └── api/  (app.py, templates/, static/)
├── deploy/
│   ├── Dockerfile  docker-compose.yml        Betrieb
│   ├── docker-compose.offline.yml            Offline-Test (internes Netz, Mock-LLM)
│   ├── docker-compose.llm.yml                Vorlage interner Apertus-Endpunkt (vLLM)
│   └── airgap/                               build-wheels.sh, build-bundle.sh, load-bundle.sh, offline-test.sh
├── scripts/                                  diagrams.mjs (Diagramme bauen, prüfen), erd_from_sql.py (ERD aus Migrationen)
├── data/                                     Import-Bündel und Gold-Set (nicht im Repo)
└── tests/  unit/  integration/  fixtures/  mock_llm/
```

## Anhang E: Diagramme

Interaktive HTML-Dateien in [`docs/architecture/`](architecture/README.md), erzeugt mit Archify aus `docs/architecture/src/*.json` (`make diagrams`). Lokal im Browser öffnen.

| Diagramm | Typ | Inhalt |
|---|---|---|
| [01-systemarchitektur](architecture/01-systemarchitektur.html) | Architektur | Komponenten, Datenbank, LLM-Endpunkt, Grenze Online/Offline |
| [02-pipeline](architecture/02-pipeline.html) | Workflow | Vom Download bis zur Ausgabe, mit Eskalation und Review |
| [03-job-lifecycle](architecture/03-job-lifecycle.html) | Lebenszyklus | Status eines Jobs: open, pending (8b/70b), done, failed |
| [04-worker-sequenz](architecture/04-worker-sequenz.html) | Sequenz | Ein Job von der Übernahme bis zum Schreiben mit Besitzprüfung |
| [05-agent-suche](architecture/05-agent-suche.html) | Sequenz | Agent-Schleife mit Werkzeugen und Zitatprüfung |
| [06-adhoc-thema](architecture/06-adhoc-thema.html) | Workflow | Ad-hoc-Thema vom Dialog bis zur Aktivierung |
| [07-datenmodell](architecture/07-datenmodell.html) | ERD | Tabellen, Schlüssel und Beziehungen |
| [08-airgap-deployment](architecture/08-airgap-deployment.html) | Datenfluss | Build online, Transfer, Betrieb offline |
