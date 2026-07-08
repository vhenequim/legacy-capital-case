"""Constrói o corpus fixture do smoke eval (eval/fixtures/).

Seleciona documentos reais já ingeridos, trunca o conteúdo em janelas ao
redor dos fatos-chave (para caber no repositório) e grava o gold set do
smoke. Rode após uma ingestão completa; o resultado é versionado no git
para o CI rodar o eval de retrieval sem depender de rede ou da base local.
"""

import json
import re
from pathlib import Path

import typer
from rich.console import Console

from legacy_retrieval.config import get_settings
from legacy_retrieval.models import Document

app = typer.Typer()
console = Console()

FIXTURES_DIR = Path("eval/fixtures")

# doc_id -> termos cujas janelas devem sobreviver à truncagem
GOLD_DOCS: dict[str, list[str]] = {
    "sec_0001045810_000104581026000051": ["Data Center revenue", "Blackwell"],
    "sec_0001018724_000101872426000002": ["capital expenditures", "property and equipment"],
    "sec_0001326801_000162828026003832": ["Capital expenditures", "property and equipment"],
    "sec_0001108524_000110852426000056": ["Remaining Performance Obligation"],
    "cvm_bbdc4_67a92c344696": ["Carteira de Crédito Expandida", "Margem Financeira"],
    "bacen_ifdata_202603": ["NUBANK"],
}

# Distratores: documentos reais que NÃO respondem as perguntas do smoke
DISTRACTOR_DOCS: dict[str, list[str]] = {
    "sec_0001045810_000104581026000060": [],
    "sec_0001373715_000137371526000054": ["remaining performance obligations"],
    "cvm_itub4_7388d9f6e31c": ["projeções"],
    "cvm_sanb11_7dc5f1a9dcc7": ["inadimplência"],
    "sec_0001535527_000153552725000005": ["revenue"],
    "ri_msft_7b9106b17e9f": ["cloud"],
}

SMOKE_QUESTIONS = [
    {
        "id": "s01",
        "question": "What was NVIDIA's Data Center revenue in the first quarter of fiscal year 2027?",
        "expected_doc_ids": ["sec_0001045810_000104581026000051"],
        "category": "single_document",
        "answerable": True,
    },
    {
        "id": "s02",
        "question": "How much did Amazon and Meta each report in capital expenditures for the full year 2025?",
        "expected_doc_ids": [
            ["sec_0001018724_000101872426000002"],
            ["sec_0001326801_000162828026003832"],
        ],
        "category": "multi_document",
        "answerable": True,
    },
    {
        "id": "s03",
        "question": (
            "What remaining performance obligation did Salesforce report "
            "in its fourth quarter fiscal 2026 earnings release?"
        ),
        "expected_doc_ids": ["sec_0001108524_000110852426000056"],
        "category": "single_document",
        "answerable": True,
    },
    {
        "id": "s04",
        "question": "Quais foram as projeções (guidance) do Bradesco para 2025?",
        "expected_doc_ids": ["cvm_bbdc4_67a92c344696"],
        "category": "single_document",
        "answerable": True,
    },
    {
        "id": "s05",
        "question": "Qual é o market share do Nubank na carteira de crédito segundo o BACEN?",
        "expected_doc_ids": ["bacen_ifdata_202603"],
        "category": "structured",
        "answerable": True,
    },
    {
        "id": "s90",
        "question": "What was Apple's iPhone revenue in fiscal year 2024?",
        "expected_doc_ids": [],
        "category": "unanswerable",
        "answerable": False,
    },
]

HEAD_CHARS = 2_000
WINDOW_CHARS = 3_000
MAX_CHARS = 15_000


def _truncate(content: str, terms: list[str]) -> str:
    if len(content) <= MAX_CHARS:
        return content

    spans: list[tuple[int, int]] = [(0, HEAD_CHARS)]
    for term in terms:
        for match in list(re.finditer(re.escape(term), content, re.IGNORECASE))[:2]:
            start = max(0, match.start() - WINDOW_CHARS // 2)
            spans.append((start, start + WINDOW_CHARS))

    spans.sort()
    merged: list[list[int]] = []
    for start, end in spans:
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])

    parts = [content[s:e] for s, e in merged]
    return "\n[...]\n".join(parts)[:MAX_CHARS]


@app.command()
def main() -> None:
    settings = get_settings()
    docs_dir = settings.processed_data_dir / "documents"
    out_dir = FIXTURES_DIR / "documents"
    out_dir.mkdir(parents=True, exist_ok=True)

    all_docs = {**GOLD_DOCS, **DISTRACTOR_DOCS}
    written = 0
    for doc_id, terms in all_docs.items():
        src = docs_dir / f"{doc_id}.json"
        if not src.exists():
            console.print(f"[red]{doc_id}: não encontrado em {docs_dir}[/red]")
            continue
        doc = Document.model_validate(json.loads(src.read_text(encoding="utf-8")))
        doc.content = _truncate(doc.content, terms)
        for term in terms:
            if term.lower() not in doc.content.lower():
                console.print(f"[yellow]{doc_id}: termo '{term}' perdido na truncagem[/yellow]")
        (out_dir / f"{doc.id}.json").write_text(doc.model_dump_json(indent=2), encoding="utf-8")
        written += 1

    questions_path = FIXTURES_DIR / "questions_smoke.jsonl"
    questions_path.write_text(
        "\n".join(json.dumps(q, ensure_ascii=False) for q in SMOKE_QUESTIONS) + "\n",
        encoding="utf-8",
    )

    total_kb = sum(p.stat().st_size for p in out_dir.glob("*.json")) // 1024
    console.print(f"[green]{written} fixtures ({total_kb} KB) + {len(SMOKE_QUESTIONS)} perguntas[/green]")


if __name__ == "__main__":
    app()
