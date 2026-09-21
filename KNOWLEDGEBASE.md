# DocuMind Knowledgebase

This is the append-only theoretical knowledge record for DocuMind. It explains
what each completed task changed, why the change exists, how its parts relate,
and what later work can safely assume. It complements `ENGINEERING_LOG.md`:
the engineering log is the development journal and verification evidence; this
file is the durable conceptual sketch.

## How to maintain this file

- Add a new dated section for each completed task or meaningful milestone.
- Do not rewrite earlier entries to make the history look cleaner. Add a later
  correction or clarification section when understanding changes.
- Record implementation facts, design rationale, assumptions, constraints, and
  verification results.
- Preserve the locked architecture in `DOCUMIND_CONTEXT.md`. This knowledgebase
  explains decisions; it does not override them.

---

## 2026-09-20 â€” Phase 0, Task 0.1: Repository Foundation

### Purpose

Task 0.1 establishes a minimal, reproducible backend platform on which the
future RAG system can be built. It intentionally contains no ingestion,
chunking, embeddings, retrieval, reranking, LLM, or evaluation logic. Those
belong to later phases and must not be introduced prematurely.

### What changed

- The project now targets Python 3.11, Django 5.2, and Django REST Framework.
- Dependencies and development tools are defined in `pyproject.toml` and locked
  in `uv.lock` for repeatable installs.
- Django configuration is split into `config/settings/base.py`, `dev.py`, and
  `prod.py`.
- Domain packages now exist for `accounts`, `documents`, `retrieval`, and `qa`.
- Docker Compose defines three required services: `web`, PostgreSQL 16 with
  pgvector, and Redis.
- A public `GET /api/health/` endpoint verifies PostgreSQL and Redis
  connectivity.
- Ruff, MyPy, pytest, pre-commit, and a GitHub Actions CI skeleton provide the
  first quality gate.

### Why these foundations matter

The project will eventually persist documents, chunks, vectors, full-text
indexes, jobs, and query logs in PostgreSQL. Selecting the pgvector-enabled
PostgreSQL image now ensures later vector fields and HNSW indexes can be added
without replacing the database service.

Redis is present before Celery is introduced because the locked architecture
uses Redis as Celery's broker/result backend. It is deliberately only a checked
dependency in Task 0.1; no background tasks exist yet.

The four Django apps establish bounded ownership before code grows:

| App | Intended responsibility in later phases |
| --- | --- |
| `accounts` | JWT authentication and request throttling |
| `documents` | Documentation models, parsing, chunking, embedding, ingestion |
| `retrieval` | Vector search, Postgres full-text search, RRF, reranking |
| `qa` | Query API, LLM interface, grounded generation, citations |

### Configuration model

`base.py` holds settings shared by every environment: installed applications,
middleware, database configuration, Redis URL, and application version.
`dev.py` permits local debugging and local hosts. `prod.py` turns debugging off
and enables HTTPS-oriented cookie and proxy settings.

All runtime values are read from environment variables. `.env.example` is a
safe template; a local `.env` is ignored by Git so passwords and API keys are
never committed. This keeps the application portable between local Docker, CI,
and deployment environments.

### Runtime flow

```text
browser or monitoring client
            |
            v
GET /api/health/ --> Django/DRF `HealthCheckView`
            |                 |
            |                 +--> PostgreSQL connection probe
            |                 +--> Redis PING probe
            v
200 healthy, or 503 unhealthy
```

The endpoint is unauthenticated because infrastructure and deployment systems
need to check service readiness before a user is authenticated. It returns the
application version plus individual dependency states. A dependency failure
does not get hidden behind a generic success response: the API returns HTTP 503
and reports the failing dependency as `disconnected`.

### Container model

```text
web
 |-- waits for healthy postgres
 |-- waits for healthy redis
 |-- applies Django migrations
 `-- starts the development server

