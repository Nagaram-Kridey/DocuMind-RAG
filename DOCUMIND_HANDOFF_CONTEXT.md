# DOCUMIND_HANDOFF_CONTEXT.md

> **Purpose:** Complete, verified handoff context for DocuMind-RAG. This file lets a
> fresh AI model (or a human) pick up the project with zero prior conversation,
> knowing exactly what is built, what is verified, what is broken, and what to do next.
>
> **Companion documents (read in this order):**
> 1. `DOCUMIND_CONTEXT.md` — the immutable specification. **Highest authority.**
> 2. `CODEX_CONTEXT.md` — the original working prompt and coding standards.
> 3. `DOCUMIND_HANDOFF_CONTEXT.md` — this file: verified state + next steps.
> 4. `ENGINEERING_LOG.md` — chronological implementation journal with evidence.
> 5. `KNOWLEDGEBASE.md` — conceptual/theoretical record of each task.
>
> **Last verified:** 2026-09-21 (Section 3 lists the evidence).
> **Repository:** https://github.com/Nagaram-Kridey/DocuMind-RAG
> **Verified commit:** `04532af` (branch `main`; Session 008 committed; Session 009
> CPU-only torch fix verified in the working tree, pending commit)

---

## 1. How to use this file

1. Read `DOCUMIND_CONTEXT.md` fully first. It defines the architecture, the phase
   plan, and the acceptance criteria. This file never overrides it.
2. Read Section 3 (Verification Report) so you know which claims are proven and
   which are not. Do not assume unverified work exists.
3. Read Section 6 (gap analysis), then Section 7 for the immediate next task with
   concrete steps.
4. Obey the documentation contract in Section 10. Every completed task updates
   `ENGINEERING_LOG.md`, `KNOWLEDGEBASE.md`, and `DOCUMIND_CONTEXT.md` Section 17.

**Hard rules carried forward (from `DOCUMIND_CONTEXT.md` §0 and `CODEX_CONTEXT.md` §4):**

- Never fabricate a metric. `__` placeholders stay until a real run writes
  `eval/results/*.json`.
- Build phase by phase. Do not start Phase 2 work while a Phase 1 acceptance
  criterion is unmet unless explicitly told to.
- No LangChain (or any retrieval framework) for chunking, fusion, retrieval, or
  evaluation. Everything must be hand-written and interview-explainable.
- Every new module ships with pytest tests. `ruff` and `mypy` must stay clean.
- Secrets only via environment variables. Never commit `.env`.

---

## 2. Project in one paragraph

DocuMind is a Django 5 + DRF backend that ingests the official **Django 5.2
documentation** (pinned to tag `5.2.9`, commit
`c14b756185c88f7f2eb745ff061f3c221fea9de7`), stores heading-aware chunks in
**PostgreSQL 16 + pgvector**, and answers questions with **citation-grounded**
LLM output. It exposes three switchable retrieval modes — `vector` (dense
baseline), `hybrid` (dense + Postgres full-text merged with hand-written RRF),
and `hybrid_rerank` (hybrid + cross-encoder reranking) — so the contribution of
each stage can be **measured**, not asserted. The star deliverable is the
three-way results table on a held-out 100-question golden set, plus a CI gate
that fails when retrieval quality regresses.

**Non-goals:** multi-tenant SaaS, model fine-tuning, rich frontend, agent
behaviour, multi-corpus support. Kubernetes is an optional stretch only.

---

## 3. Verification report (2026-09-21)

This section records what was actually executed and observed. Commands were run
from the repository root on Windows (PowerShell) with Docker Desktop running and
the pinned corpus already fetched.

### 3.1 Quality gates

| Gate | Command | Result |
| --- | --- | --- |
| Lint | `uv run --env-file .env ruff check .` | **PASS** — "All checks passed!" |
| Types | `uv run --env-file .env mypy .` | **PASS** — "Success: no issues found in 50 source files" |
| Tests | `$env:POSTGRES_HOST='localhost'; uv run --env-file .env pytest` | **PASS** — `59 passed` |
| Schema | `makemigrations --check --dry-run` | **PASS** — "No changes detected" (exit 0) |

> **Environment trap (important):** with `.env` unmodified, `mypy` and `pytest`
> fail on the host with `failed to resolve host 'postgres'`. That is **not** a code
> defect — `POSTGRES_HOST=postgres` is the Compose service name and only resolves
> inside the Compose network. Host runs must override it to `localhost`. See §9.

### 3.2 Test inventory (59 tests, all passing)

| Test file | Tests | Covers |
| --- | --- | --- |
| `tests/test_golden_set.py` | 22 | Golden-set schema, JSONL round-trip, dataset validation, summary counts |
| `tests/test_metrics.py` | 10 | Hand-computed Recall@k, hit@k, MRR@k, source matching, zero-division safety |
| `tests/test_ask.py` | 8 | Plain prompt, LLM config errors, `/api/ask/` happy path, validation, unimplemented mode |
| `tests/test_ingestion.py` | 7 | Embedder shape validation, idempotency, embedding reuse, failure recording |
| `tests/test_retrieval_vector.py` | 5 | Cosine ordering, `top_k` limit, mode dispatch, context/lookup helpers |
| `tests/test_documents_processing.py` | 3 | Heading nesting, anchors, code-block preservation, overlap, heading prefixes |
| `tests/test_models.py` | 2 | Vector dimensions, HNSW/GIN config, unique constraints, query-log defaults |
| `tests/test_health.py` | 1 | Health endpoint healthy payload |
| `tests/test_corpus.py` | 1 | Corpus pin constants |

