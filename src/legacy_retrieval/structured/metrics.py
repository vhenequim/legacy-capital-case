import re
from dataclasses import dataclass

import pandas as pd


@dataclass
class MetricPoint:
    company: str
    metric: str
    period: str
    value: float


RPO_PATTERNS = [
    re.compile(r"remaining performance obligation[s]?\s*(?:of\s*)?\$?\s*([\d,.]+)\s*(billion|million)?", re.I),
    re.compile(r"RPO\s*(?:of\s*)?\$?\s*([\d,.]+)\s*(billion|million)?", re.I),
    re.compile(r"current remaining performance obligation[s]?\s*\$?\s*([\d,.]+)\s*(billion|million)?", re.I),
]

CAPEX_PATTERNS = [
    re.compile(r"capital expenditure[s]?\s*(?:of\s*)?\$?\s*([\d,.]+)\s*(billion|million)?", re.I),
    re.compile(r"capex\s*(?:of\s*)?\$?\s*([\d,.]+)\s*(billion|million)?", re.I),
]


def _parse_amount(raw: str, unit: str | None) -> float:
    value = float(raw.replace(",", ""))
    if unit and unit.lower() == "billion":
        return value * 1_000_000_000
    if unit and unit.lower() == "million":
        return value * 1_000_000
    return value


def extract_metrics(text: str, company: str, metric: str = "rpo") -> list[MetricPoint]:
    patterns = RPO_PATTERNS if metric.lower() == "rpo" else CAPEX_PATTERNS
    points: list[MetricPoint] = []

    for pattern in patterns:
        for match in pattern.finditer(text):
            value = _parse_amount(match.group(1), match.group(2))
            window = text[max(0, match.start() - 100) : match.end() + 100]
            period_match = re.search(r"Q[1-4]\s*(?:FY)?\s*\d{4}|\d{4}", window)
            period = period_match.group(0) if period_match else "unknown"
            points.append(MetricPoint(company=company, metric=metric, period=period, value=value))

    return points


def metrics_to_dataframe(points: list[MetricPoint]) -> pd.DataFrame:
    rows = [
        {"company": p.company, "metric": p.metric, "period": p.period, "value": p.value}
        for p in points
    ]
    return pd.DataFrame(rows)


def calculate_yoy_growth(series: pd.Series) -> pd.Series:
    return series.pct_change(periods=4)


def calculate_acceleration(growth_series: pd.Series) -> pd.Series:
    return growth_series.diff()