postgres: pgvector/pgvector:pg16
redis:    redis:7-alpine
```

Compose health checks ensure that service startup is based on readiness, not
only process launch order. PostgreSQL uses `pg_isready`; Redis uses
`redis-cli ping`; the web service requests its own health endpoint.

The repository is bind-mounted into the development container. On Windows, the
host `.venv` contains Windows executables and cannot run inside Linux. A named
Docker volume is therefore mounted at `/app/.venv`, separating the container's
Linux environment from the host environment.

### Quality and reproducibility model

`uv.lock` fixes the resolved dependency versions. Ruff checks basic correctness,
imports, and modern Python usage. MyPy checks type contracts with Django and DRF
stubs. Pytest contains a smoke test that verifies the expected healthy JSON
response while mocking external dependency probes; this makes the unit test
fast and independent of a running Docker stack.

The CI workflow recreates these checks in GitHub Actions with PostgreSQL and
Redis service containers. It runs linting, type checking, and tests from the
committed lock file.

### Verification completed

- `uv run ruff check .` passed.
- `uv run mypy .` passed.
- `uv run pytest` passed (one smoke test).
- `docker compose up --build -d` started healthy web, PostgreSQL, and Redis
  services.
- A live request returned:

  ```json
  {
    "status": "healthy",
    "database": "connected",
    "redis": "connected",
    "version": "0.1.0"
  }
  ```

### Constraints carried forward

- Keep the pinned Python 3.11 / Django 5 / PostgreSQL 16 / pgvector / Redis
  foundation unless explicitly directed otherwise.
- Do not add RAG logic until the next authorised phase task.
- Add tests for every new module and keep Ruff and MyPy clean.
- Append future knowledge entries; do not replace this Task 0.1 record.

### Next theoretical milestone

The next authorised Phase 0 task can build on this foundation. Its knowledge
entry should describe only the work actually completed and link back to this
entry where it relies on the settings, service, or quality structure above.

---

## 2026-09-20 â€” Phase 1, Task: Fetch and pin the Django documentation corpus

### Purpose

The baseline retrieval system needs stable source text before it can parse,
chunk, embed, or evaluate anything. This task selects one immutable Django
documentation revision and makes obtaining it repeatable.

### Corpus identity

| Property | Pinned value |
| --- | --- |
| Documentation family | Django 5.2 |
| Upstream release tag | `5.2.9` |
| Immutable source commit | `c14b756185c88f7f2eb745ff061f3c221fea9de7` |
| Upstream repository | `https://github.com/django/django.git` |
| Local documentation path | `data/django-5.2/docs` |

The tag is convenient for people, but the commit hash is the actual
immutability guarantee. The upstream tag is annotated, so the fetch script
verifies the resolved commit rather than only trusting the tag name.

### What changed

`config/corpus.py` contains constants future ingestion code can import.
`scripts/fetch_docs.sh` performs a sparse checkout, requests only the upstream
`docs/` tree, and verifies the final commit. It exits successfully without
redownloading when the right checkout already exists; it stops if a conflicting
checkout exists. The raw corpus is ignored by Git because the versioned script
and commit make it reproducible without committing third-party source.

### Why RST source is preferred

The Django repository's reStructuredText retains document paths, headings,
paragraphs, and code blocks more directly than scraped HTML. The next task can
therefore create heading-aware chunks and stable source anchors for later
golden-set labels.

### Relationship to later retrieval work

```text
pinned Django RST source
          |
          v
parser and heading-aware chunker
          |
          v
stable source path + heading anchor + chunk text
          |
          v
embeddings, PostgreSQL records, and retrieval evaluation
```

Every retrieval mode must use this same corpus. Otherwise apparent quality
differences might result from corpus drift instead of retrieval changes.

### Quality boundary discovered

The raw Django documentation includes Python modules for its Sphinx build.
Those files are third-party data rather than DocuMind application code. MyPy
initially discovered them and produced unrelated errors, so `data/` is excluded
from MyPy while DocuMind code remains strictly type-checked.

### Verification completed

- The sparse checkout fetched and verified the pinned commit.
- A second script invocation confirmed idempotency.
- Ruff, MyPy, and both pytest tests passed.

### Constraints carried forward

- Do not mix another Django version into the corpus directory.
- Later ingestion must retain source paths and stable heading-derived anchors.
- Improve the parser rather than editing the upstream corpus.
- The next authorised work is the parser and heading-aware chunker.

---