**Session delta:** 27 tests before this session → **59 tests** after (+32).

### 3.3 Infrastructure and data

| Check | Observation |
| --- | --- |
| `docker compose ps` | `postgres` (pgvector/pgvector:pg16) healthy, `redis` (redis:7-alpine) healthy. `web` was **not** running (exited 3 h prior). |
| pgvector extension | `SELECT extname FROM pg_extension` → `plpgsql`, **`vector`** |
| Chunk indexes | `chunks_embedding_hnsw_idx` (HNSW), `chunks_search_vector_gin_idx` (GIN), `chunks_content_hash_idx`, `chunks_unique_document_ordinal`, PK, document FK |
| Row counts | `documents_document = 3`, `documents_chunk = 14`, `documents_chunk WHERE embedding IS NOT NULL = 14`, `documents_ingestionjob = 2`, `qa_querylog = 0` |
| Pinned corpus | `data/django-5.2` at commit `c14b756185c88f7f2eb745ff061f3c221fea9de7`, tag `5.2.9`, **643 `.txt` files** |
| Docker image | `documind-rag-web:latest` = 714 MB; `/app/.venv` = 60 MB; the corpus is **not** baked into the image |
| Git | HEAD `d95a882`, branch `main`; working tree clean apart from the two `eval/` files added this session |

### 3.4 Defects found and fixed this session

| # | Defect | Impact | Fix |
| --- | --- | --- | --- |
| 1 | `mypy` failed with 3 errors in untracked `eval/golden_set.py` | The quality gate was red: the repo did not satisfy its own definition of done | Rewrote record parsing with explicit `isinstance` checks and typed helpers, **no blanket `type: ignore`**; added a test for every rejection path |
| 2 | No `.dockerignore` | `data/` (~640 RST files **plus a full `.git` checkout**), the host `.venv`, and `.env` would enter future build contexts — bloated, slow, platform-poisoned images | Added `.dockerignore` excluding `data/`, `.venv/`, `.git/`, `.env`, caches, coverage output |
| 3 | `README.md` ended with a stray meaningless line ("LLM Based RAG Project with 100 Golden Questions Template usage") | Looked careless on the public repo | Removed; replaced with real "Running the quality gates", "Evaluation", and "Deployment notes" sections |
| 4 | README documented no way to run the quality gates | No reviewer could reproduce any claim; the host/container `POSTGRES_HOST` trap was undocumented | Documented both supported workflows with exact commands (§9) |
| 5 | `eval/` was untracked and untested | "Every module ships with pytest tests" was violated | Added `tests/test_golden_set.py` (22 tests) and `tests/test_metrics.py` (10 tests) |

### 3.5 Claims still NOT verified — do not repeat them as fact

| Claim | Status |
| --- | --- |
| Full corpus ingested (~1,000–3,000 chunks) | **NOT DONE.** Only a 3-file / 14-chunk smoke ingestion exists; the corpus has 643 RST files. |
| Baseline Recall@5 / MRR@10 numbers | **NOT MEASURED.** Still `__`. No `eval/results/` directory exists. |
| Golden set of 100 questions | **NOT BUILT.** Only the schema, loader, validator, and metrics exist. |
| 100% test pass inside Docker | **NOT CONFIRMED.** 59/59 confirmed on the host with the `localhost` override. |
| `hybrid` / `hybrid_rerank` modes | **NOT IMPLEMENTED.** They raise `UnsupportedModeError`; the API returns HTTP 400 by design. |
| RAGAS faithfulness / answer relevancy | **NOT RUN.** |
| Coverage ≥ 85% | **NOT MEASURED.** `pytest-cov` is not yet configured. |
| Locust p50/p95 | **NOT RUN.** `loadtest/` does not exist. |
| JWT, throttling, Celery, OpenAPI, structlog | **NOT IMPLEMENTED.** |
| `search_vector` populated | **NOT POPULATED.** The GIN index exists but every row is `NULL`, so full-text search returns nothing until Phase 2 writes it (via `UpdateTrigger`/`SearchVector` update or a migration backfill). |
| OpenSearch/BM25 keyword search | **NOT USED and not planned.** Keyword search is Postgres full-text (`ts_rank`), which is **not** BM25. Never claim BM25. |
| Golden set manually reviewed (≥ 40 questions) | **NOT DONE.** No questions exist yet, so nothing has been reviewed. |
| Resume bullets with real numbers | **NOT WRITTEN.** All `__` placeholders remain in `DOCUMIND_CONTEXT.md` §15 and §16. |

---

## 4. Complete task history (commit by commit)

Full work record from project start to the present. Each session has a matching
detailed entry in `ENGINEERING_LOG.md` and a conceptual entry in `KNOWLEDGEBASE.md`.

### Session 001 — Phase 0: Repository foundation (`e5297fb`)

- Established the reproducible Django 5 + DRF foundation: `pyproject.toml`,
  `uv.lock`, `.python-version` (3.11), `.env.example`, `.gitignore`,
  `.pre-commit-config.yaml`, `Dockerfile`, `docker-compose.yml`, `manage.py`.
- Split settings into `config/settings/base.py`, `dev.py`, `prod.py`.
- Created the four domain app packages: `apps/accounts`, `apps/documents`,
  `apps/retrieval`, `apps/qa`.
- Compose services: `web`, `postgres` (`pgvector/pgvector:pg16`), `redis`
  (`redis:7-alpine`), all with health checks. Added a named `web_venv` volume so a
  Windows host `.venv` cannot mask the container's Linux environment.
