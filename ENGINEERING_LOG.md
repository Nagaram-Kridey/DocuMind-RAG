# DocuMind Engineering Log

This document records every architectural decision, implementation,
experiment and explanation throughout the development of DocuMind.

It is intentionally more detailed than the README and serves as the
complete engineering knowledge base.

---

## Session 001

**Phase:** 0 — Setup

**Task:** 0.1 Repository Foundation

**Status:** Complete

### Goal

Establish a production-grade Django backend foundation with Docker,
PostgreSQL (pgvector), Redis, reproducible environments and CI readiness.

### Progress Checklist

- [x] Repository initialized
- [x] pyproject.toml and uv lock
- [x] Docker Compose (web, PostgreSQL 16 + pgvector, Redis)
- [x] Django project and split settings
- [x] PostgreSQL and Redis connectivity
- [x] Health endpoint
- [x] CI skeleton

## Objective

Create the reproducible Django REST Framework foundation without introducing
retrieval, ingestion, or generation logic.

## Why this task exists

Later retrieval phases need a consistent application layout, PostgreSQL 16 with
pgvector, Redis connectivity, and automated quality checks before feature work.

## Concepts

- Split settings keep shared, development, and production policy explicit.
- Compose health checks make dependency readiness observable.
- The health endpoint performs real PostgreSQL and Redis probes, returning HTTP
  503 if either required dependency is unavailable.

## Files Created

`pyproject.toml`, `uv.lock`, `.python-version`, `.env.example`, `.gitignore`,
`.pre-commit-config.yaml`, `Dockerfile`, `docker-compose.yml`, `manage.py`,
`config/`, the four required `apps/` packages, `tests/test_health.py`, and the
GitHub Actions CI workflow.

## File Explanations

`pyproject.toml` defines Python 3.11-compatible dependencies and quality-tool
configuration. `apps/qa/health.py` isolates dependency probes and
`apps/qa/views.py` exposes `GET /api/health/`. Compose defines `web`,
`postgres` (`pgvector/pgvector:pg16`), and `redis`, each with health checks.
A named container virtual-environment volume prevents a Windows host `.venv`
from masking Linux dependencies.

## Architecture

`web` waits for healthy `postgres` and `redis`, applies migrations, then serves
the public health route. Runtime configuration is environment-based; `.env` is
ignored by Git.

## Tests

- Ruff passed.
- MyPy passed with 23 source files checked.
- Pytest passed (one health-endpoint smoke test).
- Docker Compose brought up healthy web, PostgreSQL, and Redis services.
- A live health request returned database and Redis as connected, version 0.1.0.

## Lessons

On Windows, a bind-mounted repository can expose a host virtual environment to
a Linux container; isolate `/app/.venv` with a named Docker volume.

## Next Step

Remain in Phase 0 until explicitly directed to begin the next task.

---

# Session 002

Phase: Phase 0 — Documentation support
Task: Append-only theoretical knowledge record
Status: Complete

## Objective

Create an append-only knowledgebase that explains completed project work in a
continuous, task-oriented form.

## Why this task exists

The engineering log records implementation history and evidence. A separate
conceptual record makes architecture, rationale, and carried-forward constraints
easy to revisit during development and interview preparation.

## Concepts

Append-only documentation preserves the context in which decisions were made.
Corrections should be recorded as later entries rather than silently rewriting
prior understanding.

## Files Created

- `KNOWLEDGEBASE.md`

## File Explanations

`KNOWLEDGEBASE.md` defines its maintenance contract and contains the complete
theoretical explanation of Task 0.1.

## Architecture

The knowledgebase complements but does not override the immutable project
specification or the engineering log.

## Tests

Documentation-only change; no executable behavior changed.

## Lessons

Separating evidence-oriented engineering notes from conceptual explanations
makes both documents easier to use.

## Next Step

Append a new knowledgebase entry only when the next authorised task completes.

---

# Session 003

Phase: Phase 1 — Baseline
Task: Fetch and pin Django documentation corpus
Status: Complete

## Objective

Fetch the official Django documentation source at one reproducible Django 5.2
revision and record that pin in code and public documentation.

## Why this task exists

Retrieval experiments are only comparable when they use the same corpus. A
fixed source commit prevents silent documentation drift.

