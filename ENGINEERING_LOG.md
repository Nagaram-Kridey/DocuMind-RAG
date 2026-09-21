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