- `GET /api/health/` performs real PostgreSQL and Redis probes and returns HTTP 503
  when either is unavailable.
- Added `.github/workflows/ci.yml` (ruff, mypy, pytest) and a health smoke test.
- **Evidence:** live request returned
  `{"status":"healthy","database":"connected","redis":"connected","version":"0.1.0"}`.

### Session 002 — Phase 0: Documentation support

**No code change.** Created `KNOWLEDGEBASE.md` as an append-only conceptual
record, separated from the evidence-oriented engineering log.

### Session 003 — Phase 1: Pin the Django documentation corpus (`95af372`)

- Pinned Django docs to version `5.2`, tag `5.2.9`, commit
  `c14b756185c88f7f2eb745ff061f3c221fea9de7`, mirrored in `config/corpus.py`.
- Added `scripts/fetch_docs.sh`: sparse checkout of `docs/` only, verifies the
  resolved commit, idempotent on re-run, hard-fails on a conflicting checkout.
- `data/` is Git-ignored (reproducible third-party source) and excluded from mypy.
- **Evidence:** commit verified by `git rev-parse HEAD`; a second script run
  reported the pin was already correct.

### Session 004 — Phase 1: RST parser and heading-aware chunker (`792f950`)

- `apps/documents/parser.py` — hand-written RST parsing: two-line headings,
  explicit `.. _target:` anchors (preferred) with a predictable heading-slug
  fallback, corpus-relative `source_path`, nested heading paths.
- `apps/documents/chunker.py` — paragraph grouping within a section, indented code
  blocks kept intact, 400-token target with 50-token overlap, and each chunk's text
  prefixed with its full heading path.
- **Evidence:** the real `topics/db/models.txt` produced 37 sections / 41 chunks.

### Session 005 — Phase 1: Persistence models, migrations, indexes (`f98597d`)

- `apps/documents/models.py` — `Document`, `Chunk`, `IngestionJob`.
  `apps/qa/models.py` — `QueryLog`.
- `Chunk.embedding = VectorField(dimensions=384, null=True)`,
  `Chunk.search_vector = SearchVectorField(null=True)`.
- Idempotency: unique `(source_path, doc_version)` on `Document`, unique
  `(document, ordinal)` on `Chunk`.
- Indexes: HNSW (`vector_cosine_ops`, `m=16`, `ef_construction=64`), GIN on
  `search_vector`, B-tree on content hashes.
- Migration `0001_initial` runs `VectorExtension()` **before** creating the vector
  column — the image ships the extension binary but does not enable it per database.
- **Evidence:** migrations applied; `vector` extension, HNSW, and GIN confirmed live
  in PostgreSQL.

### Session 006 — Phase 1: Batch embedder and idempotent ingestion (`15845e6`)

- `apps/documents/embedder.py` — lazily loaded, process-cached
  `BAAI/bge-small-en-v1.5` encoder; L2-normalised vectors; batch size 32; the BGE
  query instruction prefix applied to queries only; strict output-shape validation.
- `apps/documents/ingestion.py` — document-level content-hash skip, chunk-level
  `content_hash` matching to recycle unchanged embeddings, `bulk_create` inside a
  transaction, and a recorded `IngestionJob` lifecycle. The embedder is injectable
  so tests never load a model.
- `apps/documents/management/commands/ingest_docs.py` — `--corpus-root`,
  `--docs-version`, `--limit`; non-zero exit when any file fails.
- **Evidence:** a real 3-file run created 3 documents / 14 chunks with 384-dim
  vectors; a repeat run reported `skipped=3`.
- **Lesson recorded:** title-only RST documents have no subheadings, so the parser
  was updated to treat a title's introductory body as its own section. This only
  surfaced by exercising the real corpus.

### Session 007 — Phase 1: `vector` mode and plain-prompt `/api/ask/` (`d95a882`, current HEAD)

- `apps/retrieval/types.py` — immutable `RetrievedChunk` with `as_citation()` and
  `as_retrieved()` projections for the API and the audit log.
- `apps/retrieval/vector.py` — annotated `CosineDistance` query ordered ascending,
  exposed as similarity (`1 - distance`).
- `apps/retrieval/service.py` — mode dispatch (`vector` implemented; `hybrid` and
  `hybrid_rerank` raise `UnsupportedModeError`), numbered context builder, and a
  chunk lookup used for citation validation.
- `apps/qa/llm_client.py` — `LLMClient` protocol, `LLMResponse`/`LLMUsage`
  dataclasses, lazily imported Anthropic/OpenAI clients, and `build_plain_prompt()`
  isolated so the Phase 3 grounded-prompt swap is one function.
- `apps/qa/generation.py` — embed once → retrieve → build context → generate →
  per-stage timings → `QueryLog`; audit failure can never break a response.
- `apps/qa/serializers.py`, `apps/qa/views.py` — request validation; `AskView` maps
  `UnsupportedModeError` → 400 and `LLMConfigurationError` → 503 so misconfiguration
  is explicit rather than a 500.
- **Evidence:** a real query returned 3 hits with top similarity 0.6826 and a
  genuine heading path.

### Session 009 — Phase 1: CPU-only torch pinned and stack re-verified (Session 009, committed separately)

- `pyproject.toml` declares `torch>=2.2,<3.0` with a `[tool.uv.sources]` mapping to
  the PyTorch CPU index; `uv.lock` dropped CUDA/nvidia/triton (−250/+45 lines).