## Concepts

The corpus pin has four parts: version (`5.2`), tag (`5.2.9`), immutable Git
commit (`c14b756185c88f7f2eb745ff061f3c221fea9de7`), and source path.

## Files Created

- `config/corpus.py`
- `scripts/fetch_docs.sh`
- `tests/test_corpus.py`

## File Explanations

The corpus module centralises metadata. The fetch script uses sparse checkout to
obtain only `docs/`, verifies the commit, and safely succeeds on a repeat run.
The raw checkout is ignored because it is reproducible source data.

## Architecture

The local corpus resides at `data/django-5.2/docs`. Later parsers must use this
path and must not combine it with another Django documentation version.

## Tests

- Sparse checkout fetched and verified tag `5.2.9` at the pinned commit.
- A second script run confirmed idempotency.
- Ruff and MyPy passed.
- Pytest passed (2 tests).

## Lessons

The downloaded third-party source includes Python files outside DocuMind's type
quality contract, so ignored raw corpus data is excluded from MyPy analysis.

## Next Step

Proceed only to the authorised Phase 1 parser and heading-aware chunker task.

---

# Session 004

Phase: Phase 1 — Baseline
Task: RST parser and heading-aware chunker
Status: Complete

## Objective

Convert pinned Django RST files into provenance-preserving sections and
retrieval-ready chunks without relying on LangChain or another retrieval
framework.

## Why this task exists

Dense retrieval requires bounded text units, while the evaluation design
requires source paths and stable anchors that survive re-chunking. Parsing and
chunking establish both before database models or embeddings are added.

## Concepts

The parser recognises two-line RST headings and explicit RST targets. The
chunker groups paragraph blocks within each heading section, keeps indented code
blocks together, applies a configurable word-based overlap, and prefixes each
chunk with its full heading path for downstream embeddings.

## Files Created

- `apps/documents/parser.py`
- `apps/documents/chunker.py`
- `tests/test_documents_processing.py`

## File Explanations

`parser.py` returns immutable parsed-document and parsed-section dataclasses,
including corpus-relative source paths, heading paths, and anchors. `chunker.py`
returns immutable chunks with ordinal, provenance, prefixed text, and a
consistent lightweight token estimate. Tests cover heading nesting, explicit
anchors, code-block preservation, overlap validation, and heading prefixes.

## Architecture

RST file → `ParsedDocument` / `ParsedSection` → `DocumentChunk`. This is a
pure, database-free pipeline. Later ingestion persists its output, and later
embedding code uses the already-prefixed chunk text.

## Tests

- Ruff passed.
- MyPy passed with 28 source files checked.
- Pytest passed (5 tests).
- A real pinned-corpus smoke check parsed `topics/db/models.txt` into 37
  sections and 41 chunks.

## Lessons

Anchors must be derived from explicit RST targets when available and from a
predictable heading slug otherwise. This keeps evaluation labels independent of
database IDs and chunk ordinal changes.

## Next Step

Proceed only to the authorised Phase 1 models, migrations, and HNSW index task.

---

# Session 005

Phase: Phase 1 — Baseline
Task: Persistence models, migrations, and HNSW index
Status: Complete

## Objective

Persist the locked Document, Chunk, IngestionJob, and QueryLog data contracts in
PostgreSQL, with pgvector and Postgres full-text indexes ready for later work.

## Why this task exists

The parser and chunker produce in-memory values. The ingestion and retrieval
tasks require a durable, indexed representation that preserves their provenance
and supports dense and keyword search.

## Concepts

The `vector` PostgreSQL extension must exist before Django can create a
`VectorField(384)`. HNSW uses cosine operators with `m=16` and
`ef_construction=64`; Postgres full-text search uses a GIN index on the
`SearchVectorField`.

## Files Created

- `apps/documents/models.py`
- `apps/qa/models.py`
- `apps/documents/migrations/0001_initial.py`
- `apps/qa/migrations/0001_initial.py`
- `tests/test_models.py`

## File Explanations

Documents are idempotent by source path and documentation version. Chunks keep
source-derived provenance, text, token count, content hash, nullable 384-dim
embedding, and searchable text vector. Ingestion jobs track lifecycle state.
Query logs reserve the complete audit contract for later QA work.

