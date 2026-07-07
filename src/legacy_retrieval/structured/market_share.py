"""Market share de crédito a partir do IF.data (BACEN).

Market share = carteira de crédito da instituição / carteira total do sistema.
"""

import pandas as pd

from legacy_retrieval.ingestion.bacen import INSTITUTION_GROUPS, BacenFetcher


def calculate_market_share(df: pd.DataFrame, institution: str) -> dict | None:
    """Calcula o share de uma instituição ou grupo econômico (ex.: NUBANK, ITAU)."""
    total = float(df["carteira_total_sistema"].iloc[0])
    key = institution.upper().strip()

    group_codes = INSTITUTION_GROUPS.get(key)
    if group_codes:
        rows = df[df["cod_inst"].isin(group_codes)]
        label = key
    else:
        mask = df["instituicao"].str.contains(institution, case=False, na=False)
        rows = df[mask]
        label = rows["instituicao"].iloc[0] if not rows.empty else institution

    if rows.empty:
        return None

    portfolio = float(rows["carteira_credito"].sum())
    return {
        "institution": label,
        "entities": rows["instituicao"].tolist(),
        "portfolio": portfolio,
        "system_total": total,
        "market_share": portfolio / total,
        "data_base": str(rows["data_base"].iloc[0]),
    }


def get_market_share_report(institution: str, ano_mes: int | None = None) -> dict:
    fetcher = BacenFetcher()
    df = fetcher.load_dataframe("ifdata", ano_mes)
    result = calculate_market_share(df, institution)
    if result is None:
        return {
            "institution": institution,
            "market_share": None,
            "error": "Institution not found in IF.data",
        }
    return result
