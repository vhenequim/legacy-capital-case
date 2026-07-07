"""Case A — Capex das hyperscalers vs demanda/receita da NVIDIA.

Resolve o case usando exclusivamente a plataforma genérica: perguntas de
retrieval + geração grounded com citações. Nenhuma lógica específica de
empresa — apenas a lista de perguntas.
"""

import json
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel

from legacy_retrieval.config import get_settings
from legacy_retrieval.indexing.indexer import DocumentIndexer
from legacy_retrieval.pipeline import RetrievalPipeline

app = typer.Typer(help="Run Case A via the generic retrieval platform")
console = Console()

QUESTIONS = [
    "How much did Microsoft report in additions to property and equipment in fiscal year 2025?",
    "How much did Amazon report in purchases of property and equipment for the full year 2025?",
    "What capital expenditures did Meta report for the full year 2025?",
    "What capital expenditures did Alphabet (Google) report for 2025?",
    "What capital expenditures did Oracle report in its most recent fiscal year?",
    "What was NVIDIA's Data Center revenue in its most recent quarter and how fast is it growing?",
    "What did NVIDIA say about demand for its Blackwell products and AI infrastructure?",
    "Considering the capital expenditures reported by Microsoft, Amazon, Meta and Google for 2025, "
    "what is the approximate aggregate capex of the hyperscalers, and how does NVIDIA describe the "
    "demand environment driving that investment?",
]


def _load_pipeline() -> RetrievalPipeline:
    settings = get_settings()
    indexer = DocumentIndexer(settings)
    state_dir = settings.processed_data_dir / "index_state"
    if not state_dir.exists():
        console.print("[red]Índice não encontrado. Rode: python scripts/index.py --fresh[/red]")
        raise typer.Exit(1)
    indexer.load_state(state_dir)
    return RetrievalPipeline(indexer, settings)


@app.command()
def main(
    output: Path = typer.Option(Path("data/processed/case_a/report.json"), "--output"),
) -> None:
    pipeline = _load_pipeline()
    results = []

    for question in QUESTIONS:
        response = pipeline.query(question)
        results.append(
            {
                "question": question,
                "answer": response.answer,
                "refused": response.refused,
                "citations": [
                    {
                        "document_id": c.document_id,
                        "company": c.company,
                        "doc_type": c.doc_type,
                        "published_at": c.published_at.isoformat() if c.published_at else None,
                        "url": c.url,
                        "excerpt": c.excerpt[:200],
                    }
                    for c in response.citations[:5]
                ],
            }
        )
        cited = ", ".join(sorted({c.company for c in response.citations[:5]})) or "—"
        console.print(Panel(response.answer, title=question[:110], subtitle=f"fontes: {cited}"))

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    console.print(f"\n[green]Relatório salvo em {output}[/green]")


if __name__ == "__main__":
    app()