## Architecture

The documents migration creates the pgvector extension before the chunk table,
then creates the cosine HNSW and full-text GIN indexes. The QA migration depends
on the configured Django user model for an optional query-log owner.

## Tests

- Ruff passed.
- MyPy passed with 31 source files checked.
- Pytest passed (7 tests).
- `makemigrations --check --dry-run` reported no pending schema changes.
- PostgreSQL confirmed the `vector` extension plus HNSW and GIN indexes.
- Documents and QA initial migrations applied successfully.

## Lessons

The pgvector Docker image contains the extension binary but does not enable it
in every database automatically; `VectorExtension()` must be in the migration
before a vector column is created.

## Next Step

Proceed only to the authorised Phase 1 embedder and ingestion-command task.

---

# Session 006

Phase: Phase 1 — Baseline
Task: Batch embedder and idempotent ingestion command
Status: Complete

## Objective

Populate the persisted chunk table with L2-normalised `bge-small-en-v1.5`
embeddings through a single, idempotent, testable ingestion pipeline.

## Why this task exists

Chunks exist without vectors after the persistence task. Dense retrieval,
the baseline evaluation, and every later mode require that each chunk carry a
384-dimension embedding produced by the pinned local model.

## Concepts

The embedder loads one cached `SentenceTransformer` per process and normalises
output so cosine distance matches the `vector_cosine_ops` HNSW index. BGE v1.5
adds a retrieval instruction prefix to queries only, never to documents.
Ingestion is idempotent at two levels: unchanged source files are skipped, and,
when a document changes, unchanged chunks keep their existing vector by matching
`content_hash`, so the encoder only runs on genuinely new text.

## Files Created

- `apps/documents/embedder.py`
- `apps/documents/ingestion.py`
- `apps/documents/management/__init__.py`
- `apps/documents/management/commands/__init__.py`
- `apps/documents/management/commands/ingest_docs.py`
- `tests/test_ingestion.py`

## File Explanations

`embedder.py` exposes `embed_documents`, `embed_query`, and a cached
`get_encoder`; it validates the encoder matrix shape before returning Python
lists. `ingestion.py` holds the deterministic pipeline (discover, parse, chunk,
embed, persist) with an injectable embedder so it can be tested without loading
a model, and records an `IngestionJob` lifecycle. `ingest_docs.py` is a thin
management command exposing `--corpus-root`, `--docs-version`, and `--limit`.
`test_ingestion.py` covers the vector-shape validator, idempotent re-ingestion,
embedding reuse on modification, and failure recording.

## Architecture

`data/django-5.2/docs` → `parse_rst_file` → `chunk_document` → `embed_documents`
→ `Chunk.objects.bulk_create`, wrapped in an `IngestionJob`. A document-level
`content_hash` gates rework; a chunk-level `content_hash` gates re-embedding.

## Tests

- Ruff passed.
- MyPy passed with 37 source files checked.
- Pytest passed (14 tests, including five new ingestion tests).
- `makemigrations --check --dry-run` reported no pending changes.
- Real ingestion of three corpus files created 3 documents and 14 chunks with
  384-dimension vectors.
- A second real ingestion reported `skipped=3`, confirming idempotency.
- Ingestion jobs were recorded with status `done`.

## Lessons

Title-only RST documents have no subheadings, so the parser initially emitted no
sections for them. The parser now treats a title's introductory body as its own
section. This surfaced only because ingestion exercised the full corpus path
rather than synthetic multi-heading fixtures.

## Next Step

Proceed only to the authorised Phase 1 `vector` retrieval mode and `/api/ask/`
endpoint with a plain prompt.

---

# Session 007

Phase: Phase 1 — Baseline
Task: Vector retrieval mode and plain-prompt /api/ask/ endpoint
Status: Complete

## Objective

Turn the embedded chunk store into a working question-answering API: a dense
`vector` retrieval mode, a provider-agnostic LLM client, and a
`POST /api/ask/` endpoint that returns an answer with citations and timings.

## Why this task exists

This is the first end-to-end query path and the baseline against which hybrid
and reranked retrieval will be compared. It also locks the `/api/ask/` request
and response contract used by every later phase and by the evaluation harness.

## Concepts

