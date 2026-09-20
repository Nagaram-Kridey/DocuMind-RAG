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
