import json
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from legacy_retrieval.config import get_settings
from legacy_retrieval.eval.harness import EvalHarness, load_questions
from legacy_retrieval.indexing.indexer import DocumentIndexer
from legacy_retrieval.models import Document
from legacy_retrieval.pipeline import RetrievalPipeline

app = typer.Typer(help="Run retrieval evaluation harness")
console = Console()


def _load_indexed_documents(processed_dir: Path) -> list[Document]:
    docs: list[Document] = []
    docs_dir = processed_dir / "documents"
    if not docs_dir.exists():
        return docs
    for path in docs_dir.glob("*.json"):
        docs.append(Document.model_validate(json.loads(path.read_text(encoding="utf-8"))))
    return docs


@app.command()
def main(
    questions: Path = typer.Option(
        Path("eval/questions.jsonl"),
        "--questions",
        "-q",
        help="Path to gold questions JSONL",
    ),
    k: int = typer.Option(10, "--k", help="Top-k for retrieval metrics"),
    processed_dir: Path = typer.Option(
        None,
        "--processed-dir",
        help="Directory with processed documents",
    ),
    output: Path = typer.Option(None, "--output", "-o", help="Write JSON report to file"),
) -> None:
    settings = get_settings()
    proc = processed_dir or settings.processed_data_dir

    indexer = DocumentIndexer(settings)
    state_dir = proc / "index_state"
    if state_dir.exists():
        indexer.load_state(state_dir)

    docs = _load_indexed_documents(proc)
    if docs and not indexer.chunks:
        console.print(f"Indexing {len(docs)} documents...")
        indexer.index_documents(docs)

    pipeline = RetrievalPipeline(indexer, settings)
    harness = EvalHarness(pipeline)

    if not questions.exists():
        console.print(f"[red]Questions file not found: {questions}[/red]")
        raise typer.Exit(1)

    qs = load_questions(questions)
    console.print(f"Running eval on {len(qs)} questions (k={k})...")

    report = harness.run(qs, k=k)
    summary = report.to_dict()

    table = Table(title="Eval Results")
    table.add_column("Metric")
    table.add_column("Value")
    table.add_row("Mean Recall@k", f"{summary['mean_recall_at_k']:.4f}")
    table.add_row("Mean Precision@k", f"{summary['mean_precision_at_k']:.4f}")
    table.add_row("Mean MRR", f"{summary['mean_mrr']:.4f}")
    table.add_row("Answer Rate", f"{summary['answer_rate']:.4f}")
    table.add_row("Refusal Rate", f"{summary['refusal_rate']:.4f}")
    console.print(table)

    if output:
        output.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        console.print(f"Report written to {output}")


if __name__ == "__main__":
    app()
