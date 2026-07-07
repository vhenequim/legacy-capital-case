"""Preços de mercado (Yahoo Finance) para o backtest do Case C.

O retorno usado é o do primeiro pregão em que o mercado pôde reagir à
divulgação:
- divulgação após o fechamento do dia D -> retorno do pregão D+1
- divulgação antes da abertura do dia D -> retorno do próprio pregão D
"""

from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

from legacy_retrieval.config import Settings, get_settings


def fetch_daily_prices(
    tickers: list[str],
    start: datetime,
    end: datetime,
    settings: Settings | None = None,
    use_cache: bool = True,
) -> pd.DataFrame:
    """Baixa preços diários ajustados. Retorna formato longo: company, date, close."""
    settings = settings or get_settings()
    cache = settings.raw_data_dir / "prices" / (
        f"prices_{start:%Y%m%d}_{end:%Y%m%d}_{'-'.join(sorted(tickers))}.csv"
    )
    if use_cache and cache.exists():
        df = pd.read_csv(cache, parse_dates=["date"])
        return df

    import yfinance as yf

    raw = yf.download(
        tickers=" ".join(tickers),
        start=start.strftime("%Y-%m-%d"),
        end=(end + timedelta(days=5)).strftime("%Y-%m-%d"),
        auto_adjust=True,
        progress=False,
        group_by="ticker",
    )

    frames: list[pd.DataFrame] = []
    for ticker in tickers:
        try:
            closes = raw[ticker]["Close"] if len(tickers) > 1 else raw["Close"]
        except KeyError:
            continue
        frame = closes.dropna().reset_index()
        frame.columns = ["date", "close"]
        frame["company"] = ticker
        frames.append(frame[["company", "date", "close"]])

    if not frames:
        raise RuntimeError(f"Yahoo Finance não retornou preços para {tickers}")

    df = pd.concat(frames, ignore_index=True)
    cache.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(cache, index=False)
    return df


def reaction_return(
    prices: pd.DataFrame,
    company: str,
    disclosed_at: datetime,
    timing: str,
) -> tuple[pd.Timestamp, float] | None:
    """Retorno do primeiro pregão pós-divulgação (close a close).

    timing: "pre_market" ou "post_market" relativo ao dia da divulgação.
    """
    series = (
        prices[prices["company"] == company]
        .sort_values("date")
        .reset_index(drop=True)
    )
    if series.empty:
        return None

    disclosure_day = pd.Timestamp(disclosed_at.date())
    if timing == "pre_market":
        # Mercado reage no próprio dia: close(D-1) -> close(D)
        reaction_mask = series["date"] >= disclosure_day
    else:
        # Divulgação após fechamento: close(D) -> close(D+1)
        reaction_mask = series["date"] > disclosure_day

    future = series[reaction_mask]
    if future.empty:
        return None

    idx = future.index[0]
    if idx == 0:
        return None  # sem pregão anterior para calcular retorno

    prev_close = series.loc[idx - 1, "close"]
    close = series.loc[idx, "close"]
    if not prev_close:
        return None
    return series.loc[idx, "date"], float(close / prev_close - 1)


def save_prices(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