- Re-verified: ruff / mypy (50 files) / 59 tests green; interpreter reports
  `2.14.0+cpu`, CUDA unavailable.
- Embedding smoke under the new lock produced a real 384-dim vector
  (`vector_dims()`), then cleaned child-first back to 3 docs / 14 chunks / 2 jobs.

### Session 008 — Phase 1: Golden-set schema, metrics, and verification (this session)

**Status:** changes are in the working tree; `eval/__init__.py` and
`eval/golden_set.py` are still untracked from the previous session and must be
committed together with the new files.

- `eval/__init__.py` — package docstring stating the harness is deliberately plain
  Python.
- `eval/golden_set.py` — hardened. `GoldenQuestion`/`GoldSource` dataclasses, JSONL
  round-trip, and **typed record parsing with no `type: ignore`**. Added
  `validate_golden_set()` (ID pattern `q\d{3}`, duplicate IDs, dev+heldout coverage,
  answerable ⇒ gold sources, unanswerable ⇒ no gold sources, `.txt` path shape, and
  an optional on-disk corpus existence check) and `summarise_golden_set()`.
- `eval/metrics.py` — **new**, hand-written retrieval metrics: `matches_gold_source()`
  (path + anchor, where an empty anchor means a path-level label),
  `first_relevant_rank()`, `recall_at_k()` (true per-question source recall),
  `hit_at_k()`, `mrr_at_k()`, and `compute_retrieval_metrics()` returning a
  JSON-serialisable payload. Unanswerable questions are excluded from retrieval
  metrics instead of being scored as failures.
- `tests/test_golden_set.py` (22 tests) and `tests/test_metrics.py` (10 tests) — all
  expected values are hand-computed in comments above the assertions.
- `.dockerignore` — new; deployment fix (§3.4 item 2).
- `README.md` — removed a stray line; added "Running the quality gates",
  "Evaluation", and "Deployment notes" sections (≈70 new lines).
- **Evidence:** `ruff` clean; `mypy` clean over 50 files; `pytest` 59 passed;
  `makemigrations --check --dry-run` reports no changes.
- **Lesson recorded:** running the quality gates on the Windows host requires
  `POSTGRES_HOST=localhost`, because `.env` carries the Compose service name. This
  was invisible until the gates were run outside Docker, and it is why the README
  now documents both workflows.

---

## 5. Complete file inventory (what exists, what it does, its state)

### 5.1 Root

| File | State | Notes |
| --- | --- | --- |
| `pyproject.toml` | ✅ committed | Python 3.11, Django 5.2, DRF 3.15, pgvector, redis, gunicorn, numpy, sentence-transformers, anthropic, openai. Ruff (E/F/I/UP, 100 cols), mypy strict with overrides for ML/LLM libs, pytest-django config. |
| `uv.lock` | ✅ committed (Session 009: CUDA entries removed, `torch 2.14.0+cpu` on all platforms) | See §6 defect A (now fixed). |
| `.python-version` | ✅ | 3.11. |
| `manage.py` | ✅ | Stock Django entrypoint. |
| `Dockerfile` | ✅ | `python:3.11-slim`, `uv sync --frozen --no-dev`, gunicorn CMD (2 workers). See §6 for gaps. |
| `docker-compose.yml` | ✅ | `web` / `postgres` / `redis` with health checks; named `web_venv` + `postgres_data` volumes. `web` overrides CMD with `runserver` — dev only. |
| `.dockerignore` | ✅ new (Session 008) | Excludes `data/`, `.venv/`, `.git/`, `.env`, caches. |
| `.env`, `.env.example` | ⚠️ | `.env` exists locally (ignored); `.example` is the template. `POSTGRES_HOST=postgres` is correct **only inside Compose**. |
| `.pre-commit-config.yaml` | ✅ | ruff + ruff-format + mypy hooks. |
| `.github/workflows/ci.yml` | ✅, needs hardening | ruff + mypy + pytest with pgvector/redis services and HF cache. Missing: coverage, retrieval eval gate, `pip-audit` (§6). |
| `README.md` | ✅ updated (Session 008) | Setup, ingestion, `/api/ask/`, quality-gate workflows, evaluation, deployment notes. Results table is intentionally absent until real numbers exist. |
| `DOCUMIND_CONTEXT.md` | ✅, update §17 pending | Immutable spec; §17 needs the Session 008 entry. |
| `ENGINEERING_LOG.md` | ✅, Session 008 pending | Detailed journal through Session 007. |
| `KNOWLEDGEBASE.md` | ✅, Session 008 pending | Conceptual record through Session 007. |
| `DOCUMIND_HANDOFF_CONTEXT.md` | ✅ new (Session 008) | This file. |
| `CODEX_CONTEXT.md` | ✅ | Original working prompt; its §5 progress table mentioning "Phase 0 just begun" is stale — superseded by this file and §17. |
| `scripts/fetch_docs.sh` | ✅ | Verified idempotent sparse-fetch + commit check. |
| `src/documind_rag/__init__.py` | ⚠️ dead scaffold | Contains a `main()` printing "Hello from documind-rag!". Exists only because `pyproject.toml` uses the `uv_build` backend. **Leave it alone** — removing it breaks `uv sync` — but no code may depend on it. |
| `data/django-5.2/` | ✅ local only, ignored | Pinned corpus, 643 `.txt` files, verified commit. Never commit; never bake into the image. |

### 5.2 `config/`

