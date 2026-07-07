"""Ingest real Case A data from SEC EDGAR and news feeds."""

from datetime import datetime
from pathlib import Path

import typer
from rich.console import Console
from rich.progress import track

from legacy_retrieval.cases import CASE_A
from legacy_retrieval.config import get_settings
from legacy_retrieval.ingestion.ir_scraper import IrScraper
from legacy_retrieval.ingestion.news import NewsFetcher
from legacy_retrieval.ingestion.sec_edgar import SecEdgarFetcher
from legacy_retrieval.models import Document

app = typer.Typer(help="Ingest Case A: hyperscalers + NVIDIA from official sources")
console = Console()


def _save_documents(docs: list[Document], out_dir: Path) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    for doc in docs:
        path = out_dir / f"{doc.id}.json"
        path.write_text(doc.model_dump_json(indent=2), encoding="utf-8")
    return len(docs)


def _clear_case_a_documents(proc_dir: Path) -> None:
    """Remove prior SEC/news documents before fresh ingest."""
    if not proc_dir.exists():
        return
    removed = 0
    for path in proc_dir.glob("*.json"):
        name = path.name
        if name.startswith(("sec_", "news_", "ri_")) or "_demo_" in name:
            path.unlink()
            removed += 1
    if removed:
        console.print(f"[yellow]Removed {removed} prior documents from {proc_dir}[/yellow]")


@app.command()
def main(
    since: str = typer.Option("2023-01-01", "--since", help="Start date YYYY-MM-DD"),
    max_filings: int = typer.Option(15, "--max", help="Max SEC filings per company"),
    skip_news: bool = typer.Option(False, "--skip-news", help="Skip news RSS ingestion"),
    skip_ri: bool = typer.Option(False, "--skip-ri", help="Skip IR site scraping"),
    fresh: bool = typer.Option(True, "--fresh/--no-fresh", help="Clear prior Case A docs"),
) -> None:
    settings = get_settings()
    since_dt = datetime.fromisoformat(since)
    proc_out = settings.processed_data_dir / "documents"
    raw_base = settings.raw_data_dir

    if fresh:
        _clear_case_a_documents(proc_out)

    total = 0
    sec = SecEdgarFetcher(settings)

    console.print("[bold]Case A — SEC EDGAR ingest[/bold]")
    for ticker in track(CASE_A.sec_tickers, description="SEC filings"):
        try:
            docs = sec.fetch(company=ticker, since=since_dt, max_filings=max_filings)
            raw_out = raw_base / "sec" / ticker.lower()
            count = _save_documents(docs, raw_out)
            count = _save_documents(docs, proc_out)
            total += count
            console.print(f"  {ticker}: {count} filings")
        except Exception as exc:
            console.print(f"  [red]{ticker}: failed — {exc}[/red]")

    sec.close()

    if not skip_ri:
        console.print("\n[bold]Case A — Investor Relations scrape[/bold]")
        with IrScraper(settings) as ri:
            for ticker in track(CASE_A.ri_tickers, description="IR sites"):
                try:
                    docs = ri.fetch(company=ticker, since=since_dt)
                    raw_out = raw_base / "ri" / ticker.lower()
                    count = _save_documents(docs, raw_out)
                    count = _save_documents(docs, proc_out)
                    total += count
                    console.print(f"  {ticker}: {count} IR documents")
                except Exception as exc:
                    console.print(f"  [red]{ticker}: failed — {exc}[/red]")

    if not skip_news:
        console.print("\n[bold]Case A — News RSS ingest[/bold]")
        news = NewsFetcher(settings)
        for ticker in track(CASE_A.news_tickers, description="News"):
            try:
                docs = news.fetch(company=ticker, since=since_dt, max_items=10)
                raw_out = raw_base / "news" / ticker.lower()
                count = _save_documents(docs, raw_out)
                count = _save_documents(docs, proc_out)
                total += count
                console.print(f"  {ticker}: {count} articles")
            except Exception as exc:
                console.print(f"  [red]{ticker}: failed — {exc}[/red]")

    console.print(f"\n[green]Case A ingest complete: {total} documents[/green]")
    console.print("Next: python scripts/index.py --fresh")


if __name__ == "__main__":
    app()
