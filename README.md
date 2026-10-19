# Hack Apertus Liebefeld — OpenParlData: Topic classification for Swiss parliaments with Apertus, Team Dreamers

Template repository for [Hack Apertus](https://hackapertus.ch/) submissions.
Every project keeps the same layout, so organizers and judges find the same
things in the same place.

There are 3 challenges to pick from:
1. Bern Economic Development Agency: Research & Expertise Navigator
2. OpenParlData: Topic classification for Swiss parliaments with Apertus
3. University of Bern: Deciphering Archives with Apertus

We picked challenge 2. Swiss parliaments publish more than 326'000 affairs from 97 parliaments
(federal, cantonal and municipal) through OpenParlData, in German, French, Italian and Romansh.
There is no shared topic classification across these parliaments, so finding all affairs on a
subject such as digitalisation means manual keyword searches that miss relevant items and return
false hits ("Städtebau" for "eBau"). The goal is an open, reusable classification service built on
Apertus that assigns topics either from a fixed two-level taxonomy (Année Politique Suisse) or from
ad-hoc topics defined by the user, without retraining. The service is validated on a real use case:
automatically detecting digitalisation affairs for the Digitale Verwaltung Schweiz (DVS).

Submissions must use the v1.5 Apertus model family.
The submission must comply with the [HackApertus T&C](https://hackapertus.ch/terms-and-conditions).

## 🎯 The Challenge

**OpenParlData: Topic classification for Swiss parliaments with Apertus**

Challenge page: [Notion guide](https://app.notion.com/p/hackapertus/OpenParlData-9e3b4fec112a82559ec0011ee5b6f48d?source=copy_link), full text in [docs/CHALLENGE.md](docs/CHALLENGE.md)

### Our solution

| | |
| --- | --- |
| Input | Affairs from the OpenParlData bulk export (`affairs`, `texts`, `docs`, `contributors`): title, submitted texts (federal level and selected cantons), start of the first extracted document (cantons, municipalities) |
| Mode 1 | Fixed taxonomy: classification along Année Politique Suisse (APS: 3 areas, 22 chapters, 165 topics in SKOS format in `registry/tags.yaml`) |
| Mode 2 | Ad-hoc topics: user defines a topic with a short description (e.g. "Digitalisierung", "Velowege"); Apertus 70B suggests multilingual keywords (de/fr/it) for candidate pre-filtering plus a random sample, classified without retraining |
| Languages | Classified directly in de, fr, it and rm, no translation step; cross-lingual topic expansion in search across de, fr and it |
| Output per affair | Topic(s), confidence score, verbatim text passage that justifies the label, one-sentence summary (`summary_de`), plus model, prompt and registry versions (`affair_topics.ndjson.gz` sidecar export and DVS CSV list) |
| Search & ParlWiki | Public search UI (cross-lingual full-text search, hierarchical navigation search over the topic tree, and a read-only tool-calling agent on Apertus 70B citing affair IDs) plus `/admin` with bottom-up summarized ParlWiki pages (`Heart` → area → chapter → topic), interactive topic graph, review queue and ad-hoc topic creation |
| Human in the loop | Labels and model-proposed new tags can be confirmed, rejected, replaced, added or undone in `/admin/review`; human decisions take precedence over reclassification |
| Model | Apertus v1.5 (70B single-pass with strict JSON schema enum over topic slugs by default; two-stage 8B → 70B escalation mode also supported; deterministic title rules for routine affairs) via an OpenAI-compatible endpoint (`LLM_BASE_URL`) |

**Evaluation.** On 473 federal affairs (`CHE` since 2024), single-pass Apertus 70B reaches **84.6 %**
any-hit agreement with Curia Vista subject areas (`parltopics eval --curia`, vs. 72.7 % for two-stage
8B with escalation; PRD target: 75 %). The full evaluation report (`parltopics eval`) measures precision
and recall across hierarchy levels (area, chapter, topic) against a full-text keyword baseline,
confidence calibration bands, candidate vs. classifier recall for ad-hoc topics
(`politmonitor_digitalisierung.csv`, `dvs_digitalisierung.csv`), and splits results by **language,
parliament level, canton (region) and political party** (`affair_contributors`) to check for bias.

**Data.** Bulk export from [files.openparldata.ch/exports](https://files.openparldata.ch/exports/)
(`bodies`, `affairs`, `texts`, `docs`, `contributors`) and the Hack Apertus evaluation dataset
(`/hackapertus`). We do not paginate the API. Routine affairs (swearing-in, resignations,
naturalisations, budgets and accounts) are classified deterministically by title rules (`stage = 'rule'`)
without an LLM call.

Details on architecture, evaluation and limitations are in [technical_report.md](technical_report.md).

## 🔧 Resources & Tools

Check our resources & tools page for detailed information:
[https://hackapertus.notion.site/liebefeld-resources-tools](https://hackapertus.notion.site/liebefeld-resources-tools)

| Models           | URL                                      |
|------------------|------------------------------------------|
| Apertus v1.5 8B  | [huggingface.co/swiss-ai/Apertus-v1.5-8B](https://huggingface.co/swiss-ai/Apertus-v1.5-8B)  |
| Apertus v1.5 70B | [huggingface.co/swiss-ai/Apertus-v1.5-70B](https://huggingface.co/swiss-ai/Apertus-v1.5-70B) |

## The structure

Keep the files and directories as shown below — don't rename or move them.

| Path | What it is |
| --- | --- |
| `README.md` | The challenge description and submission requirements |
| `technical_report.md` | The deeper write-up: architecture, evaluation, limitations |
| `LICENSE` | Apache-2.0 |
| `src/` | Your code |

ParlTopics adds these directories (monorepo, see [docs/PRD.md, Anhang D](docs/PRD.md#anhang-d-projektstruktur-monorepo)):

| Path | What it is |
| --- | --- |
| `docs/` | PRD, architecture, air-gap guide, ADRs, interactive diagrams (`docs/architecture/`) |
| `registry/` | Tag registry (`registry/tags.yaml`, SKOS), single source of all topics, plus APS descriptions and Curia Vista mappings (`registry/aps_descriptions.yaml`) |
| `prompts/` | Versioned prompts for workers, page summaries, navigation search and agent |
| `migrations/` | Numbered SQL migrations (PostgreSQL 16) |
| `web/` | Web app: React, Vite, TypeScript, Tailwind CSS, shadcn/ui; FastAPI serves the build from `web/dist` |
| `deploy/` | Dockerfile, Docker Compose, air-gap bundle and offline test |
| `tests/` | Unit and integration tests, mock LLM |
| `scripts/` | Build and check of the Archify diagrams, ERD generator, check of the web build |

## Environment

- Include instructions for running the project in your technical report.
- Use the following environment variables:
```
LLM_NAME — name and version of the model
LLM_BASE_URL — endpoint base URL
LLM_API_KEY — your API key
```

ParlTopics reads exactly these variables and adds `LLM_NAME_LARGE` for the 70B model. All settings are listed in [`.env.example`](.env.example).

## 📦 Submission Requirements & Deliverables

The submission must:
1. follow the template repo and include all prerequisite files and definitions
2. run end-to-end when judges try to run it

### Git repo (URL)
- Create your repo from this template (**Use this template**).
- Keep the layout as it is: don't rename or move its files.
- Set the repo to PUBLIC (Settings --> Collaborators --> Manage Visibility)
- Submit the URL of YOUR Git repo.

### Technical Report (pdf)
- Update [technical_report.md](technical_report.md) in this repository with all the details for your submission.
- Upload a pdf of your technical report to the root of the repo, named as `TeamName_Report.pdf`.
- Format: pdf, max. 6 pages w/o references
- Submit the pdf of the technical report.

### Demo video (URL)
- Max. 2 min demo video of your prototype
- Add the link to the **Demo** field at the top of [technical_report.md](technical_report.md)
- Submit the URL of the video.

## ⚖️ Judging Criteria

Each challenge has its own criteria, listed in its challenge description.

The main jury scores every submission on 6 dimensions (relevant for Top 6 teams):
1. **Purposeful use of AI**
2. **Technical rigour**
3. **Value, cost & scalability**
4. **Sovereign deployability**
5. **Implementation feasibility**
6. **Pitch & presentation**

Each dimension is scored from 0 to 5.

## Getting started

Requires [uv](https://docs.astral.sh/uv/), Docker with Compose v2, make and Node 22 (for the web app).

### 1. Setup and local services

```bash
git clone https://github.com/edu008/Dreamers4OpenParl.git
cd Dreamers4OpenParl
make setup              # Python 3.12 and dependencies from uv.lock (uv sync)

# Configure the model endpoint (never commit the key)
cp .env.example .env
# set LLM_API_KEY in .env; LLM_BASE_URL points to the Keera gateway (https://gateway.keera.ch/api/v1)

make db && make migrate # PostgreSQL 16 with pgvector in Docker, create the schema
make test               # unit tests
make web-build          # web app (React, shadcn/ui) into web/dist
uv run parltopics llm check
make api                # web app and API on http://127.0.0.1:8000 (Swagger UI at /v1/docs)
make web-dev            # optional: Vite with hot reload on http://127.0.0.1:5173
```

### 2. Data download, classification and export

The bulk export files are downloaded in a separate online step into `data/import/` (excluded from git):

```bash
# Download OpenParlData export (omit --bodies to download all 97 parliaments, ~6 GB) and ingest
uv run parltopics download --bundle data/import --bodies CHE
uv run parltopics ingest --bundle data/import

# Sync the SKOS tag registry and build cleaned classification inputs + full-text index
uv run parltopics registry sync
uv run parltopics inputs --body CHE --since 2024-01-01

# Classify affairs (APS), group new tag proposals, and build ParlWiki page summaries
uv run parltopics classify --task classify:aps --body CHE --since 2024-01-01 --limit 50
uv run parltopics proposals group
uv run parltopics pages

# Optional: create and run an ad-hoc topic without retraining
uv run parltopics adhoc "Velowege" --description-file velo.txt --body CHE --wait

# Export sidecar file (affair_topics.ndjson.gz), DVS list (dvs_liste.csv) and Markdown wiki
uv run parltopics export --out dist/export
uv run parltopics wiki --out wiki

# Or run the full daily pipeline end-to-end (ingest -> inputs -> registry -> classify -> proposals -> pages -> export -> wiki)
uv run parltopics daily --bundle data/import --body CHE --since 2024-01-01
```

### 3. Evaluation and offline verification

```bash
# Coarse check of active APS labels against Curia Vista subject areas (federal affairs)
mkdir -p data/import/hackapertus
curl -o data/import/hackapertus/che_affairs_keywords.csv https://files.openparldata.ch/hackapertus/che_affairs_keywords.csv
uv run parltopics eval --curia data/import/hackapertus/che_affairs_keywords.csv

# Full evaluation report (precision, recall, baseline, confidence bands, bias by language/level/canton/party)
uv run parltopics eval --gold data/gold --out data/eval/report.md

# Verify air-gapped build and runtime in an isolated Docker network without internet access
make offline-test
```

## 📚 Project documentation (German)

| Document | Content |
| --- | --- |
| [PRD](docs/PRD.md) | Product requirements: goals, scope by phase, requirements F1–F27, metrics, milestones, research background |
| [Architektur](docs/ARCHITEKTUR.md) | Worker and agent design, page tree with summaries, navigation search, pipeline, tools |
| [Diagramme](docs/architecture/README.md) | Ten interactive Archify diagrams (open the HTML files locally) |
| [Air-Gap](docs/AIRGAP.md) | Build online, transfer, run offline; offline test |
| [Entwicklung](docs/ENTWICKLUNG.md) | Setup, tests, conventions, pull request checklist |
| [Design](DESIGN.md) | Design system («Schweizer Plakat»: Swiss Design in Swiss Red, black and white) |
| [ADR](docs/adr/README.md) | Architecture decisions |

## 🤖 Use of AI tools

- **Apertus v1.5** (8B, 70B) is the only model used inside the product.
- **Claude** (Anthropic) was used as a development assistant for data exploration, code and documentation.
- **Archify** (MIT) renders the architecture diagrams in `docs/architecture/`.

## 👥 Team Dreamers

- Eduan Roci ([@edu008](https://github.com/edu008))
- Lirim Zahiri ([@lirimzahiri](https://github.com/lirimzahiri))
- Mouad Medini ([@mdmdni](https://github.com/mdmdni))

## License

All Hack Apertus projects are open-sourced. Please check our Terms & Conditions for specific licensing details (6. What you build is open source): https://hackapertus.ch/terms-and-conditions

## Support

### FAQ
💡 https://hackapertus.ch/faq

### Contact

💬 In case you have questions, join the conversation on Discord. Alternatively, send an email to “hello@hackapertus.ch”.
