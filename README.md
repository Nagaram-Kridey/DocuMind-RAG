# DocuMind RAG

DocuMind is a production-style Django REST Framework backend for evaluating dense, hybrid, and reranked Retrieval-Augmented Generation systems over the Django 5.2 documentation.

## Local setup

1. Copy `.env.example` to `.env` and set secure local values.
2. Run `docker compose up --build`.
3. Open `http://localhost:8000/api/health/`.

The corpus will use Django documentation, which is BSD-licensed. Retrieval and evaluation features are introduced in later phases.
LLM Based RAG Project with 100 Golden Questions Template usage
