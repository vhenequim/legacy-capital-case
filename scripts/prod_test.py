"""
Production-style test runner for Case A.

This is the default way to test the platform: real data, Docker infra, API smoke tests.
"""

import subprocess
import sys
import time

import httpx
import typer
from rich.console import Console
from rich.table import Table

from legacy_retrieval.cases import CASE_A
from legacy_retrieval.config import get_settings
from legacy_retrieval.indexing.indexer import DocumentIndexer
from legacy_retrieval.pipeline import RetrievalPipeline

app = typer.Typer(help="Production-style test runner")
console = Console()

API_URL = "http://localhost:8000"


def _run(cmd: list[str]) -> None:
    console.print(f"[dim]$ {' '.join(cmd)}[/dim]")
    result = subprocess.run(cmd, check=False)
    if result.returncode != 0:
        console.print(f"[red]Command failed: {' '.join(cmd)}[/red]")
        raise typer.Exit(result.returncode)


def _wait_for_qdrant(timeout: int = 30) -> bool:
    settings = get_settings()
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            httpx.get(f"{settings.qdrant_url}/collections", timeout=2.0)
            return True
        except Exception:
            time.sleep(1)
    return False


def _check_ollama() -> bool:
    try:
        resp = httpx.get(f"{get_settings().ollama_base_url}/api/tags", timeout=3.0)
        return resp.status_code == 200
    except Exception:
        return False


@app.command()
def ollama() -> None:
    """Check Ollama is running and model is available."""
    settings = get_settings()
    if not _check_ollama():
        console.print("[red]Ollama não está rodando.[/red]")
        console.print("Instale em https://ollama.com e execute:")
        console.print(f"  ollama pull {settings.ollama_model}")
        console.print("  ollama serve")
        raise typer.Exit(1)
    console.print(f"[green]Ollama OK — model: {settings.ollama_model}[/green]")


@app.command()
def up() -> None:
    """Start Docker infrastructure (Qdrant + Postgres)."""
    _run(["docker", "compose", "up", "-d", "qdrant", "postgres"])
    if _wait_for_qdrant():
        console.print("[green]Infrastructure ready (Qdrant + Postgres)[/green]")
    else:
        console.print("[yellow]Qdrant not responding yet — continuing anyway[/yellow]")


@app.command()
def ingest(
    since: str = typer.Option("2023-01-01", "--since"),
    max_filings: int = typer.Option(15, "--max"),
) -> None:
    """Ingest real Case A data from SEC + news."""
    _run([
        sys.executable,
        "scripts/ingest_cases.py",
        "--case",
        "A",
        "--since",
        since,
        "--max",
        str(max_filings),
    ])


@app.command()
def index() -> None:
    """Index all processed documents (fresh Qdrant collection)."""
    _run([sys.executable, "scripts/index.py", "--fresh"])


@app.command()
def smoke(
    use_api: bool = typer.Option(False, "--api", help="Test via HTTP API instead of pipeline"),
) -> None:
    """Run Case A sample questions and show results."""
    settings = get_settings()

    if use_api:
        table = Table(title="Case A Smoke Test (API)")
        table.add_column("Question")
        table.add_column("Status")
        for question in CASE_A.sample_questions:
            try:
                resp = httpx.post(
                    f"{API_URL}/query",
                    json={"question": question, "top_k": 10},
                    timeout=120.0,
                )
                data = resp.json()
                status = "REFUSED" if data.get("refused") else "OK"
            except Exception as exc:
                status = f"ERROR: {exc}"
            table.add_row(question[:55] + "...", status)
        console.print(table)
        return

    indexer = DocumentIndexer(settings)
    state_dir = settings.processed_data_dir / "index_state"
    if state_dir.exists():
        indexer.load_state(state_dir)
    else:
        console.print("[red]Index not found. Run: python scripts/prod_test.py full[/red]")
        raise typer.Exit(1)

    pipeline = RetrievalPipeline(indexer, settings)
    table = Table(title="Case A Smoke Test (Pipeline)")
    table.add_column("Question")
    table.add_column("Status")
    table.add_column("Citations")

    for question in CASE_A.sample_questions:
        response = pipeline.query(question)
        status = "REFUSED" if response.refused else "OK"
        table.add_row(question[:50] + "...", status, str(len(response.citations)))

    console.print(table)


@app.command()
def full(
    since: str = typer.Option("2023-01-01", "--since"),
    max_filings: int = typer.Option(10, "--max", help="Filings per company (lower = faster)"),
    skip_docker: bool = typer.Option(False, "--skip-docker"),
) -> None:
    """Full prod test: docker up → ingest → index → smoke."""
    console.print("[bold]Production test — Case A[/bold]\n")

    if not skip_docker:
        up()

    if get_settings().llm_provider == "ollama":
        if not _check_ollama():
            console.print("[yellow]Ollama offline — LLM cairá para modo extractivo[/yellow]")
        else:
            console.print(f"[green]Ollama online ({get_settings().ollama_model})[/green]")

    ingest(since=since, max_filings=max_filings)
    index()
    smoke()

    console.print("\n[green]Prod test complete.[/green]")
    console.print("Start API: uvicorn legacy_retrieval.api.main:app --reload --port 8000")
    console.print("Then: python scripts/prod_test.py smoke --api")


@app.command()
def explain() -> None:
    """Print what each AI component does in this system."""
    console.print("""
[bold]Where AI is used in this platform[/bold]

1. [cyan]Embeddings[/cyan] (sentence-transformers, local & free)
   → Converts questions and document chunks into vectors.
   → Lets the system find semantically similar text even without exact keywords.

2. [cyan]Cross-encoder reranker[/cyan] (local & free)
   → Re-scores top candidates against the question.
   → This is the main "understand the question" step for retrieval quality.

3. [cyan]BM25[/cyan] (not ML, classical search)
   → Exact keyword matching: "capex", "RPO", "provisões".

4. [cyan]LLM[/cyan] (optional — synthesis only)
   → Does NOT search documents. Only summarizes retrieved evidence.
   → Options:
      • [green]local[/green] (default) — extractive, no API, free
      • [green]ollama[/green] — free local LLM (llama3.2, mistral, etc.)
      • openai — paid API (best quality)

[bold]Free testing stack (recommended)[/bold]
  EMBEDDING_PROVIDER=local
  LLM_PROVIDER=local        # or ollama if you install Ollama
  docker compose up -d
  python scripts/prod_test.py full

[bold]Case A data sources[/bold]
  SEC EDGAR — filings 10-K, 10-Q, 8-K (free, official)
  News RSS  — Yahoo Finance headlines (free)
""")


if __name__ == "__main__":
    app()
