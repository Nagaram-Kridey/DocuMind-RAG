# DocuMind RAG

DocuMind is a production-style Django REST Framework backend for evaluating dense, hybrid, and reranked Retrieval-Augmented Generation systems over the Django 5.2 documentation, pinned to Django tag `5.2.9` (`c14b756185c88f7f2eb745ff061f3c221fea9de7`).

## Local setup

1. Copy `.env.example` to `.env` and set secure local values.
2. Run `docker compose up --build`.
3. Open `http://localhost:8000/api/health/`.

The corpus will use Django documentation, which is BSD-licensed. Retrieval and evaluation features are introduced in later phases.

To fetch the exact corpus revision on a Unix-like shell, run `sh scripts/fetch_docs.sh`. The raw source is deliberately ignored by Git; the script and pinned commit make it reproducible.

## Ingesting the corpus

After the corpus is fetched and PostgreSQL is running, index it with:

```sh
uv run python manage.py ingest_docs
```

The command parses each RST file, chunks it by heading, embeds every chunk with
`BAAI/bge-small-en-v1.5`, and stores the result in PostgreSQL. It is idempotent:
unchanged documents are skipped, and unchanged chunks keep their existing
vectors when a document is edited. Useful options:

- `--limit N` ingests only the first `N` files (handy for a quick smoke test).
- `--corpus-root PATH` points at a different pinned checkout.
- `--docs-version VERSION` overrides the recorded documentation version.

## Asking a question

`POST /api/ask/` retrieves the most relevant chunks and answers with citations:

```sh
curl -X POST http://localhost:8000/api/ask/ \
  -H "Content-Type: application/json" \
  -d '{"question": "How do I define a model field?", "mode": "vector", "top_k": 5}'
```

Response:

```json
{
  "answer": "...",
  "refused": false,
  "citations": [
    {"chunk_id": 12, "title": "Models", "heading_path": "Models > Fields", "url": "...", "score": 0.83}
  ],
  "mode": "vector",
  "latency_ms": {"embed": 12, "retrieve": 35, "rerank": 0, "llm": 900, "total": 947}
}
```

Generation is provider-agnostic: set `LLM_PROVIDER` (`anthropic` or `openai`),
`LLM_MODEL`, and `LLM_API_KEY` in `.env`. Only `mode=vector` (the dense baseline)
is implemented so far; `hybrid` and `hybrid_rerank` are added in later phases.
LLM Based RAG Project with 100 Golden Questions Template usage
