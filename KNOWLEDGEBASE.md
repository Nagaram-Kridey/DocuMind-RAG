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

## 2026-09-20 — Phase 0, Task 0.1: Repository Foundation

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

## 2026-09-20 — Phase 1, Task: Fetch and pin the Django documentation corpus

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

## 2026-09-20 — Phase 1, Task: RST parser and heading-aware chunker

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
