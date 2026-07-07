"""Seed demo documents for offline development and eval testing."""

import json
from datetime import datetime
from pathlib import Path

import typer
from rich.console import Console

from legacy_retrieval.config import get_settings
from legacy_retrieval.models import Document

app = typer.Typer()
console = Console()

DEMO_DOCUMENTS: list[dict] = [
    {
        "id": "sec_0000789019_demo_capex",
        "source": "sec_edgar",
        "company": "MSFT",
        "doc_type": "filing",
        "title": "Microsoft FY2025 Capex Guidance",
        "content": (
            "Microsoft expects capital expenditures to increase substantially in fiscal year 2025 "
            "to support cloud and AI infrastructure demand. We anticipate capital expenditure "
            "of approximately $80 billion in FY2025, with the majority directed toward "
            "datacenter expansion and AI compute capacity."
        ),
    },
    {
        "id": "sec_0001018724_demo_capex",
        "source": "sec_edgar",
        "company": "AMZN",
        "doc_type": "filing",
        "title": "Amazon Q4 2024 Capex Outlook",
        "content": (
            "Amazon expects capital expenditures to be approximately $100 billion in 2025, "
            "primarily reflecting investments in technology infrastructure including AWS "
            "datacenters and AI capabilities."
        ),
    },
    {
        "id": "sec_0001326801_demo_capex",
        "source": "sec_edgar",
        "company": "META",
        "doc_type": "filing",
        "title": "Meta AI Infrastructure Investment",
        "content": (
            "Meta plans capital expenditures in the range of $60 to $65 billion in 2025, "
            "driven by generative AI infrastructure and datacenter buildout."
        ),
    },
    {
        "id": "sec_0001045810_demo_demand",
        "source": "sec_edgar",
        "company": "NVDA",
        "doc_type": "filing",
        "title": "NVIDIA Hyperscaler Demand Commentary",
        "content": (
            "NVIDIA noted unprecedented demand for AI infrastructure from hyperscalers including "
            "Microsoft, Amazon, Google, and Meta. Data center revenue grew significantly as "
            "cloud providers expanded GPU deployments for training and inference workloads."
        ),
    },
    {
        "id": "cvm_bbdc4_demo_guidance",
        "source": "cvm",
        "company": "BBDC4",
        "doc_type": "earnings_release",
        "title": "Bradesco Q1 2024 Earnings",
        "content": (
            "O Bradesco informou que pretende reduzir o nível de provisões para devedores "
            "duvidosos ao longo de 2024, refletindo a melhora na qualidade da carteira de crédito. "
            "A guidance de provisões para Q1 2024 indica redução gradual trimestre a trimestre."
        ),
    },
    {
        "id": "cvm_bbdc4_demo_delivery",
        "source": "cvm",
        "company": "BBDC4",
        "doc_type": "earnings_release",
        "title": "Bradesco Q3 2024 Results",
        "content": (
            "No Q3 2024, o Bradesco reportou redução de 8% nas provisões para devedores duvidosos "
            "em relação ao mesmo período do ano anterior, cumprindo a orientação dada no início do ano."
        ),
    },
    {
        "id": "cvm_itub4_demo_sentiment",
        "source": "cvm",
        "company": "ITUB4",
        "doc_type": "earnings_release",
        "title": "Itaú Q2 2024 Credit Outlook",
        "content": (
            "O Itaú Unibanco manteve tom cauteloso sobre crescimento de crédito no Q2 2024, "
            "citando cenário macroeconômico desafiador e pressão nas margens."
        ),
    },
    {
        "id": "cvm_itub4_demo_sentiment_q4",
        "source": "cvm",
        "company": "ITUB4",
        "doc_type": "earnings_release",
        "title": "Itaú Q4 2024 Credit Outlook",
        "content": (
            "No Q4 2024, o Itaú apresentou tom mais otimista sobre crescimento da carteira de crédito, "
            "destacando recuperação da demanda por financiamento imobiliário e crédito consignado."
        ),
    },
    {
        "id": "bacen_scr_demo",
        "source": "bacen",
        "company": "BACEN",
        "doc_type": "structured",
        "title": "BACEN SCR Market Share Data",
        "content": (
            "BACEN SCR market share data as of September 2024. "
            "NU PAGAMENTOS (Nubank) holds approximately 2.2% of total system credit portfolio. "
            "instituicao,carteira_ativa,carteira_total_sistema,data_base\n"
            "NU PAGAMENTOS,115000000000,5200000000000,2024-09\n"
            "ITAÚ UNIBANCO,920000000000,5200000000000,2024-09\n"
            "BRADESCO,760000000000,5200000000000,2024-09\n"
        ),
    },
    {
        "id": "sec_0001108524_demo_rpo",
        "source": "sec_edgar",
        "company": "CRM",
        "doc_type": "filing",
        "title": "Salesforce Q3 FY2024 RPO",
        "content": (
            "Salesforce reported remaining performance obligations of $48.3 billion as of Q3 FY2024, "
            "up 17% year-over-year. Current remaining performance obligation grew 12% year-over-year."
        ),
    },
    {
        "id": "sec_0001373715_demo_rpo",
        "source": "sec_edgar",
        "company": "NOW",
        "doc_type": "filing",
        "title": "ServiceNow RPO Q2 and Q3 FY2024",
        "content": (
            "ServiceNow Q2 FY2024: remaining performance obligations of $18.2 billion, RPO growth 22% YoY. "
            "ServiceNow Q3 FY2024: remaining performance obligations of $19.1 billion, RPO growth 24% YoY. "
            "Acceleration in RPO growth from 22% to 24% year-over-year."
        ),
    },
]


