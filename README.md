# Hack Apertus Liebefeld: OpenParlData Topic Classification, Team Dreamers

Template repository for [Hack Apertus](https://hackapertus.ch/) submissions.
Every project keeps the same layout, so organizers and judges find the same
things in the same place.

There are 3 challenges to pick from:
1. Bern Economic Development Agency: Research & Expertise Navigator
2. OpenParlData: Topic classification for Swiss parliaments with Apertus
3. University of Bern: Deciphering Archives with Apertus

We picked challenge 2. Swiss parliaments publish more than 326'000 affairs from 89 parliaments
(federal, cantonal and municipal) through OpenParlData, in German, French, Italian and Romansh.
There is no shared topic classification across these parliaments, so finding all affairs on a
subject such as digitalisation means manual keyword searches that miss relevant items and return
false hits ("Städtebau" for "eBau"). The goal is an open, reusable classification service built on
Apertus that assigns topics either from a fixed two level taxonomy (Année Politique Suisse) or from
ad hoc topics defined by the user, without retraining. The service is validated on a real use case:
automatically detecting digitalisation affairs for the Digitale Verwaltung Schweiz (DVS).

Submissions must use the v1.5 Apertus model family.
The submission must comply with the [HackApertus T&C](https://hackapertus.ch/terms-and-conditions).

## 🎯 The Challenge

**OpenParlData: Topic classification for Swiss parliaments with Apertus**

Challenge page: [Notion guide](https://app.notion.com/p/hackapertus/OpenParlData-9e3b4fec112a82559ec0011ee5b6f48d?source=copy_link), full text in [docs/CHALLENGE.md](docs/CHALLENGE.md)

### Our solution

| | |
| --- | --- |
| Input | Affairs from the OpenParlData bulk export: title, texts (federal level), start of the first document (cantons, municipalities) |
| Mode 1 | Fixed taxonomy: two level classification along Année Politique Suisse (APS) |
| Mode 2 | Ad hoc topics: user defines a topic with a short description (e.g. "Digitalisierung", "Covid-19"), no retraining |
| Languages | Classified directly in de, fr, it and rm, no translation step |
| Output per affair | Topic(s), confidence score and the text passage that justifies the label |
| Human in the loop | Labels can be reviewed and corrected |
| Model | Apertus v1.5 (8B for bulk runs, 70B for difficult cases) via an OpenAI compatible endpoint |

**Evaluation.** Gold set built from manually checked keyword hits plus a random sample without
keyword hits, so both precision and recall are measurable. Baseline: a title regex for
digitalisation finds 8'151 affairs (2.5 %), of which 78 out of 100 checked were relevant.
Results are additionally split by language, parliament level and region to check for bias.

**Data.** Bulk export from [files.openparldata.ch/exports](https://files.openparldata.ch/exports/)
(`affairs`, `texts`, `docs`). We do not paginate the API. Elections and naturalisations are
filtered out before classification.

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
| `registry/tags.yaml` | Tag registry, the single source of all topics |
| `prompts/` | Versioned prompts for workers and agent |
| `migrations/` | Numbered SQL migrations (PostgreSQL 16) |
| `deploy/` | Dockerfile, Docker Compose, air-gap bundle and offline test |
| `tests/` | Unit and integration tests, mock LLM |
| `scripts/` | Build and check of the Archify diagrams, ERD generator |

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

> Status: work in progress during the hackathon (18 to 19 October 2026). The commands below are updated as the code in `src/` lands. Commands that are not implemented yet exit with code 3 and name their milestone.

Requires [uv](https://docs.astral.sh/uv/), Docker with Compose v2 and make.

```bash
git clone https://github.com/edu008/Dreamers4OpenParl.git
cd Dreamers4OpenParl
make setup              # Python 3.12 and dependencies from uv.lock (uv sync)

# Configure the model endpoint (never commit the key)
cp .env.example .env
# set LLM_NAME, LLM_NAME_LARGE, LLM_BASE_URL, LLM_API_KEY in .env

make db && make migrate # PostgreSQL 16 with pgvector in Docker, create the schema
make test               # unit tests
uv run parltopics llm check
make api                # web app and API on http://127.0.0.1:8000
```

The bulk export files are downloaded in a separate online step (`uv run parltopics download`) into
`data/import/`, which is excluded from git. Exact run commands for data download, classification and
evaluation follow in this section and in the reproducibility chapter of the technical report.

## 📚 Project documentation (German)

| Document | Content |
| --- | --- |
| [PRD](docs/PRD.md) | Product requirements: goals, scope by phase, requirements F1–F22, metrics, milestones |
| [Architektur](docs/ARCHITEKTUR.md) | Worker and agent design, pipeline, tools, versions and hashes |
| [Diagramme](docs/architecture/README.md) | Eight interactive Archify diagrams (open the HTML files locally) |
| [Air-Gap](docs/AIRGAP.md) | Build online, transfer, run offline; offline test |
| [Entwicklung](docs/ENTWICKLUNG.md) | Setup, tests, conventions, pull request checklist |
| [ADR](docs/adr/README.md) | Architecture decisions |

## 🤖 Use of AI tools

- **Apertus v1.5** (8B, 70B) is the only model used inside the product.
- **Claude** (Anthropic) was used as a development assistant for data exploration, code and documentation.
- **Archify** (MIT) renders the architecture diagrams in `docs/architecture/`.

## 👥 Team Dreamers

`TODO: Namen der drei Teammitglieder`

## License

All Hack Apertus projects are open-sourced. Please check our Terms & Conditions for specific licensing details (6. What you build is open source): https://hackapertus.ch/terms-and-conditions

## Support

### FAQ
💡 https://hackapertus.ch/faq

### Contact

💬 In case you have questions, join the conversation on Discord. Alternatively, send an email to “hello@hackapertus.ch”.
