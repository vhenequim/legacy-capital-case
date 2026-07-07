import typer
from rich.console import Console
from rich.markdown import Markdown

from legacy_retrieval.config import get_settings
from legacy_retrieval.indexing.indexer import DocumentIndexer
from legacy_retrieval.pipeline import RetrievalPipeline

console = Console()


def main(
    question: str = typer.Argument(..., help="Question to ask"),
    top_k: int = typer.Option(10, "--top-k", "-k", help="Number of results"),
) -> None:
    settings = get_settings()
    indexer = DocumentIndexer(settings)
    state_dir = settings.processed_data_dir / "index_state"
    if state_dir.exists():
        indexer.load_state(state_dir)

    pipeline = RetrievalPipeline(indexer, settings)
    response = pipeline.query(question, top_k=top_k)

    if response.refused:
        console.print("[yellow]Não encontrei essa informação na base.[/yellow]")
    else:
        console.print(Markdown(response.answer))

    if response.citations:
        console.print("\n[bold]Citations:[/bold]")
        for i, c in enumerate(response.citations, 1):
            console.print(
                f"  {i}. [{c.document_id}] {c.company} ({c.doc_type}) "
                f"- {c.excerpt[:100]}..."
            )


if __name__ == "__main__":
    typer.run(main)