## 2026-09-20 â€” Phase 1, Task: RST parser and heading-aware chunker

### Purpose

This task turns the pinned Django documentation from raw RST files into small,
traceable units that later stages can store, embed, retrieve, and evaluate. It
is deliberately hand-written so every transformation is explainable and no
retrieval framework hides the mechanics.

### The processing model

```text
RST file
  |
  v
parser: title + heading sections + anchors
  |
  v
chunker: paragraph groups + code-block preservation + overlap
  |
  v
retrieval-ready chunk: source path, heading path, anchor, ordinal, text
```

`parse_rst_file()` reads a corpus file and records its path relative to the
pinned `docs/` root. That relative path is the stable document identity used by
later golden-set labels. `parse_rst()` can also operate on in-memory RST text,
which makes parser tests fast and focused.

### Heading and anchor handling

The parser recognises conventional two-line RST headings: a non-indented title
followed by a uniform adornment line such as `====` or `----`. The first heading
becomes the document title. Later headings form a path, for example:

```text
Models > Quick example > Field options
```

An explicit RST target like `.. _field-options:` is preferred as the section
anchor because it matches the upstream documentation's stable link identity.
When no target exists, a predictable slug of the heading path is used. This is
why an evaluation label can reference a document path and anchor rather than a
database chunk ID.

### Chunk boundaries and context

The chunker never crosses a heading section, so a chunk has unambiguous topical
provenance. Within a section it groups blocks separated by blank lines up to a
default target of 400 lightweight word tokens, adding 50 tokens of overlap to
the following chunk. These are configuration constants rather than model-token
counts; a future tokenizer can refine the count without changing source
identity.

Indented code blocks stay together as a single block. They may make an
individual chunk exceed the target, which is intentional: splitting a code
example damages the technical meaning more than a slightly larger chunk harms
retrieval. Each final chunk starts with its heading path, preserving context for
the later embedding model.

### Provenance contract

Every `DocumentChunk` carries:

| Field | Why it matters |
| --- | --- |
| `source_path` | Identifies the pinned RST document |
| `heading_path` | Provides human-readable context and embedding prefix |
| `anchor` | Stable retrieval/evaluation label within a document |
| `ordinal` | Preserves position within an ingestion run |
| `text` | Heading-prefixed text for future embedding |
| `token_count` | Supports chunk-size observability and later persistence |

The model layer in the next task should persist these values without changing
their semantic meaning.

### Verification completed

- Unit tests verified nesting, explicit anchors, code-block preservation,
  heading prefixes, chunk ordinals, and invalid overlap rejection.
- The real `topics/db/models.txt` corpus file produced 37 sections and 41
  chunks.
- Ruff, MyPy, and all five pytest tests passed.

### Constraints carried forward

- Do not replace this hand-written pipeline with LangChain.
- Keep code blocks intact during later ingestion transformations.
- Store source path and anchor alongside every chunk.
- The next authorised work is persistence models, migrations, and the pgvector
  HNSW index; do not begin embedding or query retrieval yet.

---

## 2026-09-20 â€” Phase 1, Task: Persistence models, migrations, and indexes

### Purpose

This task gives the parser and chunker output a durable database representation.
It establishes the exact persistence contract needed before embeddings and
ingestion are introduced.

### Data model map

```text
Document 1 ----- * Chunk

IngestionJob     tracks one ingestion lifecycle
QueryLog         records one future QA request and its evidence
```

`Document` identifies an upstream RST source with its title, documentation
version, canonical URL, and content hash. A unique `(source_path, doc_version)`
constraint makes re-ingestion idempotent at the document level.

`Chunk` belongs to exactly one document and stores the parser/chunker
provenance contract: heading path, anchor, ordinal, text, token count, and
content hash. Its unique `(document, ordinal)` constraint prevents duplicate
positions in a document. The embedding is nullable because the parser can
persist chunks before the later embedder populates vectors.

`IngestionJob` captures pending, running, done, and failed states plus document
and chunk counts. `QueryLog` already reserves the audit fields required by the
locked QA design, but no query endpoint or LLM behavior is implemented yet.

### Index strategy

