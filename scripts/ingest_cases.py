"""Ingestao unificada dos Cases A, B e C a partir das fontes oficiais.

Uso:
    python scripts/ingest_cases.py --case A
    python scripts/ingest_cases.py --case all --since 2024-01-01
"""

from datetime import datetime
from pathlib import Path

import typer
from rich.console import Console

from legacy_retrieval.cases import CASES, CaseConfig
from legacy_retrieval.config import get_settings
from legacy_retrieval.ingestion.bacen import BacenFetcher
from legacy_retrieval.ingestion.cvm import CvmFetcher
from legacy_retrieval.ingestion.news import NewsFetcher
from legacy_retrieval.ingestion.sec_edgar import SecEdgarFetcher
from legacy_retrieval.models import Document

app = typer.Typer(help="Ingest cases A/B/C from official sources")
console = Console()


def _save_documents(docs: list[Document], dirs: list[Path]) -> int:
    for out_dir in dirs:
        out_dir.mkdir(parents=True, exist_ok=True)
        for doc in docs:
            (out_dir / f"{doc.id}.json").write_text(
                doc.model_dump_json(indent=2), encoding="utf-8"
            )
    return len(docs)


def _ingest_sec(case: CaseConfig, since: datetime, max_filings: int) -> int:
    settings = get_settings()
    proc_out = settings.processed_data_dir / "documents"
    total = 0
    with SecEdgarFetcher(settings) as sec:
        for ticker in case.sec_tickers:
            try:
                docs = sec.fetch(
                    company=ticker,
                    since=since,
                    filing_types=case.sec_filing_types,
                    max_filings=max_filings,
                )
                raw_out = settings.raw_data_dir / "sec" / ticker.lower()
                total += _save_documents(docs, [raw_out, proc_out])
                console.print(f"  SEC {ticker}: {len(docs)} filings")
            except Exception as exc:
                console.print(f"  [red]SEC {ticker}: failed — {exc}[/red]")
    return total


def _ingest_news(case: CaseConfig, since: datetime) -> int:
    settings = get_settings()
    proc_out = settings.processed_data_dir / "documents"
    total = 0
    news = NewsFetcher(settings)
    for ticker in case.news_tickers:
        try:
            docs = news.fetch(company=ticker, since=since, max_items=10)
            raw_out = settings.raw_data_dir / "news" / ticker.lower()
            total += _save_documents(docs, [raw_out, proc_out])
            console.print(f"  News {ticker}: {len(docs)} articles")
        except Exception as exc:
            console.print(f"  [red]News {ticker}: failed — {exc}[/red]")
    return total


def _ingest_cvm(case: CaseConfig, since: datetime, max_docs: int) -> int:
    settings = get_settings()
    proc_out = settings.processed_data_dir / "documents"
    total = 0
    with CvmFetcher(settings) as cvm:
        for company in case.cvm_companies:
            try:
                docs = cvm.fetch(company=company, since=since, max_docs=max_docs)
                raw_out = settings.raw_data_dir / "cvm" / company.lower()
                total += _save_documents(docs, [raw_out, proc_out])
                console.print(f"  CVM {company}: {len(docs)} documentos")
            except Exception as exc:
                console.print(f"  [red]CVM {company}: failed — {exc}[/red]")
    return total


def _ingest_bacen(case: CaseConfig) -> int:
    settings = get_settings()
    proc_out = settings.processed_data_dir / "documents"
    total = 0
    fetcher = BacenFetcher(settings)
    for dataset in case.bacen_datasets:
        try:
            docs = fetcher.fetch(dataset=dataset)
            total += _save_documents(docs, [proc_out])
            console.print(f"  BACEN {dataset}: {len(docs)} documento(s)")
        except Exception as exc:
            console.print(f"  [red]BACEN {dataset}: failed — {exc}[/red]")
    return total


@app.command()
def main(
    case: str = typer.Option("all", "--case", help="A, B, C ou all"),
    since: str = typer.Option("2024-01-01", "--since", help="Data inicial YYYY-MM-DD"),
    max_filings: int = typer.Option(15, "--max", help="Max filings SEC por empresa"),
    skip_news: bool = typer.Option(False, "--skip-news"),
) -> None:
    since_dt = datetime.fromisoformat(since)
    selected = list(CASES.values()) if case.lower() == "all" else [CASES[case.upper()]]

    total = 0
    for cfg in selected:
        console.print(f"\n[bold]Case {cfg.id} — {cfg.name}[/bold]")
        if cfg.sec_tickers:
            total += _ingest_sec(cfg, since_dt, max_filings)
        if cfg.news_tickers and not skip_news:
            total += _ingest_news(cfg, since_dt)
        if cfg.cvm_companies:
            total += _ingest_cvm(cfg, since_dt, max_docs=25)
        if cfg.bacen_datasets:
            total += _ingest_bacen(cfg)

    console.print(f"\n[green]Ingestao concluida: {total} documentos[/green]")
    console.print("Proximo passo: python scripts/index.py --fresh")


if __name__ == "__main__":
    app()
