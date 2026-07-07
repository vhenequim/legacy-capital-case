from datetime import datetime
from pathlib import Path

import typer
from rich.console import Console

from legacy_retrieval.config import get_settings
from legacy_retrieval.ingestion.bacen import BacenFetcher
from legacy_retrieval.ingestion.cvm import CvmFetcher
from legacy_retrieval.ingestion.investor_relations import InvestorRelationsFetcher
from legacy_retrieval.ingestion.news import NewsFetcher
from legacy_retrieval.ingestion.sec_edgar import SecEdgarFetcher
from legacy_retrieval.models import Document

app = typer.Typer(help="Ingest documents from official sources")
console = Console()

FETCHERS = {
    "sec": SecEdgarFetcher,
    "cvm": CvmFetcher,
    "bacen": BacenFetcher,
    "ri": InvestorRelationsFetcher,
    "news": NewsFetcher,
}


def _save_documents(docs: list[Document], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for doc in docs:
        path = out_dir / f"{doc.id}.json"
        path.write_text(doc.model_dump_json(indent=2), encoding="utf-8")


@app.command()
def main(
    source: str = typer.Option(..., "--source", "-s", help="Source: sec, cvm, bacen, ri, news"),
    company: str = typer.Option("", "--company", "-c", help="Company ticker"),
    since: str = typer.Option("2023-01-01", "--since", help="Start date YYYY-MM-DD"),
    max_filings: int = typer.Option(20, "--max", help="Max documents to fetch"),
) -> None:
    settings = get_settings()
    settings.raw_data_dir.mkdir(parents=True, exist_ok=True)
    settings.processed_data_dir.mkdir(parents=True, exist_ok=True)

    since_dt = datetime.fromisoformat(since)
    fetcher_cls = FETCHERS.get(source)
    if not fetcher_cls:
        console.print(f"[red]Unknown source: {source}[/red]")
        raise typer.Exit(1)

    fetcher = fetcher_cls(settings)

    if source == "bacen":
        docs = fetcher.fetch(dataset="scr")
        docs.extend(fetcher.fetch(dataset="ifdata"))
    elif source in {"cvm", "ri"}:
        if not company:
            console.print("[red]--company required for cvm/ri[/red]")
            raise typer.Exit(1)
        docs = fetcher.fetch(company=company, since=since_dt)
    elif source == "news":
        if not company:
            console.print("[red]--company required for news[/red]")
            raise typer.Exit(1)
        docs = fetcher.fetch(company=company, since=since_dt)
    else:
        if not company:
            console.print("[red]--company required for sec[/red]")
            raise typer.Exit(1)
        docs = fetcher.fetch(company=company, since=since_dt, max_filings=max_filings)

    raw_out = settings.raw_data_dir / source / (company.lower() if company else "all")
    proc_out = settings.processed_data_dir / "documents"
    _save_documents(docs, raw_out)
    _save_documents(docs, proc_out)

    console.print(f"[green]Ingested {len(docs)} documents from {source}[/green]")


if __name__ == "__main__":
    app()
