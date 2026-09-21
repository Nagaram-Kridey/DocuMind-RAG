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

## Running the quality gates

`ruff`, `mypy`, and `pytest` all need the environment variables in `.env`,
and `mypy`/`pytest` additionally need to reach PostgreSQL. There are two
supported ways to run them.

**Inside Docker (recommended: the `postgres` hostname resolves there).**

```sh
docker compose run --rm --no-deps web uv run ruff check .
docker compose run --rm --no-deps web uv run mypy .
docker compose run --rm --no-deps web uv run pytest
```

**On the host.** `uv run --env-file .env` loads `.env` without exporting it
first, but `.env` deliberately points at the Docker service name `postgres`.
A host run must override it with `localhost`, because that name only resolves
inside the Compose network:

```sh
# Linux / macOS
POSTGRES_HOST=localhost uv run --env-file .env pytest

# PowerShell
$env:POSTGRES_HOST = "localhost"; uv run --env-file .env pytest
```

The same override applies to `manage.py` commands run on the host, including
`makemigrations --check --dry-run` and `ingest_docs`.

## Evaluation

The evaluation harness lives in `eval/`. It is plain Python so every metric is
explainable:

- `eval/golden_set.py` — golden-set schema, JSONL round-trip, and dataset
  validation (duplicate IDs, dev/heldout coverage, answerable/unanswerable
  shape, and gold paths that must exist in the pinned corpus).
- `eval/metrics.py` — hand-written Recall@k, hit@k, and MRR@k. Ground truth is
  `(source_path, anchor)` rather than chunk IDs, so labels survive re-chunking.

Questions are stored as JSONL, one object per line:

```json
{"id": "q001", "question": "...", "gold_sources": [{"path": "topics/db/models.txt", "anchor": "field-options"}], "answerable": true, "split": "dev"}
```

Planned next: `eval/build_golden_set.py` (LLM-drafted questions for manual
review), `eval/run_eval.py` (runs one mode over a split and writes
`eval/results/*.json`), and `eval/ragas_eval.py`. **No results table is
published here until real numbers exist**; see `DOCUMIND_CONTEXT.md` Section 15.

## Deployment notes

- The image is built from `pyproject.toml` + `uv.lock` with `uv sync --frozen`,
  and production traffic is served by gunicorn (`Dockerfile` `CMD`).
- `docker-compose.yml` overrides that with Django's development server and is
  intended for local development only. Use
  `DJANGO_SETTINGS_MODULE=config.settings.prod` with a real WSGI/ASGI server and
  a reverse proxy for deployment.
- `.dockerignore` excludes the pinned corpus (`data/`, ~640 RST files),
  the host `.venv`, `.git`, and `.env` from the build context. Compose
  bind-mounts the repository for ingestion, so the corpus never needs to be
  baked into the image.
- Secrets come only from environment variables; `.env` is never committed.

The corpus is Django documentation, which is BSD-licensed. Attribution belongs
in this README when the corpus is described publicly.
