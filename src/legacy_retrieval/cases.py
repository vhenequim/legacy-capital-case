"""Case definitions for ingestion and validation."""

from dataclasses import dataclass


@dataclass(frozen=True)
class CaseConfig:
    id: str
    name: str
    sec_tickers: list[str]
    news_tickers: list[str]
    ri_tickers: list[str]
    sample_questions: list[str]


CASE_A = CaseConfig(
    id="A",
    name="NVIDIA / Hyperscaler Capex",
    sec_tickers=["MSFT", "AMZN", "GOOGL", "META", "NVDA", "ORCL", "CRWV"],
    news_tickers=["MSFT", "AMZN", "GOOGL", "META", "NVDA", "ORCL"],
    ri_tickers=["MSFT", "AMZN", "GOOGL", "META", "NVDA", "ORCL", "CRWV"],
    sample_questions=[
        "What capital expenditure guidance did Microsoft provide for fiscal year 2025?",
        "What did NVIDIA comment about AI infrastructure demand from hyperscalers?",
        "Compare capex investment plans across Microsoft, Amazon, and Meta for AI infrastructure.",
        "What is the aggregate capex outlook mentioned by hyperscalers?",
    ],
)

CASES = {"A": CASE_A}