Dense retrieval orders chunks by pgvector cosine distance, which returns
similarity-ordered results directly from the HNSW index. The LLM is hidden
behind an `LLMClient` protocol so tests never touch a paid provider and the
provider can be swapped by settings alone. The plain prompt is isolated so the
Phase 3 citation-grounded contract replaces exactly one function.

## Files Created

- `apps/retrieval/types.py`
- `apps/retrieval/vector.py`
- `apps/retrieval/service.py`
- `apps/qa/llm_client.py`
- `apps/qa/generation.py`
- `apps/qa/serializers.py`
- `tests/test_retrieval_vector.py`
- `tests/test_ask.py`

## File Explanations

`types.py` defines the immutable `RetrievedChunk` with citation and audit
projections. `vector.py` runs the annotated cosine-distance query and converts
distance to similarity. `service.py` dispatches by mode and builds the numbered
context; unimplemented modes raise rather than silently returning baseline
results. `llm_client.py` defines the client protocol, response/usage dataclasses,
lazy Anthropic/OpenAI clients, and the plain prompt builder. `generation.py`
embeds once, retrieves, generates, times each stage, and writes a `QueryLog`.
`serializers.py` validates requests and documents the response shape.

## Architecture

```text
POST /api/ask/ (AskView)
  -> AskRequestSerializer (length, mode enum, top_k range)
  -> generation.answer_question
       -> embed_query
       -> retrieval.retrieve(mode=vector)
       -> build_context
       -> llm_client.generate_answer (plain prompt)
       -> QueryLog.objects.create
  -> {answer, refused, citations, mode, latency_ms}
```

`AskView` maps `UnsupportedModeError` to HTTP 400 and `LLMConfigurationError`
to HTTP 503, so misconfiguration is explicit rather than a 500.

## Tests

- Ruff passed.
- MyPy passed with 45 source files checked.
- Pytest passed (27 tests, including 13 new retrieval/ask tests).
- `makemigrations --check --dry-run` reported no changes.
- A real query against the ingested corpus returned 3 hits, top score 0.6826,
  with a genuine heading path.

## Lessons

Mypy's Django plugin crashed while analysing third-party `transformers` code;
the fix was to list the ML/LLM packages in the mypy overrides with
`follow_imports = "skip"` so only DocuMind code is type-checked. Also, annotating
the query-log owner with a custom protocol was rejected by the Django stubs, so
the concrete `User` type is imported under `TYPE_CHECKING` instead.

## Next Step

Proceed only to the authorised Phase 1 golden-set construction, metrics, and
baseline evaluation task.

---

# Session 008

Phase: Phase 1 — Baseline
Task: Golden-set schema hardening, retrieval metrics, and verification fixes
Status: Complete

## Objective

Repair the red quality gate left by untracked in-progress `eval/` work, build the
deterministic half of the Phase 1 evaluation harness (schema + metrics + tests),
verify every done task against live evidence, and hand over a single context file
a fresh model or reviewer can work from.

## Why this task exists

Session 007 ended with `eval/__init__.py` and `eval/golden_set.py` written but
untracked, and `mypy` failing on them — so the repository did not satisfy its own
definition of done. At the same time, the golden-set drafting (`build_golden_set.py`
needs an LLM key and a human review pass) could not be honestly completed in one
turn, but the schema, validation, and metric machinery could be finished
deterministically and tested without any model call. Finally, running the gates
for the first time outside Docker exposed environment and dependency defects that
had to be fixed or documented before anyone could trust the claimed state.

## Concepts

Record parsing uses explicit `isinstance` checks so malformed JSONL fails with a
precise message instead of being coerced into a plausible-looking question. The
metrics use ground truth as `(source_path, anchor)` pairs: a chunk satisfies a
gold source when both match, and an empty gold anchor is a path-level label
matching any section of that file. Recall@k is true per-question source recall
(matched gold sources / total gold sources, averaged); hit@k records whether any
gold source surfaced; MRR@k uses the first relevant rank. Unanswerable questions
have no ground truth, so they are excluded from retrieval metrics rather than
scored as failures — retrieval quality and refusal behaviour are separate
concerns measured by separate code.

## Files Created

