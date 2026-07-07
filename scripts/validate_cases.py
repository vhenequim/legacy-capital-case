"""Validate representative questions for Cases A, B, and C."""

import json

import pandas as pd
import typer
from rich.console import Console
from rich.table import Table

from legacy_retrieval.config import get_settings
from legacy_retrieval.indexing.indexer import DocumentIndexer
from legacy_retrieval.models import Document
from legacy_retrieval.pipeline import RetrievalPipeline
from legacy_retrieval.structured.backtest import run_rpo_backtest, summarize_backtest
from legacy_retrieval.structured.market_share import get_market_share_report
from legacy_retrieval.structured.metrics import extract_metrics

app = typer.Typer()
console = Console()

CASE_QUESTIONS = {
    "A": [
        "What is the aggregate capex guidance for hyperscalers in 2025?",
        "What did NVIDIA comment about demand from hyperscalers?",
    ],
    "B": [
        "Did Bradesco fulfill the promise to reduce provisions made in Q1?",
        "How did Itaú credit outlook change between Q2 and Q4 2024?",
        "What is Nubank market share according to BACEN data?",
    ],
    "C": [
        "What was Salesforce RPO in Q3 FY2024?",
        "What is the RPO growth acceleration for ServiceNow?",
    ],
}


def _load_pipeline() -> RetrievalPipeline:
    settings = get_settings()
    indexer = DocumentIndexer(settings)
    state_dir = settings.processed_data_dir / "index_state"
    if state_dir.exists():
        indexer.load_state(state_dir)
    else:
        docs_dir = settings.processed_data_dir / "documents"
        docs = [
            Document.model_validate(json.loads(p.read_text(encoding="utf-8")))
            for p in docs_dir.glob("*.json")
        ]
        indexer.index_documents(docs)
    return RetrievalPipeline(indexer, settings)


@app.command()
def main() -> None:
    pipeline = _load_pipeline()
    table = Table(title="Case Validation")
    table.add_column("Case")
    table.add_column("Question")
    table.add_column("Status")
    table.add_column("Refused")

    for case, questions in CASE_QUESTIONS.items():
        for q in questions:
            response = pipeline.query(q)
            status = "OK" if not response.refused else "REFUSED"
            table.add_row(case, q[:60] + "...", status, str(response.refused))

    console.print(table)

    # Structured validations
    console.print("\n[bold]Case B - Market Share (Nubank):[/bold]")
    ms = get_market_share_report("NU PAGAMENTOS")
    console.print(json.dumps(ms, indent=2))

    console.print("\n[bold]Case C - RPO Extraction (Salesforce):[/bold]")
    settings = get_settings()
    crm_doc = settings.processed_data_dir / "documents" / "sec_0001108524_demo_rpo.json"
    if crm_doc.exists():
        doc = Document.model_validate(json.loads(crm_doc.read_text(encoding="utf-8")))
        metrics = extract_metrics(doc.content, "CRM", "rpo")
        for m in metrics:
            console.print(f"  {m.metric}: {m.value:,.0f} ({m.period})")

    console.print("\n[bold]Case C - Backtest Summary:[/bold]")
    rpo_df = pd.DataFrame(
        [
            {
                "company": "NOW",
                "period": "Q2 FY2024",
                "value": 18.2e9,
                "earnings_date": "2024-07-24",
                "timing": "post_market",
            },
            {
                "company": "NOW",
                "period": "Q3 FY2024",
                "value": 19.1e9,
                "earnings_date": "2024-10-23",
                "timing": "post_market",
            },
        ]
    )
    returns_df = pd.DataFrame(
        [
            {"company": "NOW", "date": "2024-07-25", "return": 0.032},
            {"company": "NOW", "date": "2024-10-24", "return": 0.018},
        ]
    )
    bt = run_rpo_backtest(rpo_df, returns_df)
    summary = summarize_backtest(bt)
    console.print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    app()