@app.command()
def main() -> None:
    settings = get_settings()
    out = settings.processed_data_dir / "documents"
    out.mkdir(parents=True, exist_ok=True)

    for raw in DEMO_DOCUMENTS:
        doc = Document(
            id=raw["id"],
            source=raw["source"],
            company=raw["company"],
            doc_type=raw["doc_type"],
            published_at=datetime(2024, 6, 1),
            title=raw["title"],
            content=raw["content"],
        )
        path = out / f"{doc.id}.json"
        path.write_text(doc.model_dump_json(indent=2), encoding="utf-8")

    # Update eval questions with concrete doc IDs
    eval_path = Path("eval/questions.jsonl")
    if eval_path.exists():
        lines = []
        id_map = {
            "sec_0000789019_*": "sec_0000789019_demo_capex",
            "sec_0001045810_*": "sec_0001045810_demo_demand",
            "sec_0001018724_*": "sec_0001018724_demo_capex",
            "sec_0001326801_*": "sec_0001326801_demo_capex",
            "cvm_bbdc4_*": "cvm_bbdc4_demo_guidance",
            "cvm_itub4_*": "cvm_itub4_demo_sentiment",
            "bacen_scr_*": "bacen_scr_demo",
            "sec_0001108524_*": "sec_0001108524_demo_rpo",
            "sec_0001373715_*": "sec_0001373715_demo_rpo",
        }
        for line in eval_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            q = json.loads(line)
            q["expected_doc_ids"] = [
                id_map.get(eid, eid.replace("*", "demo")) for eid in q["expected_doc_ids"]
            ]
            if q["id"] == "q04":
                q["expected_doc_ids"] = ["cvm_bbdc4_demo_guidance"]
            if q["id"] == "q05":
                q["expected_doc_ids"] = ["cvm_bbdc4_demo_guidance", "cvm_bbdc4_demo_delivery"]
            if q["id"] == "q06":
                q["expected_doc_ids"] = ["cvm_itub4_demo_sentiment", "cvm_itub4_demo_sentiment_q4"]
            lines.append(json.dumps(q, ensure_ascii=False))
        eval_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    console.print(f"[green]Seeded {len(DEMO_DOCUMENTS)} demo documents to {out}[/green]")


if __name__ == "__main__":
    app()