- `eval/metrics.py`
- `tests/test_metrics.py`
- `tests/test_golden_set.py`
- `.dockerignore`
- `DOCUMIND_HANDOFF_CONTEXT.md`

## Files Modified

- `eval/golden_set.py` (typed parsing, `validate_golden_set`,
  `summarise_golden_set`, `GoldenSetValidationError`)
- `README.md` (quality-gate workflows, evaluation, deployment notes; stray line removed)
- `DOCUMIND_CONTEXT.md` (Section 17 tracker and session log)
- `KNOWLEDGEBASE.md` (Session 008 conceptual entry)

## File Explanations

`metrics.py` is import-light (only `apps.retrieval.types`, itself a plain
dataclass module) so the metric math stays independent of Django and the database.
`golden_set.py` keeps schema, I/O, validation, and reporting in one module so the
acceptance check for a future `build_golden_set.py` is a single function call.
`.dockerignore` keeps the pinned corpus (643 RST files plus its `.git` checkout),
the host `.venv`, and `.env` out of every future build context. The README gains
the two verified quality-gate workflows because the host/container hostname trap
had no documented answer anywhere. `DOCUMIND_HANDOFF_CONTEXT.md` consolidates the
verification report, every session's evidence, the production/deployment gap
analysis, and the exact procedure list for the remaining Phase 1 work.

## Architecture

```text
eval/golden_set.jsonl (future: 100 reviewed questions)
        |
        v
load_golden_set -> validate_golden_set (fail fast on bad data)
        |
        v
run_eval.py (future) -> retrieval.retrieve(mode) per question
        |
        v
RetrievalOutcome(question_id, answerable, retrieved, gold_sources)
        |
        v
compute_retrieval_metrics -> RetrievalMetrics.as_dict()
        |
        v
eval/results/<mode>_<split>_<date>.json (committed evidence)
```

## Tests

- Ruff passed.
- MyPy passed with 50 source files checked (previously 3 errors in
  `eval/golden_set.py`, now none; no blanket `type: ignore` introduced).
- Pytest passed: 59 tests (27 pre-existing + 32 new: 22 golden-set, 10 metrics),
  every expected metric value hand-computed in a comment above its assertion.
- `makemigrations --check --dry-run` reported no changes (exit 0 with the host
  `POSTGRES_HOST=localhost` override).
- Live database still holds 3 documents / 14 chunks (all embedded) / 2 jobs;
  corpus still pinned at `c14b756185c88f7f2eb745ff061f3c221fea9de7` with 643 files;
  pgvector extension plus HNSW and GIN indexes confirmed.

## Lessons

Three lessons for production readiness. First, the shipped `.env` is a Docker
contract, not a host contract: `POSTGRES_HOST=postgres` only resolves inside the
Compose network, so host-side gates need a `localhost` override — now documented.
Second, the lock resolves CUDA-capable torch on Linux while the Windows host
installed the CPU build; the resulting multi-GB re-download inside
`docker compose run web` stalled container-side testing entirely, so the next task
must pin CPU-only torch before anything that touches containers. Third, the image
is built `--no-dev` while `uv run` needs the dev group, which forces a re-sync on
every `compose run` — test tooling should be baked into a dev image or profile
once the lock is fixed.

## Next Step

Commit Session 008, then fix the CPU-only torch resolution (§6 defect A in
`DOCUMIND_HANDOFF_CONTEXT.md`), run the full corpus ingestion, draft and manually
review the 100-question golden set, implement `eval/run_eval.py`, and record the
`vector` baseline on `dev` then `heldout`.

---

# Session 009

Phase: Phase 1 — Baseline (handoff Step 1: infrastructure first)
Task: Pin CPU-only torch and re-verify the stack
Status: Complete

## Objective

Remove the CUDA-capable torch resolution that stalled every Linux container
workflow, re-sync and re-verify the full quality gate under the new lock, and
prove the embedding stack still produces genuine 384-dimensional vectors with an
isolated smoke ingestion — without touching the real `5.2` production rows.

## Why this task exists

Session 008's verification found that `uv.lock` resolved torch 2.14.0 from PyPI
with Linux CUDA dependencies, so `docker compose run web` downloaded a multi-GB
GPU stack and never reached the tests. That blocked container-side verification,
inflated CI cold caches, and shipped a GPU dependency a CPU-only service never
uses. Per the handoff procedure, this had to be fixed before the full corpus
ingestion and every later eval run.

