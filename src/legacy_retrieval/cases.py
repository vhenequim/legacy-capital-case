"""Case definitions for ingestion and validation."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class CaseConfig:
    id: str
    name: str
    sec_tickers: list[str] = field(default_factory=list)
    sec_filing_types: set[str] | None = None
    news_tickers: list[str] = field(default_factory=list)
    ri_tickers: list[str] = field(default_factory=list)
    cvm_companies: list[str] = field(default_factory=list)
    bacen_datasets: list[str] = field(default_factory=list)
    sample_questions: list[str] = field(default_factory=list)


CASE_A = CaseConfig(
    id="A",
    name="NVIDIA / Hyperscaler Capex",
    sec_tickers=["MSFT", "AMZN", "GOOGL", "META", "NVDA", "ORCL", "CRWV", "NBIS"],
    news_tickers=["MSFT", "AMZN", "GOOGL", "META", "NVDA", "ORCL"],
    ri_tickers=["MSFT", "AMZN", "GOOGL", "META", "NVDA", "ORCL", "CRWV"],
    sample_questions=[
        "What capital expenditure guidance did Microsoft provide for fiscal year 2025?",
        "What did NVIDIA comment about AI infrastructure demand from hyperscalers?",
        "Compare capex investment plans across Microsoft, Amazon, and Meta for AI infrastructure.",
        "What is the aggregate capex outlook mentioned by hyperscalers?",
    ],
)

# Bancos brasileiros: ADRs listados na SEC (6-K/20-F trazem os earnings
# releases oficiais) + documentos CVM + dados estruturados BACEN.
CASE_B = CaseConfig(
    id="B",
    name="Bancos brasileiros: guidance, sentimento e market share",
    sec_tickers=["ITUB", "BBD", "BSBR", "NU"],
    sec_filing_types={"6-K", "20-F"},
    cvm_companies=["ITUB4", "BBDC4", "SANB11", "BBAS3"],
    bacen_datasets=["ifdata"],
    sample_questions=[
        "Did Bradesco fulfill its guidance on loan loss provisions?",
        "How did Itau's tone about credit growth change across quarters?",
        "What is Nubank's market share of the total credit portfolio per BACEN data?",
    ],
)

CASE_C = CaseConfig(
    id="C",
    name="Backtest: aceleracao de RPO vs retorno pos-earnings",
    sec_tickers=[
        "CRM", "NOW", "SAP", "HUBS", "NET", "DDOG", "SNOW", "AKAM",
        "PANW", "CRWD", "OKTA", "TEAM", "MNDY", "GTLB", "ZS",
    ],
    sec_filing_types={"10-Q", "10-K", "20-F", "6-K", "8-K"},
    sample_questions=[
        "What was Salesforce's remaining performance obligation in the latest quarter?",
        "How did ServiceNow's RPO growth evolve across quarters?",
    ],
)

CASES = {"A": CASE_A, "B": CASE_B, "C": CASE_C}