| Index | Field | Future use |
| --- | --- | --- |
| HNSW (`vector_cosine_ops`) | `Chunk.embedding` | Dense cosine retrieval |
| GIN | `Chunk.search_vector` | PostgreSQL full-text search |
| B-tree | content hashes | Idempotent ingestion lookup |
| Unique constraints | source/version and document/ordinal | Data integrity |

The HNSW parameters are deliberately fixed at `m=16` and
`ef_construction=64`, matching the architecture specification. They establish
the graph quality/build-cost tradeoff before baseline measurement begins.

### Why pgvector extension migration matters

Installing the `pgvector` Python package lets Django describe a vector field,
but PostgreSQL also needs its server-side `vector` type. The pgvector Docker
image provides that extension binary; `VectorExtension()` activates it in the
actual `documind` database. It must run before the migration creates
`vector(384)`, otherwise PostgreSQL rejects the table definition.

### Verification completed

- Both initial migrations applied to the live PostgreSQL container.
- `vector` was confirmed as an enabled database extension.
- The HNSW cosine index and GIN full-text index were confirmed in PostgreSQL.
- Django found no ungenerated model migrations.
- Ruff, MyPy, and seven pytest tests passed.

### Constraints carried forward

- Embeddings remain exactly 384 dimensions for `BAAI/bge-small-en-v1.5`.
- Keep HNSW cosine settings at `m=16` and `ef_construction=64` unless explicitly
  changing a locked decision.
- Do not claim Postgres full-text search is BM25.
- The next authorised work is batch embedding and an idempotent ingestion
  command; retrieval endpoints remain out of scope.

---

## 2026-09-20 â€” Phase 1, Task: Batch embedder and idempotent ingestion

### Purpose

This task fills the previously nullable `Chunk.embedding` column and turns the
in-memory parser/chunker output into queryable database rows. It is the last
Phase 1 step before the `vector` retrieval mode, and it establishes the
provenance-preserving text that dense retrieval will later search.

### The ingestion pipeline

```text
pinned RST files (data/django-5.2/docs)
        |
        v
parse_rst_file -> ParsedDocument / ParsedSection
        |
        v
chunk_document -> DocumentChunk (heading-prefixed text)
        |
        v
embed_documents -> L2-normalised 384-dim vectors
        |
        v
Chunk.objects.bulk_create  (recorded by one IngestionJob)
```

Every run â€” success or partial failure â€” writes an `IngestionJob` so the
operation is auditable. A per-document exception is captured into the job's
`error` field and the run is marked `failed` rather than silently succeeding.

### The embedding contract

`apps/documents/embedder.py` wraps a single `SentenceTransformer` instance in an
`lru_cache`, so the model is loaded once per process and shared by ingestion and
(query time) retrieval. That is important because model loading dominates the
first request's latency and because reranking and embedding must not reload the
same weights repeatedly.

Two details keep the vectors compatible with the database:

| Decision | Reason |
| --- | --- |
| `normalize_embeddings=True` | The HNSW index uses `vector_cosine_ops`; unit vectors make cosine and inner-product equivalent |
| Query-only instruction prefix | BGE v1.5 documents recommend the retrieval prefix for queries, not documents; applying it to both would distort relevance |

The encoder is described by a narrow `Encoder` protocol rather than the concrete
class, which both narrows the surface DocuMind depends on and lets MyPy accept
the third-party return value through a single `cast`.

### Why ingestion is idempotent at two levels

1. **Document level.** Each document stores a SHA-256 of its raw RST bytes. If
   the bytes are unchanged, the whole document is skipped and its chunks are
   never rewritten. This makes re-running `ingest_docs` cheap and safe.
2. **Chunk level.** When a document *does* change, existing chunk embeddings are
   indexed by `content_hash`. Any chunk whose text is byte-identical keeps its
   previous vector, and only genuinely new or edited chunks are re-embedded.

This second level matters for evaluation: as the chunker evolves, unchanged text
does not pay the encoder cost again, and embedding stability is preserved.

### Testability and dependency injection

`ingest_corpus` accepts an `embed_texts` callable defaulting to
`embed_documents`. Unit tests inject a deterministic fake that records its
inputs, so the ingestion logic is exercised without downloading or running a
model. This keeps tests fast and network-free while the production default still
uses the real encoder.

