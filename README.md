# DocuMind RAG

DocuMind is a production-style Django REST Framework backend for evaluating dense, hybrid, and reranked Retrieval-Augmented Generation systems over the Django 5.2 documentation, pinned to Django tag `5.2.9` (`c14b756185c88f7f2eb745ff061f3c221fea9de7`).

## Local setup

1. Copy `.env.example` to `.env` and set secure local values.
2. Run `docker compose up --build`.
3. Open `http://localhost:8000/api/health/`.

The corpus will use Django documentation, which is BSD-licensed. Retrieval and evaluation features are introduced in later phases.

To fetch the exact corpus revision on a Unix-like shell, run `sh scripts/fetch_docs.sh`. The raw source is deliberately ignored by Git; the script and pinned commit make it reproducible.
LLM Based RAG Project with 100 Golden Questions Template usage
