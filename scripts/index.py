import json
import shutil
from pathlib import Path

import typer
from rich.console import Console

from legacy_retrieval.config import get_settings
from legacy_retrieval.indexing.indexer import DocumentIndexer
from legacy_retrieval.models import Document

app = typer.Typer(help="Index processed documents")
console = Console()


def _reset_qdrant_collection(settings) -> None:
    try:
        from qdrant_client import QdrantClient

        client = QdrantClient(url=settings.qdrant_url, check_compatibility=False)
        if settings.qdrant_collection in [
            c.name for c in client.get_collections().collections
        ]:
            client.delete_collection(settings.qdrant_collection)
            console.print(f"[yellow]Cleared Qdrant collection: {settings.qdrant_collection}[/yellow]")
    except Exception as exc:
        console.print(f"[yellow]Qdrant reset skipped: {exc}[/yellow]")


@app.command()
def main(
    processed_dir: Path = typer.Option(
        None, "--processed-dir", help="Processed documents directory"
    ),
    fresh: bool = typer.Option(False, "--fresh", help="Reset Qdrant collection and BM25 state"),
) -> None:
    settings = get_settings()
    proc = processed_dir or settings.processed_data_dir
    docs_dir = proc / "documents"
    state_dir = proc / "index_state"

    if not docs_dir.exists():
        console.print(f"[red]No documents found at {docs_dir}[/red]")
        raise typer.Exit(1)

    if fresh:
        if state_dir.exists():
            shutil.rmtree(state_dir)
        _reset_qdrant_collection(settings)

    docs: list[Document] = []
    for path in docs_dir.glob("*.json"):
        docs.append(Document.model_validate(json.loads(path.read_text(encoding="utf-8"))))

    console.print(f"Indexing {len(docs)} documents...")
    indexer = DocumentIndexer(settings)
    chunks = indexer.index_documents(docs)

    indexer.save_state(state_dir)

    console.print(f"[green]Indexed {len(chunks)} chunks. State saved to {state_dir}[/green]")

if __name__ == "__main__":
    app()