`corpus.py` (pin constants), `urls.py` (`/api/` → `apps.qa.urls`), `wsgi.py`,
`settings/base.py` (env-driven, `APP_VERSION="0.1.0"`, DRF JSON-only, LLM settings),
`settings/dev.py` (`DEBUG`/`ALLOWED_HOSTS` from env), `settings/prod.py`
(`DEBUG=False`, HTTPS cookie flags, `SECURE_SSL_REDIRECT`). All behave as specified.

### 5.3 `apps/documents/`

`parser.py` ✅, `chunker.py` ✅, `models.py` ✅, `embedder.py` ✅,
`ingestion.py` ✅, `management/commands/ingest_docs.py` ✅, `migrations/0001_initial.py` ✅,
`apps.py` ✅. No `tasks.py` / Celery wiring yet — correct for Phase 1 (sync first).

### 5.4 `apps/retrieval/`

`types.py` ✅, `vector.py` ✅, `service.py` ✅, `apps.py` ✅.
**Missing by design (Phases 2–3):** `keyword.py`, `fusion.py` (RRF), `rerank.py`.

### 5.5 `apps/qa/`

`health.py` ✅, `views.py` ✅ (`HealthCheckView`, `AskView`), `urls.py` ✅
(`health/`, `ask/`), `serializers.py` ✅, `llm_client.py` ✅, `generation.py` ✅,
`models.py` ✅ (`QueryLog`), `migrations/0001_initial.py` ✅.
**Missing by design (Phase 4):** JWT views, throttles; **missing (Phase 3):**
grounded prompt, refusal, citation validation.

### 5.6 `apps/accounts/`

Only `apps.py` + migrations state — an empty placeholder. JWT work belongs here in Phase 4.

### 5.7 `eval/`

`__init__.py` ✅, `golden_set.py` ✅ (hardened Session 008), `metrics.py` ✅ new.
**Missing (rest of Phase 1):** `golden_set.jsonl`, `build_golden_set.py`,
`run_eval.py`, `ragas_eval.py`, `results/` — see §7 for exact procedures.

### 5.8 `tests/`

Nine files, 59 tests, all passing (§3.2). No `conftest.py` — none is needed
(default DB, no global fixtures).

---

## 6. Production and deployment gap analysis

Ordered by impact. Items A–C materially affect reproducibility, cost, or
correctness; the rest are the already-planned Phase 2–4 scope.

### DEFECT A — PyTorch resolves to the CUDA stack everywhere, silently (HIGH)

**Evidence.** `uv.lock` resolves `torch 2.14.0` from PyPI with
`sys_platform == 'linux'` CUDA dependencies (`cuda-bindings`, `cuda-toolkit`,
`nvidia-*`, `triton`). The Windows host happened to install `torch 2.14.0+cpu`
(476 MB, `cuda_available=False`, zero `nvidia-*` packages), but inside Linux the
same lock pulls the multi-GB CUDA stack: a `docker compose run web uv run pytest`
was observed downloading `torch`, `triton`, and a dozen `nvidia-*` wheels and
never finished in the time available. No `[tool.uv]` source or index pin exists
in `pyproject.toml`, so this is luck on Windows and pain on Linux/CI.

**Impact.**
1. CI (`uv sync --all-groups --frozen`) downloads gigabytes on every cold cache.
2. The production image carries a GPU stack a CPU-only workload never uses.
3. Fresh container workflows (`run`, fresh builds) stall for many minutes.

**Recommended fix (verified 2026-09-21 — applied as Session 009).**
The fix below is now the locked state, kept here as the record of what was done
and why. Declared CPU-only torch explicitly in `pyproject.toml`:

```toml
dependencies = [
  ...,
  "torch>=2.2,<3.0",
  ...
]

[[tool.uv.index]]
name = "pytorch-cpu"
url = "https://download.pytorch.org/whl/cpu"
explicit = true

[tool.uv.sources]
torch = { index = "pytorch-cpu" }
```

Observed result of `uv lock`: CUDA/nvidia/triton entries dropped from `uv.lock`
(`-250/+45` lines), `torch 2.14.0+cpu` resolved on all platforms, host venv
re-synced to the 118 MB CPU wheel, and the interpreter reports `2.14.0+cpu`
with CUDA unavailable. Re-verified: ruff clean, mypy clean (50 files), 59/59
tests green. Embedding smoke (`ingest_docs --corpus-root <temp/RST>`
`--docs-version torch-smoke`) produced 1 doc / 1 chunk with `embedded=1` and
`vector_dims(embedding) = 384`; smoke rows deleted child-first
(`Chunk` → `Document` → `IngestionJob`), restoring exactly 3 docs / 14 chunks /
2 jobs. Lesson: raw SQL `DELETE` does not follow Django `on_delete=CASCADE`.
**Still open:** re-running the container test workflow end-to-end (cheap now that
the lock is CPU-only, but not yet re-attempted), then the dev-image/profile work
in item 2 below.

### DEFECT B — `docker compose run web` re-syncs dependencies on every invocation (HIGH)

**Evidence.** The image is built with `uv sync --frozen --no-dev`, but `uv run`
inside a `compose run` resolves the dev group (`pytest`, `mypy`, `ruff`) and
re-syncs into `web_venv` — which, given Defect A, means gigabytes of download.
Two consecutive `compose run … pytest` invocations both stalled with zero test
output; `docker logs` showed wheel downloads, and both containers had to be
removed (45% CPU while downloading).

**Impact.** The README's Docker workflow is currently unusable in practice, and
any operator running `compose run` for migrations or ingestion pays the same tax.

