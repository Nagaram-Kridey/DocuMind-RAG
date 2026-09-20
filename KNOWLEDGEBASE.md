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
