# Technical report — `project name`, `team name`

A deeper write-up than the README: what you built, how it works, and what the
numbers say.

- **Challenge:** OpenParlData: Topic classification for Swiss parliaments with Apertus
- **Event:** On-site Liebefeld
- **Team:** `team name` — `member`, `member`, `member`
- **Demo:** `link to video`

## 1. Summary

The problem, your approach, and the headline result in one paragraph.

## 2. Architecture

Components, data flow, and where each one runs. Put diagrams in `docs/` and
reference them here.

> Draft from the project setup. Details: [docs/ARCHITEKTUR.md](docs/ARCHITEKTUR.md) and the interactive
> diagrams in [docs/architecture/](docs/architecture/README.md), e.g. the
> [system architecture](docs/architecture/01-systemarchitektur.html) and the
> [pipeline](docs/architecture/02-pipeline.html).

### Target architecture (mandatory)

State which of the three architectures your project is deployable in, and how
it meets that constraint:

- **a) On-premise** — on the organisation's own infrastructure, under its own administration.
- **b) Air-gapped** — with no external network connection at runtime.
- **c) Sovereign Swiss cloud** — on a cloud platform operated in Switzerland, under Swiss jurisdiction, with Swiss data residency.

List any external dependencies, and separate build time from runtime.

**ParlTopics targets b) Air-gapped**, which also covers a) and c). At runtime the application talks to one
host only, the OpenAI-compatible Apertus endpoint in `LLM_BASE_URL`; the HTTP client refuses every other
host. During the hack this endpoint is Keera; in air-gapped operation it is an Apertus server inside the
same network (template: `deploy/docker-compose.llm.yml`). Code and images are identical in both cases.

| Phase | Where | External dependencies |
| --- | --- | --- |
| Build | machine with internet | PyPI (wheels pinned in `uv.lock`), Docker Hub (`python:3.12-slim`, `pgvector/pgvector:pg16`) |
| Data download | machine with internet | `files.openparldata.ch` |
| Transfer | removable media | bundle with images, wheels and checksums; data bundle |
| Runtime | server without internet | only `LLM_BASE_URL` |

The app image is built only from bundled wheels (`pip install --no-index`). A CI job runs the services in a
Docker network without a route to the internet and checks migration, registry, LLM call (mock), health
endpoint and that outbound internet access fails. See [docs/AIRGAP.md](docs/AIRGAP.md) and the
[air-gap diagram](docs/architecture/08-airgap-deployment.html).

## 3. Use of Apertus

- **Model:** `e.g. swiss-ai/Apertus-v1.5-8B`
- **How it is used:** inference | fine-tuning | evaluation | red-teaming | agents / tool use
- **Where it runs:** `local weights, hosted endpoint, ...`

Prompts, adapters, quantisation, serving stack — whatever a reader needs to
rebuild your setup.

## 4. Data

What you used, where it came from, and its licence. Flag anything personal or
non-redistributable, and keep it out of the repository (see `.gitignore`).
If data comes from human subjects or contains personal information, describe
how consent was obtained.

## 5. Limitations

Where it breaks, what you did not test, and known failure modes.

## 6. Reproducibility

What a judge needs to get your numbers back: hardware, runtime, seeds, and the
exact commit.


## License

Creative Commons Attribution 4.0 (CC-BY-4.0). All HackApertus projects are open-sourced.

## References
