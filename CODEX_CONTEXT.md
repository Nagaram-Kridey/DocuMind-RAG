# CODEX CONTEXT — DocuMind RAG

**Project:** DocuMind-RAG
**Repository:** https://github.com/Nagaram-Kridey/DocuMind-RAG
**Owner:** Nagaram Kridey

> This file is the initialization context for VS Code + Codex. Treat it as the working prompt before generating or modifying any code.

---

# 1. Project Mission

DocuMind is a **production-grade Retrieval-Augmented Generation (RAG) backend** built with Django REST Framework.

This is **not** a chatbot project.

The objective is to demonstrate real-world backend engineering by implementing and evaluating three retrieval systems:

1. Dense Vector Retrieval (Baseline)
2. Hybrid Retrieval (Vector + PostgreSQL Full-Text + RRF)
3. Hybrid Retrieval + Cross-Encoder Reranking

The strongest deliverable is the **evaluation pipeline** and measurable retrieval improvements, not the UI.

---

# 2. Documents Hierarchy (IMPORTANT)

There are three documentation files with different responsibilities.

## README.md

Public GitHub documentation.

Contains:

* Project overview
* Features
* Architecture diagram
* Installation
* API usage
* Results table
* Tech stack

Keep concise.

---

## DOCUMIND_CONTEXT.md

The immutable project specification.

Contains:

* Architecture
* Tech stack
* Data model
* Phase roadmap
* Decisions
* Evaluation methodology

Never modify unless project requirements change.

---

## ENGINEERING_LOG.md

Mandatory development journal.

**Every completed task must update this file.**

Each session records:

* Objective
* Why it exists
* Concepts
* Files created
* File-by-file explanation
* Architecture
* Tests
* Lessons learned
* Next task

This is the complete engineering knowledge base.

---

# 3. Locked Technical Decisions

Do NOT change these unless explicitly instructed.

| Layer       | Choice                   |
| ----------- | ------------------------ |
| Backend     | Django 5 + DRF           |
| Language    | Python 3.11              |
| Database    | PostgreSQL 16            |
| Vector      | pgvector                 |
| Async       | Celery + Redis           |
| Embeddings  | BAAI/bge-small-en-v1.5   |
| Reranker    | BAAI Cross Encoder       |
| Retrieval   | Handwritten RRF          |
| Search      | PostgreSQL Full-Text     |
| Testing     | pytest                   |
| Quality     | Ruff + MyPy              |
| CI          | GitHub Actions           |
| Docs Corpus | Django 5.2 Documentation |

Avoid LangChain for retrieval logic.

Implement chunking, fusion, retrieval, and evaluation manually.

---

# 4. Development Principles

1. Build phase by phase.
2. Never fabricate metrics.
3. Every module must include tests.
4. Prefer explainable code over abstraction.
5. Keep Ruff and MyPy clean.
6. Update ENGINEERING_LOG after every task.
7. README only changes when public functionality changes.

---

# 5. Current Progress

Current Phase:

**Phase 0 — Setup**

Task 0.1 has begun.

Completed:

* Project architecture finalized
* Documentation strategy finalized
* Repository selected
* Context established

Not yet implemented:

* pyproject.toml
* Docker
* Django
* PostgreSQL
* Health endpoint
* CI

---

# 6. Immediate Task — 0.1 Repository Foundation

Build the foundation only.

Create:

## Root

* pyproject.toml
* Dockerfile
* docker-compose.yml
* .env.example
* .gitignore
* .pre-commit-config.yaml
* README.md
* ENGINEERING_LOG.md

## Django

Create Django project:

config/

Split settings:

* base.py
* dev.py
* prod.py

Apps directory:

* accounts
* documents
* retrieval
* qa

---

# 7. Docker Services

docker-compose must contain:

* web
* postgres (pgvector/pg16)
* redis

Health checks required.

Environment variables loaded from `.env`.

---

# 8. Health Endpoint

Implement:

GET `/api/health/`

Return JSON similar to:

```json
{
  "status":"healthy",
  "database":"connected",
  "redis":"connected",
  "version":"0.1.0"
}
```

No retrieval logic yet.

---

# 9. Engineering Log Format

Every session follows:

```md
# Session 001

Phase:
Task:
Status:

## Objective

## Why this task exists

## Concepts

## Files Created

## File Explanations

## Architecture

## Tests

## Lessons

## Next Step
```

Append sessions chronologically.

---

# 10. Coding Standards

* Type hints everywhere.
* Google-style docstrings.
* Small focused modules.
* No magic numbers.
* Environment variables only.
* Use dataclasses where appropriate.
* Keep functions interview-explainable.

---

# 11. Acceptance Criteria for Task 0.1

* Docker Compose starts successfully.
* Django boots.
* PostgreSQL connects.
* Redis connects.
* `/api/health/` returns healthy.
* Ruff passes.
* MyPy passes.
* One smoke pytest passes.
* ENGINEERING_LOG updated.

Do not begin Phase 1 until all acceptance criteria are satisfied.

---

## End of Context

Treat this file together with `DOCUMIND_CONTEXT.md`. If conflicts occur, `DOCUMIND_CONTEXT.md` has higher priority, while `ENGINEERING_LOG.md` records implementation history.