## Concepts

`uv` resolves packages per the declared indexes. Adding `torch` as an explicit
dependency with a `[tool.uv.sources]` entry pointing at the PyTorch CPU wheel
index replaces the PyPI CUDA resolution with `torch 2.14.0+cpu` on every
platform, and drops the `cuda-bindings`, `cuda-toolkit`, `nvidia-*`, and `triton`
packages from the lock entirely. The fix is fully reversible because both
`pyproject.toml` and `uv.lock` are committed.

## Files Created

None. This task changes dependency resolution only.

## File Explanations

`pyproject.toml` gains the explicit `torch>=2.2,<3.0` dependency (with a comment
explaining the CPU-only rationale), an explicit `pytorch-cpu` index entry, and a
`[tool.uv.sources]` mapping. `uv.lock` shrinks by 250 lines: 45 insertions, 250
deletions, all CUDA/nvidia/triton removals plus the `+cpu` torch wheels.

## Architecture

```text
pyproject.toml (torch + pytorch-cpu index + sources)
        |
        v
uv lock -> CUDA/nvidia/triton gone, torch 2.14.0+cpu everywhere
        |
        v
uv sync -> host venv: 476 MB torch build replaced by the 118 MB CPU wheel
        |
        v
ingest_docs (isolated temp corpus, distinct doc_version) -> 384-dim vector
```

## Tests

- Ruff passed.
- MyPy passed with 50 source files checked.
- Pytest passed: 59 tests, unchanged.
- Interpreter reports `torch 2.14.0+cpu`, `cuda_available=False`; `uv.lock`
  contains zero `nvidia-`/`cuda-toolkit`/`triton`/`cuda-bindings` entries.
- Embedding smoke: `ingest_docs --corpus-root <temp/RST> --docs-version
  torch-smoke` created 1 document / 1 chunk with `embedded=1`; PostgreSQL
  `vector_dims(embedding)` returned **384**; the smoke `Document`, its `Chunk`,
  and its `IngestionJob` were then deleted child-first, restoring the production
  data to exactly 3 documents / 14 chunks / 2 jobs (all embeddings present).

## Lessons

Two operational lessons. First, the 476 MB host `torch` directory number did not
mean the host had CUDA: Windows PyPI wheels bundle broadly, while the lock's
Linux markers selected CUDA extras that Windows never installed — which is why
the defect only bit inside Linux containers. Second, raw cross-DB deletes do not
follow Django's `on_delete=CASCADE`: deleting the smoke `Document` row directly
raised a foreign-key violation, so cleanup had to run child-first
(`Chunk` → `Document` → `IngestionJob`). If smoke cleanup ever grows beyond
throwaway rows, do it through the ORM or a management command so cascade rules
apply.

## Next Step

Proceed to handoff Step 2: the full corpus ingestion against the pinned Django
5.2 checkout, verifying chunk counts, non-null embeddings, and a `done`
`IngestionJob` before any eval work begins.

---

# Session 010

Phase: Phase 1 — Baseline
Task: Ollama Cloud LLM provider and live end-to-end RAG
Status: Complete

## Objective

Remove the last user-facing blocker (missing LLM configuration) by adding an
`ollama` provider that reaches Ollama-hosted models through their
OpenAI-compatible cloud endpoint, then prove the full `/api/ask/` pipeline
live: retrieval over indexed chunks, remote generation, citations, and query
logging.

## Why this task exists

The API previously answered every question with HTTP 503 because no provider
credentials were configured. A local 30B model was rejected on hardware
grounds (16 GB RAM, CPU-only), so the chosen path is Ollama Cloud: the same
provider surface with no local RAM cost, no model download, and negligible
eval cost. The provider seam keeps Anthropic/OpenAI unchanged and local
Ollama reachable through `LLM_BASE_URL`.

## Concepts

Ollama exposes an OpenAI-compatible API, so the existing `OpenAILLMClient`
serves both `openai` and `ollama` providers; only the base URL differs. The
key-format check identified the configured key as an Ollama key rather than an
Anthropic key. A curl probe of `https://ollama.com/v1/models` listed the
available cloud models, and `gpt-oss:20b` was selected as the best
grounded-QA quality-per-cost choice.

