"""Case B — Bancos brasileiros: guidance vs entrega, sentimento e market share.

Partes 1 e 2 usam a plataforma genérica (retrieval + geração grounded).
Parte 3 cruza a estratégia declarada (retrieval) com o market share calculado
a partir do IF.data real do BACEN (estruturado).
"""

import json
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel

from legacy_retrieval.config import get_settings
from legacy_retrieval.indexing.indexer import DocumentIndexer
from legacy_retrieval.pipeline import RetrievalPipeline
from legacy_retrieval.structured.market_share import get_market_share_report

app = typer.Typer(help="Run Case B via the generic retrieval platform")
console = Console()

PART1_GUIDANCE_VS_DELIVERY = [
    "O que o Bradesco disse sobre a expectativa de inadimplência e provisões para devedores "
    "duvidosos, e o que os resultados trimestrais seguintes mostraram sobre essas provisões?",
    "Que guidance ou expectativa o Banco do Brasil apresentou para sua carteira de crédito, "
    "e o resultado divulgado depois confirmou essa expectativa?",
]

PART2_SENTIMENT = [
    "Como o tom do Itaú sobre crescimento de crédito e cenário macroeconômico mudou entre os "
    "trimestres de 2025 e 2026? Ficou mais otimista, mais cauteloso ou estável?",
    "Compare o discurso do Santander Brasil sobre rentabilidade e qualidade da carteira ao longo "
    "dos últimos trimestres disponíveis.",
]

PART3_STRATEGY_QUERIES = {
    "NUBANK": "Qual estratégia de crescimento de crédito o Nubank declarou nos seus resultados recentes?",
    "ITAU": "Qual estratégia para a carteira de crédito o Itaú declarou nos seus resultados recentes?",
    "BRADESCO": "Qual estratégia de crescimento o Bradesco declarou para sua carteira de crédito?",
}


def _load_pipeline() -> RetrievalPipeline:
    settings = get_settings()
    indexer = DocumentIndexer(settings)
    state_dir = settings.processed_data_dir / "index_state"
    if not state_dir.exists():
        console.print("[red]Índice não encontrado. Rode: python scripts/index.py --fresh[/red]")
        raise typer.Exit(1)
    indexer.load_state(state_dir)
    return RetrievalPipeline(indexer, settings)


def _ask(pipeline: RetrievalPipeline, question: str) -> dict:
    response = pipeline.query(question)
    cited = ", ".join(sorted({c.company for c in response.citations[:5]})) or "—"
    console.print(Panel(response.answer, title=question[:110], subtitle=f"fontes: {cited}"))
    return {
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
            }
            for c in response.citations[:5]
        ],
    }


@app.command()
def main(
    output: Path = typer.Option(Path("data/processed/case_b/report.json"), "--output"),
) -> None:
    pipeline = _load_pipeline()
    report: dict = {"part1_guidance_vs_delivery": [], "part2_sentiment": [], "part3_strategy_vs_market_share": []}

    console.print("\n[bold]Parte 1 — Promessa vs entrega[/bold]")
    for q in PART1_GUIDANCE_VS_DELIVERY:
        report["part1_guidance_vs_delivery"].append(_ask(pipeline, q))

    console.print("\n[bold]Parte 2 — Mudança de sentimento[/bold]")
    for q in PART2_SENTIMENT:
        report["part2_sentiment"].append(_ask(pipeline, q))

    console.print("\n[bold]Parte 3 — Estratégia declarada vs market share (BACEN IF.data)[/bold]")
    for institution, strategy_q in PART3_STRATEGY_QUERIES.items():
        share = get_market_share_report(institution)
        entry = {"institution": institution, "market_share": share, "strategy": _ask(pipeline, strategy_q)}
        if share.get("market_share") is not None:
            console.print(
                f"  [cyan]{institution}[/cyan]: carteira R$ {share['portfolio'] / 1e9:.0f} bi "
                f"= {share['market_share'] * 100:.2f}% do sistema (IF.data {share['data_base']})"
            )
        report["part3_strategy_vs_market_share"].append(entry)

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    console.print(f"\n[green]Relatório salvo em {output}[/green]")


if __name__ == "__main__":
    app()