### A parser gap discovered by real data

Running the pipeline over real corpus files exposed a defect that synthetic
fixtures had hidden: a document whose only heading is its title produced no
sections, and therefore no chunks. The parser now emits a title section for that
introductory body. This is the intended benefit of exercising the full path
rather than only unit fixtures.

### Verification completed

- Ruff and MyPy passed (37 source files, no type errors).
- All 14 pytest tests passed, including idempotent re-ingestion, embedding
  reuse on modification, and failure recording.
- Ingestion of three real corpus files created 3 documents and 14 chunks, each
  with a 384-dimension vector; a second run reported `skipped=3`.
- Both runs recorded `done` ingestion jobs.

### Constraints carried forward

- All embeddings must remain 384 dimensions and L2-normalised.
- Do not apply the BGE query prefix to document text.
- Re-use embeddings by `content_hash`; do not drop and re-embed unchanged text.
- The next authorised work is the `vector` retrieval mode and a plain-prompt
  `/api/ask/` endpoint; hybrid search, reranking, and generation grounding
  remain out of scope until their phases.

---

## 2026-09-20 â€” Phase 1, Task: Vector retrieval mode and /api/ask/

### Purpose

This task converts the embedded chunk store into the first working query path.
It establishes the baseline retrieval mode and freezes the `/api/ask/` contract
that later phases and the evaluation harness depend on.

### The query path

```text
POST /api/ask/  {question, mode, top_k}

---

## 2026-09-21 â€” Phase 1, Task: Ollama Cloud provider and live end-to-end RAG

### Purpose

The retrieval pipeline was complete and tested, but every `/api/ask/` call
returned HTTP 503 because no LLM was configured. This task adds the missing
generation provider and proves the whole chain â€” retrieval, generation,
citations, audit logging â€” against the live service.

### Provider decision

A local 30B-class model was evaluated and rejected: the machine has 16 GB RAM
and no NVIDIA GPU, and a 30B model needs roughly 25 GB just for weights. The
selected path is **Ollama Cloud**: models run remotely behind an
OpenAI-compatible API, so the existing `OpenAILLMClient` works unchanged with
only a different base URL. The configured key is an Ollama API key; a
`/v1/models` probe confirmed reachability and listed the available models.
`gpt-oss:20b` was chosen for grounded QA quality per unit cost; the exact
model name is recorded with every eval result because cloud models can be
retired.

### What changed

- `apps/qa/llm_client.py` registers an `ollama` provider that routes through
  `OpenAILLMClient` with `settings.LLM_BASE_URL` falling back to
  `https://ollama.com/v1`. Anthropic and OpenAI behaviour is unchanged, and a
  local Ollama server remains available by setting `LLM_BASE_URL`.
- `config/settings/base.py` adds the optional `LLM_BASE_URL` setting.
- `.env.example` and the local `.env` set `LLM_PROVIDER=ollama` and
  `LLM_MODEL=gpt-oss:20b`.
- Two factory tests cover the cloud default and the local override.

### Verified end-to-end behaviour

With `web` recreated on a clean virtual-environment volume, the live API
returned real grounded answers with citations and similarity scores for two
real questions, and PostgreSQL recorded both `QueryLog` rows with
`model=gpt-oss:20b` and token accounting. Warm request latency measured
embed 18 ms, retrieve 16 ms, LLM ~3.5 s, total ~3.6 s; the first request
additionally paid the one-time in-container bge-small model download.

### Operational lessons

---

## 2026-09-21 â€” Phase 1, Task: Full corpus ingestion and live LLM validation

### Purpose

The QA pipeline had only been proven against 14 smoke chunks. Evaluation
numbers require the real index, so the entire pinned corpus (643 RST files)
was ingested and the LLM path re-validated over it.

### What the index now holds

| Measure | Value |
| --- | --- |
| Documents | 640 (this run) + 3 smoke docs = 643 |
| Chunks | 6,487 |
| Embedded chunks | 6,487 / 6,487 (100%) |
| Job state | `done`, no error, ~13 minutes |

The chunk count exceeded the 1,000-3,000 planning estimate. The honest
measured number is what the README must carry.