**Recommended fixes (in order).**
1. Fix Defect A first — a CPU-only lock makes the re-sync cheap.
2. Then add a dedicated `test` or `dev-tools` Compose profile (or a
   `Dockerfile.dev` that syncs `--all-groups`) so test/dev tooling is baked in
   once, not re-resolved per invocation.
3. Re-verify: `docker compose run --rm -T --no-deps web uv run pytest -q` must
   complete and print `59 passed` (update the count as tests grow).

### GAP C — Development server is the composed runtime (MEDIUM)

`docker-compose.yml` overrides the image's gunicorn CMD with
`manage.py runserver`. That is correct for local work and wrong for anything
else: `runserver` is single-process, non-threaded by default, auto-reloads, and
is explicitly not for production. For deployment the change is `command:` → the
gunicorn invocation (or a `compose.prod.yml` overlay), `DJANGO_SETTINGS_MODULE`
→ `config.settings.prod`, a non-root `USER` in the image, and a reverse proxy
in front. The README's "Deployment notes" now states the boundary explicitly;
do not let `runserver` behind a public port.

### GAP D — CI has no teeth yet (MEDIUM)

Today's `ci.yml` runs ruff, mypy, pytest. The locked plan requires more:

1. **Coverage gate.** Add `pytest-cov`, fail under 85%.
2. **Retrieval eval smoke gate.** After the baseline exists (§7), run `run_eval.py`
   on a fixed ~20-question smoke subset against a pre-ingested fixture and fail
   below the recorded thresholds. Fast, CPU-only, no LLM calls.