## Files Created

None. Four files changed: `apps/qa/llm_client.py`,
`config/settings/base.py`, `.env.example`, and `tests/test_ask.py`.

## File Explanations

`llm_client.py` registers the `ollama` provider in the factory map, routing
through `OpenAILLMClient` with `settings.LLM_BASE_URL` or the
`OLLAMA_CLOUD_BASE_URL` default. `base.py` adds the optional `LLM_BASE_URL`
setting. `.env`/`.env.example` set `LLM_PROVIDER=ollama` and
`LLM_MODEL=gpt-oss:20b`. Two new tests prove the factory returns the cloud
client and honours a local-server override.

## Architecture

```text
POST /api/ask/ -> embed (bge-small, cached) -> vector top-k (HNSW)
              -> generation via Ollama Cloud (gpt-oss:20b)
              -> citations + QueryLog row
```

The container reaches `https://ollama.com` directly, so no host networking is
required.

## Tests


---

# Session 011

Phase: Phase 1 — Baseline
Task: Full corpus ingestion and live LLM validation
Status: Complete

## Objective

Ingest the entire pinned Django 5.2 corpus (643 RST files), verify every
chunk is embedded, recheck all service connections, and validate the LLM
end-to-end over the full index with on-corpus and off-corpus questions.

## Why this task exists

Session 010 proved the pipeline against 14 smoke chunks only. The evaluation
work that follows needs the real index; the baseline numbers would be
meaningless without it.

## Concepts

The detached `docker compose exec -d` run keeps ingestion alive across host
shell sessions while writing a log to the bind-mounted repository. The job
row's `doc_count`/`chunk_count` update at completion; live progress is
observable through the document/chunk tables.

## Files Created

None. Ingestion and verification only; documentation updated.

## File Explanations

`documents_ingestionjob` row 4 recorded `done` with `doc_count=640`,
`chunk_count=6487`. The chunk table holds 6,487 rows with 6,487 non-null
384-dimensional embeddings across 643 distinct documents (640 ingested this
run plus the 3 pre-existing smoke documents, idempotently skipped where
unchanged).

## Architecture

RST corpus (643 files) → parser → chunker → batch bge-small embeddings →
PostgreSQL (HNSW + GIN). The live QA path is unchanged: embed query → HNSW
top-k → Ollama Cloud generation → citations → QueryLog.

## Tests

- Ingestion job 4: `done`, no error, 640 docs / 6487 chunks in ~13 minutes.
- `SELECT count(embedding)` equals chunk count (6487/6487).
- Health endpoint 200; Redis PONG; PostgreSQL reachable.
- Live LLM checks: raw-SQL question answered with correct citations;
  select_related/prefetch_related answered accurately (top score 0.86,
  cited `ref/models/querysets`); an off-corpus weather question was
  correctly declined instead of hallucinated.
- Ruff and MyPy clean; 61 pytest tests passing.

## Lessons

Chunk counts exceeded the 1,000-3,000 planning estimate; the honest number
(6,487) is recorded and must be used in the README rather than the estimate.
The `refused` flag remains Phase 3 contract (exact `INSUFFICIENT_CONTEXT`
marker); the plain prompt's soft refusal still behaved correctly.

## Next Step

Proceed to the golden-set drafting and review, then `run_eval.py` and the
vector baseline.

- Ruff passed. MyPy passed (50 files). Pytest passed (61 tests).
- Live: health 200; two real questions answered with citations and scores.
- QueryLog rows 1-2 recorded `mode=vector`, `model=gpt-oss:20b`, token
  accounting (625/234 and 436/319).
- Warm latency: embed 18 ms, retrieve 16 ms, LLM ~3.5 s, total ~3.6 s.

## Lessons

An interrupted `uv sync` inside a container can leave a silently corrupted
package (a truncated `transformers` produced a misleading circular-import
error). Deleting the `web_venv` volume and recreating the container forces a
clean, uninterrupted sync. Also: Windows `curl` sends PowerShell-mangled JSON
unless the payload is written to a file without a UTF-8 BOM.

## Next Step

Proceed to the full-corpus ingestion, then the golden-set build task.

