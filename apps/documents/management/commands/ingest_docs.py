"""Management command that ingests the pinned documentation corpus."""

from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandParser

from apps.documents.ingestion import IngestionResult, discover_document_paths, ingest_corpus
from config.corpus import DJANGO_DOCS_RELATIVE_PATH


class Command(BaseCommand):
    """Parse, chunk, embed, and persist the pinned Django documentation."""

    help = "Ingest the pinned Django documentation corpus into PostgreSQL."

    def add_arguments(self, parser: CommandParser) -> None:
        """Expose optional corpus, version, and subset controls."""
        parser.add_argument(
            "--corpus-root",
            type=Path,
            default=Path(settings.BASE_DIR) / DJANGO_DOCS_RELATIVE_PATH,
            help="Directory containing the pinned RST documentation.",
        )
        parser.add_argument(
            "--docs-version",
            default=settings.DOCS_VERSION,
            help="Documentation version recorded on ingested documents.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Ingest at most this many files (0 means all).",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        """Run ingestion and report the resulting counts."""
        corpus_root: Path = options["corpus_root"]
        doc_version: str = options["docs_version"]
        limit: int = options["limit"]

        if not corpus_root.is_dir():
            self.stderr.write(f"Corpus root does not exist: {corpus_root}")
            raise SystemExit(1)

        paths = discover_document_paths(corpus_root)
        if limit > 0:
            paths = paths[:limit]

        self.stdout.write(f"Ingesting {len(paths)} file(s) from {corpus_root} ...")
        result = ingest_corpus(corpus_root, doc_version, paths=paths)
        self._report(result)
        if result.errors:
            raise SystemExit(1)

    def _report(self, result: IngestionResult) -> None:
        """Print a human-readable ingestion summary."""
        self.stdout.write(
            self.style.SUCCESS(
                "Ingestion complete: "
                f"created={result.documents_created} "
                f"updated={result.documents_updated} "
                f"skipped={result.documents_skipped} "
                f"chunks={result.chunks_created} "
                f"embedded={result.chunks_embedded} "
                f"reused={result.chunks_reused_embeddings}"
            )
        )
        for error in result.errors:
            self.stderr.write(self.style.ERROR(error))