### Live validation over the full index

- A raw-SQL question returned a correct answer with a code example, cited to
  `topics/db/sql/` sections.
- A select_related versus prefetch_related question returned an accurate
  technical answer cited to `ref/models/querysets/`, top similarity 0.86.
- An off-corpus question (weather) was declined rather than answered â€” the
  plain prompt's grounding instruction held.

### Constraints carried forward

- The `refused` boolean still maps only to the Phase 3 `INSUFFICIENT_CONTEXT`
  contract; soft refusals under the plain prompt are not flagged yet.
- Any re-ingestion must remain idempotent via content hashes; do not wipe the
  index between retrieval experiments without recording it.
- Next authorised work: golden-set drafting (Step 3 of the handoff), manual
  review of at least 40 questions, then `run_eval.py` and the baseline.


An interrupted container dependency sync can corrupt a package so subtly that
the failure surfaces as an unrelated circular import; deleting the
`web_venv` volume and recreating the container forces a clean sync. On
Windows, JSON request bodies must be written to a file without a UTF-8 BOM
and passed via `--data-binary @file`, or PowerShell quoting mangles them.

### Constraints carried forward

- Record `LLM_MODEL` with every evaluation result; cloud models can be
  retired by the provider.
- The API key stays in `.env` only and must never be committed.
- Answers currently draw from only 3 indexed documents; full-corpus
  ingestion is the next authorised task before any evaluation numbers.

        |
        v
AskRequestSerializer  -> validation (length, mode enum, top_k 1..10)
        |
        v
