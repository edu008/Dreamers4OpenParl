# Challenge: OpenParlData – Topic classification for Swiss parliaments with Apertus

Originaltext der Challenge (Englisch), übernommen von der sprintd-Seite des Events «Hack Apertus» Liebefeld, Stand 18.10.2026. Dieser Text ist die Vorgabe. Bei Widersprüchen zum PRD gilt die Challenge. Nicht umformulieren.

- Guide: <https://app.notion.com/p/hackapertus/OpenParlData-9e3b4fec112a82559ec0011ee5b6f48d?source=copy_link>
- Event: <https://app.sprintd.org/events/hack-apertus-liebefeld/cases>

## 1. Context and Background

OpenParlData.ch collects parliamentary data from 90 Swiss federal, cantonal and municipal parliaments and makes it accessible through a single open API. It currently provides access to more than 300,000 political affairs and 900,000 documents in German, French, Italian and, to a tiny extent, Romansh. While this creates a common basis for accessing and analysing parliamentary information across Switzerland, the data is currently primarily searchable through full-text search. A number of parliaments, organisations and research projects have developed their own approaches to organising affairs by topic, but these are typically designed for specific use cases, use different classification schemes and often rely on manual tagging. There is therefore a need for a shared, accessible approach to topic classification that builds on the data provided by OpenParlData.ch.

### Problem Description

Today there is no common way to turn this large body of parliamentary information into topic-based results. Existing topic classifications are fragmented across parliaments and projects, differ in structure and are often created manually for a specific purpose, so a classification created for one use case cannot easily be reused for another. At the same time, full-text search requires users to anticipate the terminology in the underlying documents and repeat it across languages. The result: even seemingly straightforward questions about a topic across parliaments require substantial manual work: identifying relevant affairs, interpreting them, and assigning topic labels by hand. The data is available, but its thematic structure is not reusable as a shared resource.

### Main Objective

Develop an open and reusable classification service for Swiss parliamentary data, based on Apertus and OpenParlData. The service processes parliamentary affairs (titles, texts and associated documents) in German, French, Italian and Romansh, and automatically returns either topics from a standard two-level classification (such as the Année Politique Suisse scheme) or ad-hoc topics defined by users (such as "digitalisation" or "Covid-19"). The approach is validated through a practical use case with Digital Administration Switzerland (DVS), automatically identifying digitalisation-related affairs across the OpenParlData dataset as an alternative to the current manual process.

## 2. Datasets

- **OpenParlData API** (REST / JSON, public, no key required): <https://api.openparldata.ch/documentation>. Affairs, documents with extracted text, bodies, persons, votes. Multilingual (de / fr / it / rm), federal, cantonal and municipal level.
- **Data export:** <https://files.openparldata.ch>

### Supporting Materials

- Challenge background and prior work: <https://gitlab.com/groups/opendata.ch/openparldatach/-/wikis/Home/Future-Topics/Classification>
- BFH prototype: <https://huggingface.co/spaces/rcds/SwissParlTopicModelling>
- Demokratis classification for consultations: <https://github.com/Demokratis-ch/demokratis-ml>
- Earlier classification work from Basel-Stadt (GitHub repos, tbc)
- API documentation and example queries

## 3. Technology

- **Languages / frameworks:** no restriction (OpenParlData itself uses Apache Hop, <https://hop.apache.org>).
- **Platforms:** both are allowed: the Apertus compute and inference infrastructure provided at the hackathon, or local.
- **Models:** Apertus v1.5, 8B or 70B (`huggingface.co/swiss-ai/Apertus-v1.5-8B`, `huggingface.co/swiss-ai/Apertus-v1.5-70B`).

## 4. Expected Outputs

- Source code in a **public repository under an open-source licence** (README with setup and usage).
- A **working prototype** (API endpoint, script, or small demo UI) that classifies affairs from the OpenParlData API.
- **Short evaluation results** on a labelled sample.
- A **5-minute pitch / demo** on the final day.

### Success Criteria

- **Classification quality** on a labelled sample (e.g. the DVS "digitalisation" use case; accuracy on the APS topics).
- **Works across languages** (at least de / fr / it) and across parliament levels.
- **Ad-hoc topics** can be added without retraining.
- **Feasible runtime** for 300,000+ affairs.

### Evaluation Criteria

Usefulness for the OpenParlData community and public-sector users; technical quality and reproducibility; multilingual performance; innovation; ease of integration into OpenParlData; quality of the pitch.

## 5. Ethical Guidelines

- **Transparent and explainable results:** show why a topic was assigned (e.g. confidence, the relevant text passage).
- **Check for bias** between languages, regions and parties.
- **Neutrality:** classification must stay neutral and must not judge political positions.
- **Human in the loop:** topic labels are suggestions; a human should be able to correct them.

## 6. Legal and Compliance

All data is public (open government data from Swiss parliaments). Solutions should be published under an open-source licence, see the Hack Apertus Terms & Conditions (§6).

## Abgleich mit ParlTopics (Stand 18.10.2026)

| Vorgabe | Stand im Projekt |
|---|---|
| 5-Minuten-Pitch | nicht im PRD, zusätzlich zum 2-Minuten-Demo-Video des Templates einplanen |
| Bias nach Sprache, Region **und Partei** | Sprache, Ebene, Kanton und Partei im Evaluationsbericht (`parltopics eval`); die Partei ist die der erstgenannten Urheberin oder des erstgenannten Urhebers (`affair_contributors`), 85 % der CHE-Geschäfte ab 2024 haben eine |
| Neutralität | verankert in PRD 7.9 (Regel 7) und in den Prompts: eigene Regel im Agenten (`agent_system_v2`), «sachlich, ohne Wertung politischer Positionen» in Navigationsantworten und Seitenzusammenfassungen; das Stichproben-Review prüft es |
| Laufzeit für 300'000+ Geschäfte | Durchsatz noch nicht gemessen |
| Prototyp klassifiziert Geschäfte «from the API» | Projekt nutzt den Bulk-Export (bewusst); API-Beispiel ergänzen |
| Vorarbeiten (BFH, Demokratis) | als Vergleich noch nicht berücksichtigt |