3. **Dependency audit.** Add `pip-audit` (at least as `continue-on-error` while
   the lock's CUDA packages still trigger noise — resolved by Defect A).
4. **Cache discipline.** The HF cache key should include the lock hash
   (`hashFiles('uv.lock')`), not just the model name, so a model change cannot
   reuse a stale cache.

### GAP E — No database connection pooling or request timeouts (MEDIUM)

`DATABASES` has no `CONN_MAX_AGE`, no `OPTIONS` timeouts, and DRF has no throttle
classes yet. For a CPU-bound embedding service behind gunicorn workers this is a
slow-client and connection-churn risk. Phase 4 adds throttling; connection pooling
(`CONN_MAX_AGE` or PgBouncer) and Gunicorn `--timeout` tuning belong in the same
hardening pass. Locust results (§6-excluded until Phase 4) will justify the values.

### GAP F — `search_vector` is `NULL` on every row (LOW now, blocks Phase 2)

The GIN index exists but is dead weight: ingestion never populates
`search_vector`. Phase 2 must add the population mechanism — a Postgres
`UpdateTrigger`, a save-time `SearchVector(...)` update, or a migration backfill
— and a regression test asserting `search_vector IS NOT NULL` after ingestion.
Until then, any claim about hybrid retrieval is fictional.

### Later-phase scope (already planned, not yet started)

Phase 2: `keyword.py` (Postgres full-text), `fusion.py` (hand-written RRF with
`k=60`), `mode=hybrid`, hybrid results saved. Phase 3: `rerank.py`
(cross-encoder, top-30 → top-5), citation-grounded prompt, `INSUFFICIENT_CONTEXT`
refusal, citation validation, RAGAS faithfulness/relevancy, grounded-vs-plain
comparison. Phase 4: JWT (`simplejwt`), DRF throttles, Celery + Redis ingestion
endpoints, drf-spectacular docs, structlog, Locust, CI eval gate, 85%+ coverage,
README results table, resume bullets — and the production items C–E above.

---

## 7. Next task (Phase 1 remainder): golden set → baseline numbers

Phase 1's acceptance criterion is: **baseline Recall@5 and MRR saved to
`eval/results/baseline_vector_*.json`, with unit tests for chunker and metrics
passing.** The chunker and metrics tests pass; everything below is still open.
Work in this exact order — each step is independently verifiable.

### Step 0 — Commit this session's work first

Stage and commit the Session 008 files before anything new, so the next change
set is reviewable. Verify the gates immediately before committing; record the
results in the Session 008 entry (§10 tells you where).

```sh
git add eval/__init__.py eval/golden_set.py eval/metrics.py \
        tests/test_golden_set.py tests/test_metrics.py \
        .dockerignore README.md DOCUMIND_HANDOFF_CONTEXT.md \
        ENGINEERING_LOG.md KNOWLEDGEBASE.md DOCUMIND_CONTEXT.md
# re-run the three gates (see §9), then:
git commit -m "v0.1.0 | Session 008: golden-set schema, retrieval metrics, verification fixes"
```

### Step 1 — CPU-only torch: DONE (Session 009, verified this turn)

`pyproject.toml` declares `torch>=2.2,<3.0` with the PyTorch CPU index;
`uv.lock` has zero CUDA/nvidia/triton entries; gates re-verified green;
embedding smoke confirmed 384 dims and was cleaned.

### Step 1b — LLM provider: DONE (Session 010, verified this turn)

The `ollama` provider routes through the OpenAI SDK at `https://ollama.com/v1`
(Ollama Cloud; key in `.env`, `LLM_MODEL=gpt-oss:20b`). Live `/api/ask/`
verified end-to-end: citations, similarity scores, QueryLog rows 1–2, warm
latency embed 18 ms / retrieve 16 ms / LLM ~3.5 s. Record `LLM_MODEL` with
every eval result — cloud models can be retired. A corrupted container venv
(misleading `transformers` circular import) was fixed by deleting the
`web_venv` volume and recreating `web`. **Start the remaining work at
Step 2 (full corpus ingestion).**

### Step 2 — Full corpus ingestion: DONE (Session 011, verified this turn)

Job 4: `done`, 640 docs / 6,487 chunks, 6,487/6,487 embeddings non-null,
~13 minutes inside the `web` container. All connections rechecked (health
200, Redis PONG). Live LLM validation over the full index: correct grounded
answers with citations for on-corpus questions (top similarity 0.86) and a
correct decline for an off-corpus question. **Start the remaining work at
Step 3 (`eval/build_golden_set.py`).**

### Repository state as of 2026-09-21 (post-push)

`origin/main` = **`35409c6`** (`v0.1.0 | Session 011: full corpus ingestion (6487
chunks), live LLM validation, connections rechecked`), working tree clean. Recent
history: `2271eeb` (Session 010: Ollama Cloud provider, live end-to-end RAG),
`4c45851` (Session 009: CPU-only torch), `04532af` (Session 008: golden-set
schema + metrics). Live stack verified after push: 6,487/6,487 chunks embedded,
health 200, Redis PONG, Ollama Cloud (`gpt-oss:20b`) answering with citations,
QueryLog audit rows written. Next worker starts at **Step 3 —
`eval/build_golden_set.py`**; the LLM provider it needs now exists.

### Step 3 — `eval/build_golden_set.py` (LLM-assisted drafting script)

Per `DOCUMIND_CONTEXT.md` §9: sample chunks, draft candidate questions with the
small/cheap `JUDGE_MODEL`, emit JSONL in the `GoldenQuestion` schema. The script
may propose; only a human disposes (Step 4). The script must:

- sample across document areas (models, queries, views, forms, auth, ORM…) so the
  set is not clustered on one topic;
- emit exactly the schema `golden_set.py` validates (so `validate_golden_set()`
  is the acceptance check);
- reserve 10 slots for **deliberately unanswerable** questions (plausible Django
  questions whose answers are absent from the pinned docs);
- pre-assign `split` 70 `dev` / 30 `heldout`, stratified across topics.

### Step 4 — Manual review (≥ 40 questions) and the golden file

Read at least 40 drafted questions against the cited sources. Fix wrong anchors,
rewrite ambiguous questions, delete questions answerable from general knowledge
("what is Python?"), and confirm the 10 unanswerable ones genuinely cannot be
answered from the corpus. Record the reviewed count — the README must quote it.
Then:

```sh
# place the reviewed file, then:
uv run --env-file .env python -c "
from pathlib import Path
from eval.golden_set import load_golden_set, summarise_golden_set, validate_golden_set
qs = load_golden_set(Path('eval/golden_set.jsonl'))
validate_golden_set(qs, corpus_root=Path('data/django-5.2/docs'))
print(summarise_golden_set(qs))"
```

Expect `total=100, answerable=90, unanswerable=10, dev=70, heldout=30`
(approximately — the split must contain both, exactly if the plan holds).
Commit `eval/golden_set.jsonl`.

### Step 5 — `eval/run_eval.py` + baseline `vector` results

`run_eval.py` runs one retrieval mode over one split, builds `RetrievalOutcome`
objects from the database (using the same `retrieve()` the API uses, so the
number describes the deployed path), computes `compute_retrieval_metrics()`, and
writes `eval/results/<mode>_<split>_<date>.json` including:

- mode, split, corpus commit (`c14b756185c88f7f2eb745ff061f3c221fea9de7`),
  chunking parameters (400/50), embedding model, k values;
- `RetrievalMetrics.as_dict()` payload;
- per-question first-relevant-rank (enables honest error analysis later).

Run order: **tune nothing on `heldout`.** Run on `dev` first (sanity), then once
on `heldout` for the locked baseline. Commit the JSON files — they are the
evidence behind every future resume claim.

### Step 6 — Close Phase 1

- Add the baseline row to the results table (`DOCUMIND_CONTEXT.md` §9 layout;
  the README table follows only when all three modes exist).
- Update `DOCUMIND_CONTEXT.md` §15 (Results Log) with the real run file and
  numbers, §17 checkboxes, and the session log.
- Add the retrieval-smoke subset + thresholds to `ci.yml` (see §6 Gap D.2).
- Only then start Phase 2 (`keyword.py` + RRF).

**What NOT to do in this task:** touch `hybrid`/`rerank`/RAGAS/JWT/Celery, change
chunking parameters (that would invalidate heldout comparability — decide
deliberately or not at all), or tune prompts against `heldout`.

### Step 7 — Streamlit demo UI (planned; scheduling decided below)

A simple Streamlit landing page was requested by the owner (2026-09-21) so the
API can be tested directly from a browser instead of raw `curl`. It is
**planned, not yet built**, and deliberately scheduled *after* the baseline
eval so it never delays the phase's acceptance criteria.

**Scope (keep it small — a test surface, not a product):**

- New top-level `ui/app.py` (Streamlit is already a resume skill; no new heavy
  framework). Run with `uv run --env-file .env streamlit run ui/app.py`; the
  app talks to the live API at `API_BASE_URL` (env, default
  `http://localhost:8000`), never to the database directly.
- One text box + mode selector (`vector` only until Phase 2/3 modes exist,
  then auto-list available modes) + "Ask" button.
- Renders: answer, refused flag, citations (title / heading path / URL /
  score), and the `latency_ms` breakdown — mirroring the `/api/ask/` response
  shape exactly so the UI stays a thin client.
- A health banner driven by `GET /api/health/` (show DB/Redis state).
- No auth in v1: for JWT-enabled Phase 4, add a sidebar token field that
  attaches `Authorization: Bearer …` to requests.
- Tests: the UI calls the API over HTTP, so cover it with a thin `requests`
  wrapper module (`ui/client.py`) unit-tested against a mocked transport;
  Streamlit rendering itself stays untested (thin layer).

**Sequencing:** implement as `Phase 4` work (with JWT/throttling) or
immediately after Step 5 baseline results if the owner wants browser testing
earlier — it is a one-session task, roughly: `ui/client.py` + tests →
`ui/app.py` → README "Demo UI" section → optional `streamlit` service in
`docker-compose.yml`. Do not let it displace `run_eval.py` or the manual
golden-set review if time conflicts.

---

## 8. Verified command reference

All commands run from the repository root. The `uv run --env-file .env` prefix
is required whenever Django settings or tools need secrets/DB config.

| Purpose | Command | Verified |
| --- | --- | --- |
| Lint | `uv run --env-file .env ruff check .` | ✅ PASS |
| Types | `uv run --env-file .env mypy .` | ✅ PASS, 50 files |
| Tests (host) | `$env:POSTGRES_HOST='localhost'; uv run --env-file .env pytest` (PowerShell) or `POSTGRES_HOST=localhost uv run --env-file .env pytest` (bash) | ✅ 61 passed (Session 010) |
| Tests (container) | `docker compose run --rm -T --no-deps web uv run pytest -q` | ❌ stalled — see §6 Defect B; use the host form until fixed |
| Migration drift check | `uv run --env-file .env python manage.py makemigrations --check --dry-run` (same `POSTGRES_HOST` override on host) | ✅ "No changes detected" |
| Fetch corpus | `sh scripts/fetch_docs.sh` | ✅ idempotent, verified commit |
| Ingest (smoke) | `uv run --env-file .env python manage.py ingest_docs --limit 3` | ✅ historically; re-verify after any lock change |
| Ingest (full) | `uv run --env-file .env python manage.py ingest_docs` (run detached in `web`: `docker compose exec -d -T web sh -c "uv run python manage.py ingest_docs"`) | ✅ DONE — 640 docs / 6,487 chunks, 100% embedded, job `done` in ~13 min (Session 011) |
| Validate a golden file | `python -c "from pathlib import Path; from eval.golden_set import …"` (see §7 Step 4) | ✅ logic covered by tests, no golden file yet |
| Live DB row counts | `docker compose exec -T postgres psql -U documind -d documind -c "SELECT …"` | ✅ see §3.3 |

Health endpoint: `GET http://localhost:8000/api/health/` returns the version plus
`database`/`redis` states (200 healthy, 503 otherwise), after `docker compose up`.

---

## 9. Documentation maintenance contract

Four files must stay consistent after **every** completed task. Update all four
in the same commit as the code:

1. **`ENGINEERING_LOG.md`** — append a `# Session NNN` entry:
   Objective → Why this task exists → Concepts → Files Created → File
   Explanations → Architecture → Tests (with real observed output, counts, and
   timings where relevant) → Lessons → Next Step. Record numbers as observed,
   never as hoped.
2. **`KNOWLEDGEBASE.md`** — append a dated `## YYYY-MM-DD — Phase X, Task: …`
   section explaining what changed, why, and what later work may assume.
   Never rewrite earlier entries; add a later correction section instead.
3. **`DOCUMIND_CONTEXT.md` §17** — check the finished boxes, prepend the session
   log line (`YYYY-MM-DD: what was done | next step | blockers`), update
   §15 Results Log from real `eval/results/` files only, and add a §18 row if a
   locked decision changed (with date and rationale).
4. **`DOCUMIND_HANDOFF_CONTEXT.md`** (this file) — move the completed work from
   §6/§7 into §4, refresh §3 with the newly observed gate output and row counts,
   and re-point §7 at the next task.

`README.md` changes only when public functionality changes, results exist, or
setup/workflow instructions change. `CODEX_CONTEXT.md` is historical — read it,
do not edit its progress claims.

---

## 10. Interview talking points (why each locked decision exists)

These are the explanations the owner must be able to give; they constrain what
later work may change.

- **pgvector over a separate vector DB:** one datastore, transactional consistency
  between chunks and vectors, no extra service to operate, and it exercises the
  SQL/PostgreSQL skills the target roles require.
- **Hand-written RRF (`score(d) = Σ 1 / (60 + rank_i(d))`):** dense and keyword
  scores live on incomparable scales; RRF fuses *ranks*, so no score
  normalisation is needed.
- **Postgres full-text, never "BM25":** `ts_rank` is a lexical rank, not BM25.
  Saying "BM25" on a resume would be a false claim a knowledgeable interviewer
  can expose in one question.
- **Gold labels as (path, anchor), not chunk IDs:** re-chunking experiments must
  not invalidate the evaluation set; provenance survives parameter changes.
- **Dev/heldout split:** tune on `dev`, report `heldout` once. Tuning on the
  reported split is overfitting with extra steps.
- **L2-normalised embeddings + `vector_cosine_ops` HNSW:** cosine similarity and
  inner product coincide, and `CosineDistance` ordering comes straight from the
  index.
- **Injectable embedder + `LLMClient` protocol:** tests never download a model or
  call a paid API; providers swap by settings alone.
- **Citation validator (Phase 3):** cited chunk IDs are parsed and checked against
  retrieved IDs, so a fluent but fabricated citation is caught in code, not by eye.

---

*End of handoff context. The next model should start at §7 Step 0 after reading
`DOCUMIND_CONTEXT.md` in full.*