answer_question
        |-- embed_query(question)            -> 384-dim query vector
        |-- retrieve(mode)                    -> ranked RetrievedChunk list
        |-- build_context                     -> numbered [chunk_id] blocks
        |-- generate_answer (plain prompt)    -> LLM text + usage
        |-- QueryLog.objects.create           -> audit record
        v
{answer, refused, citations, mode, latency_ms}
```

### Why cosine distance is the ordering signal

Chunk embeddings are L2-normalised and the column is indexed with
`vector_cosine_ops`. `CosineDistance` returns `1 - cosine_similarity`, so an
ascending `ORDER BY distance` yields the most similar chunks first and lets the
HNSW index do the ordering. The retrieved score exposed to clients is
`1 - distance`, i.e. the cosine similarity.

### Mode dispatch is honest, not silently degraded

Only `vector` is implemented in Phase 1, but `hybrid` and `hybrid_rerank` are
valid modes in the API. `service.retrieve` raises `UnsupportedModeError` for
valid-but-unimplemented modes and `AskView` maps that to HTTP 400. Returning
baseline results for an unimplemented mode would corrupt the evaluation, so it
is refused instead.

### The provider-agnostic LLM boundary

Generation depends only on the `LLMClient` protocol and the `LLMResponse` /
`LLMUsage` dataclasses. Provider SDKs are imported lazily inside the concrete
clients, so importing the module never needs an SDK or key, and switching
providers is a settings change. Because tests inject a fake client, no paid API
is ever contacted in the suite.

### Plain prompt now, grounded prompt later

Phase 1 intentionally uses a plain prompt that answers only from the provided
context. The citation-grounded contract, refusal handling, and citation
validation belong to Phase 3. Isolating the prompt in `build_plain_prompt` means
that upgrade is one function, and the two prompts can be compared directly on
faithfulness as the results table requires.

### Audit and timing

Each request records `embed`, `retrieve`, `rerank`, `llm`, and `total`
milliseconds in `QueryLog.latency_ms` and in the response. `rerank` is present as
zero so the response shape never changes when Phase 3 adds reranking. Query
logging is wrapped so an audit failure can never break a user response.

### Verification completed

- Ruff and MyPy passed (45 source files, no type errors).
- All 27 pytest tests passed (13 new retrieval/ask tests).
- `makemigrations --check --dry-run` reported no changes.
- A real query returned 3 hits with a top similarity of 0.6826 and a genuine
  heading path, proving the full embed â†’ retrieve path against real data.

### Constraints carried forward

- Keep the `/api/ask/` request and response shape stable for the evaluation
  harness.
- Never return baseline results for an unimplemented mode.
- Keep the LLM behind the `LLMClient` protocol; never call a provider in tests.
- The next authorised work is the 100-question golden set, `metrics.py`, and
  `run_eval.py` to record the baseline vector numbers.

---

## 2026-09-21 â€” Phase 1, Task: Golden-set schema hardening, retrieval metrics, and verification

### Purpose

This task completes the deterministic, model-free half of the Phase 1 evaluation
harness and repairs the quality gate that Session 007 left red. The golden
questions themselves (LLM drafting plus human review) remain future work; what
exists now is the machinery that makes those questions measurable â€” and the
proof that everything built so far is genuinely green.

### What changed

`eval/golden_set.py` was rewritten into a strict contract: typed record parsing
with explicit `isinstance` checks, a `GoldenSetValidationError` raised for every
malformed input, `validate_golden_set()` for dataset-level invariants (ID pattern
`q\d{3}`, duplicate IDs, dev+heldout coverage, answerable/unanswerable shape,
`.txt` path shape, on-disk corpus check), and `summarise_golden_set()` for the
counts the README must eventually quote.

`eval/metrics.py` implements Recall@k, hit@k, and MRR@k from scratch. Ground truth
is `(source_path, anchor)` because chunk IDs do not survive re-chunking; an empty
gold anchor is a path-level label. Recall is genuine per-question source recall,
not a binary hit rate, and unanswerable questions are excluded from retrieval
metrics because refusal is a generation concern measured elsewhere (Phase 3).

### Verification completed

- Ruff passed; MyPy passed (50 source files, zero errors, no blanket ignores).
- All 59 pytest tests passed (27 pre-existing + 32 new with hand-computed values).
- `makemigrations --check --dry-run` reported no changes.
- Live PostgreSQL re-confirmed: `vector` extension, HNSW + GIN indexes,
  3 documents / 14 chunks (all embedded) / 2 jobs.
- Corpus re-confirmed: tag `5.2.9`, commit
  `c14b756185c88f7f2eb745ff061f3c221fea9de7`, 643 `.txt` files.

### Deployment defects discovered

The project's first run of the gates outside Docker surfaced two real
infrastructure defects, recorded with evidence and fixes in
`DOCUMIND_HANDOFF_CONTEXT.md` Â§6: the lock resolves CUDA-capable torch on Linux
(multi-GB downloads stalling container workflows), and `docker compose run`
re-syncs dev dependencies on every invocation because the image is built
`--no-dev`. A `.dockerignore` was added immediately; the torch pin is scoped as
the first step of the next task.

### Constraints carried forward

- Do not build `run_eval.py` before the reviewed golden file exists; metrics
  without ground truth are decoration.
- Tune nothing on `heldout`; run `dev` for sanity, `heldout` once for the record.
- Keep `eval/` free of framework and provider dependencies so the harness stays
  runnable in CI without model weights or API keys.
- The next authorised work is the CPU-only torch fix, full corpus ingestion,
  golden-set drafting and review, `run_eval.py`, and the locked `vector` baseline.

---

## 2026-09-21 â€” Phase 1, Task: Pin CPU-only torch and re-verify the stack

### Purpose

Make the dependency lock match the service's actual hardware: CPU everywhere.
This removes the silent CUDA resolution that made container workflows unusable
and keeps CI caches and the production image free of a GPU stack the workload
never exercises.

### What changed

`pyproject.toml` now declares `torch>=2.2,<3.0` explicitly with a
`[tool.uv.sources]` mapping to the PyTorch CPU wheel index. `uv.lock` dropped
`cuda-bindings`, `cuda-toolkit`, all `nvidia-*` packages, and `triton`
(250 deletions), resolving `torch 2.14.0+cpu` on every platform instead.

### Verification completed

- Ruff, MyPy (50 files), and all 59 pytest tests passed under the new lock.
- The interpreter reports `torch 2.14.0+cpu` with CUDA unavailable.
- An isolated smoke ingestion (`torch-smoke` version, temp corpus) produced a
  genuine embedding whose `vector_dims()` in PostgreSQL is 384; the smoke rows
  were deleted child-first, restoring the production data exactly.
- A raw cross-table `DELETE` does not trigger Django cascades â€” cleanup must run
  child-first when done in SQL.

### Constraints carried forward

- Every future lock regeneration must be checked for `nvidia-`, `cuda-toolkit`,
  `triton`, and `cuda-bindings` entries before it is committed.
- Full corpus ingestion is the next authorised work; no eval numbers may be
  recorded until it completes with all embeddings present.

---

## 2026-09-21 â€” Phase 1, Task: Live golden-set draft

### Purpose

The baseline evaluation needs a fixed question set whose answers exist in the
indexed corpus and whose provenance is trustworthy. This task produced that
draft by letting the LLM draft questions from real ingested chunks while the
database, not the model, supplies every gold source.

### How provenance is protected

The LLM sees 9 sampled chunk excerpts per topic area and returns questions
referencing chunks by index only. Python resolves each index against the
sampled chunks and copies the path/anchor from the database row. A hallucinated
path can therefore never enter the dataset; an out-of-range or duplicate index
question is silently dropped. Out-of-range indices are additionally caught as
`IndexError` so a misbehaving model cannot crash the run.

### Dataset shape and split discipline

Ten topic areas Ã— 9 answerable questions = 90, plus 10 unanswerable questions
= 100 total. The dev/heldout assignment uses fixed offset sets (3 heldout per
early block, 2 per late block, unanswerable blocks 1/3/5 to heldout), yielding
exactly 70 dev / 30 heldout with zero randomness. Re-running with identical
LLM output reproduces the identical file.

### Reproducibility metadata

Each drafted question's `notes` field records the generating model (e.g.
`model=gpt-oss:20b`). If the drafting model changes later, results remain
attributable. Environment provenance matters too: `uv run --env-file .env`
does not override already-set OS variables, so a stale shell `LLM_PROVIDER`
can silently redirect provider selection â€” clear process env vars before
debugging provider behaviour.

### Verification completed

- Ruff, MyPy (52 files), and 71 pytest tests passed.
- Live draft run produced `eval/golden_set_draft.jsonl`: 100 questions,
  90 answerable / 10 unanswerable, 70 dev / 30 heldout.
- Every gold source is a database-verified (path, anchor) pair.

### Constraints carried forward

- The draft is not the golden set until the owner reviews â‰¥40 questions.
- Do not tune retrieval against heldout questions at any point.
- The next authorised work is the manual review + promotion to
  `eval/golden_set.jsonl`, then `run_eval.py` and the vector baseline.

---

## 2026-09-21 - Phase 1, Task: Golden-set draft hardening and canonical artifact

### Purpose

After the first live draft run, the quality gates surfaced three harness
defects. Fixing them before the review step guarantees the artifact the owner
reviews comes from a clean, fully gated pipeline.

### What changed

- Out-of-range LLM chunk indices are now dropped (`IndexError` handled) instead
  of crashing the draft loop - defensive parsing against imperfect LLM output.
- The canonical draft artifact is `eval/drafts/golden_set_draft.jsonl`,
  separating generated artifacts from the eval package root and from the
  future committed `eval/golden_set.jsonl`.
- A stale OS-level `LLM_PROVIDER=anthropic` was diagnosed as the cause of a
  confusing 401 during the first run: `uv --env-file` does not override
  variables already present in the environment.

### Why provenance discipline matters

The draft flow samples chunks from PostgreSQL and lets the LLM choose excerpts
by index only; path/anchor pairs are attached in Python from the database. A
hallucinated source therefore cannot enter the golden set - a property worth
preserving as review and promotion proceed.

### Verification completed

- Ruff clean; MyPy clean (52 files); 71 pytest tests passed.
- Live re-run: 100 questions (90 answerable / 10 unanswerable), 70 dev /
  30 heldout, each with a DB-verified gold source; model name recorded in
  per-question notes for reproducibility.

### Constraints carried forward

- Review is a human task: at least 40 questions before promotion; record the
  count in the README.
- Never tune against `heldout`.
- Next authorised work: promotion to `eval/golden_set.jsonl`, then
  `eval/run_eval.py` and the vector baseline on dev and heldout.
