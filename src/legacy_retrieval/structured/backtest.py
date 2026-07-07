from dataclasses import dataclass

import pandas as pd

from legacy_retrieval.structured.metrics import calculate_acceleration, calculate_yoy_growth


@dataclass
class BacktestResult:
    company: str
    period: str
    rpo_value: float
    yoy_growth: float | None
    acceleration: float | None
    next_day_return: float | None
    earnings_timing: str  # pre_market | post_market


def run_rpo_backtest(
    rpo_df: pd.DataFrame,
    returns_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Run RPO acceleration backtest.

    rpo_df columns: company, period, value, earnings_date, timing
    returns_df columns: company, date, return
    """
    results: list[dict] = []

    for company in rpo_df["company"].unique():
        company_rpo = rpo_df[rpo_df["company"] == company].sort_values("period")
        growth = calculate_yoy_growth(company_rpo["value"])
        acceleration = calculate_acceleration(growth)

        for idx, row in company_rpo.iterrows():
            pos = company_rpo.index.get_loc(idx)
            yoy = (
                float(growth.iloc[pos])
                if pos < len(growth) and pd.notna(growth.iloc[pos])
                else None
            )
            accel = (
                float(acceleration.iloc[pos])
                if pos < len(acceleration) and pd.notna(acceleration.iloc[pos])
                else None
            )

            next_return = None
            if "earnings_date" in row and pd.notna(row["earnings_date"]):
                ed = pd.to_datetime(row["earnings_date"])
                company_returns = returns_df[returns_df["company"] == company]
                if not company_returns.empty:
                    company_returns = company_returns.copy()
                    company_returns["date"] = pd.to_datetime(company_returns["date"])
                    after = company_returns[company_returns["date"] > ed].sort_values("date")
                    if not after.empty:
                        next_return = float(after.iloc[0]["return"])

            results.append(
                {
                    "company": company,
                    "period": row["period"],
                    "rpo_value": float(row["value"]),
                    "yoy_growth": yoy,
                    "acceleration": accel,
                    "next_day_return": next_return,
                    "earnings_timing": row.get("timing", "unknown"),
                }
            )

    return pd.DataFrame(results)


def summarize_backtest(backtest_df: pd.DataFrame) -> dict:
    if backtest_df.empty:
        return {"hit_rate": 0.0, "sample_size": 0}

    valid = backtest_df.dropna(subset=["acceleration", "next_day_return"])
    if valid.empty:
        return {"hit_rate": 0.0, "sample_size": 0}

    positive_accel = valid[valid["acceleration"] > 0]
    hits = positive_accel[positive_accel["next_day_return"] > 0]

    return {
        "hit_rate": len(hits) / len(positive_accel) if len(positive_accel) > 0 else 0.0,
        "sample_size": len(valid),
        "positive_accel_count": len(positive_accel),
        "mean_return_when_accel_positive": float(positive_accel["next_day_return"].mean())
        if len(positive_accel) > 0
        else 0.0,
    }
