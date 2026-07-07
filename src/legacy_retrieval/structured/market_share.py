import pandas as pd

from legacy_retrieval.ingestion.bacen import BacenFetcher


def calculate_market_share(
    df: pd.DataFrame,
    institution: str,
    portfolio_col: str = "carteira_ativa",
    total_col: str = "carteira_total_sistema",
) -> pd.DataFrame:
    """Calculate market share = bank portfolio / total system portfolio."""
    mask = df["instituicao"].str.contains(institution, case=False, na=False)
    bank_rows = df[mask].copy()
    if bank_rows.empty:
        return pd.DataFrame()

    if total_col in df.columns:
        bank_rows["market_share"] = bank_rows[portfolio_col] / bank_rows[total_col]
    else:
        total = df[portfolio_col].sum()
        bank_rows["market_share"] = bank_rows[portfolio_col] / total

    return bank_rows[["instituicao", portfolio_col, "market_share", "data_base"]]


def get_market_share_report(institution: str) -> dict:
    fetcher = BacenFetcher()
    df = fetcher.load_dataframe("scr")
    result = calculate_market_share(df, institution)
    if result.empty:
        return {"institution": institution, "market_share": None, "error": "Institution not found"}

    row = result.iloc[0]
    return {
        "institution": row["instituicao"],
        "portfolio": float(row["carteira_ativa"]),
        "market_share": float(row["market_share"]),
        "data_base": row["data_base"],
    }
