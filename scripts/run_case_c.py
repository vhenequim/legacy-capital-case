"""Case C — Backtest: aceleração de RPO antecipa a reação da ação?

Pipeline:
1. Extrai RPO dos 8-K/10-Q reais indexados (structured/rpo.py)
2. Determina a data/hora do evento de earnings via acceptanceDateTime da SEC
   (antes da abertura -> reação no próprio pregão; após fechamento -> D+1)
3. Calcula YoY growth e aceleração (growth_t - growth_{t-1})
4. Cruza com o retorno do primeiro pregão pós-divulgação (Yahoo Finance)
"""

import json
from datetime import datetime
from pathlib import Path

import pandas as pd
import typer
from rich.console import Console
from rich.table import Table

from legacy_retrieval.cases import CASE_C
from legacy_retrieval.config import get_settings
from legacy_retrieval.ingestion.sec_edgar import TICKER_CIK, SecEdgarFetcher
from legacy_retrieval.models import Document
from legacy_retrieval.structured.prices import fetch_daily_prices, reaction_return
from legacy_retrieval.structured.rpo import best_total_rpo, extract_rpo_observations

app = typer.Typer(help="Run Case C RPO acceleration backtest")
console = Console()


def _load_observations(docs_dir: Path) -> pd.DataFrame:
    tickers = set(CASE_C.sec_tickers)
    rows = []
    for path in sorted(docs_dir.glob("sec_*.json")):
        doc = Document.model_validate(json.loads(path.read_text(encoding="utf-8")))
        if doc.company not in tickers:
            continue
        if doc.metadata.get("form") not in ("8-K", "10-Q", "10-K"):
            continue
        best = best_total_rpo(extract_rpo_observations(doc))
        if best is None:
            continue
        rows.append(
            {
                "company": best.company,
                "filed_at": best.event_date,
                "accession": best.accession,
                "document_id": best.document_id,
                "form": doc.metadata.get("form"),
                "rpo_value": best.value,
                "stated_yoy_pct": best.stated_yoy_pct,
                "pattern_rank": best.pattern_rank,
            }
        )
    return pd.DataFrame(rows)


def _dedupe_quarters(df: pd.DataFrame) -> pd.DataFrame:
    """Um evento por trimestre por empresa (8-K e 10-Q do mesmo período duplicam)."""
    df = df.copy()
    df["quarter_key"] = df["filed_at"].dt.to_period("Q").astype(str)
    df = df.sort_values(["company", "filed_at", "pattern_rank"])
    return df.groupby(["company", "quarter_key"], as_index=False).first()


def _acceptance_times(companies: list[str]) -> dict[str, datetime]:
    """accession -> acceptanceDateTime (ET) via SEC submissions."""
    result: dict[str, datetime] = {}
    with SecEdgarFetcher() as sec:
        for ticker in companies:
            cik = TICKER_CIK.get(ticker)
            if not cik:
                continue
            try:
                submissions = sec._submissions(cik)
            except Exception:
                continue
            recent = submissions.get("filings", {}).get("recent", {})
            for accession, accepted in zip(
                recent.get("accessionNumber", []),
                recent.get("acceptanceDateTime", []),
                strict=False,
            ):
                try:
                    result[accession] = datetime.fromisoformat(accepted.rstrip("Z"))
                except ValueError:
                    continue
    return result


def _classify_timing(accepted_et: datetime | None) -> str:
    if accepted_et is None:
        return "post_market"  # conservador: maioria divulga após o fechamento
    hour = accepted_et.hour + accepted_et.minute / 60
    if hour < 9.5:
        return "pre_market"
    if hour >= 16.0:
        return "post_market"
    return "intraday"


@app.command()
def main(
    output_dir: Path = typer.Option(Path("data/processed/case_c"), "--output-dir"),
) -> None:
    settings = get_settings()
    docs_dir = settings.processed_data_dir / "documents"

    console.print("[bold]1. Extraindo RPO dos filings reais[/bold]")
    obs = _load_observations(docs_dir)
    if obs.empty:
        console.print("[red]Nenhuma observação de RPO encontrada. Rode a ingestão antes.[/red]")
        raise typer.Exit(1)
    events = _dedupe_quarters(obs)
    console.print(f"  {len(events)} eventos trimestrais de {events['company'].nunique()} empresas")

    console.print("[bold]2. Horário de divulgação (SEC acceptanceDateTime)[/bold]")
    acceptance = _acceptance_times(sorted(events["company"].unique()))
    events["accepted_at"] = events["accession"].map(acceptance)
    events["timing"] = events["accepted_at"].apply(_classify_timing)

    console.print("[bold]3. Crescimento YoY e aceleração[/bold]")
    events = events.sort_values(["company", "filed_at"]).reset_index(drop=True)
    frames = []
    for company, group in events.groupby("company"):
        group = group.sort_values("filed_at").reset_index(drop=True)
        computed = group["rpo_value"].pct_change(periods=4) * 100
        group["yoy_pct"] = group["stated_yoy_pct"].fillna(computed)
        group["acceleration_pp"] = group["yoy_pct"].diff()
        frames.append(group)
    events = pd.concat(frames, ignore_index=True)

    console.print("[bold]4. Retorno do primeiro pregão pós-divulgação[/bold]")
    start = events["filed_at"].min() - pd.Timedelta(days=10)
    end = datetime.utcnow()
    prices = fetch_daily_prices(sorted(events["company"].unique()), start, end, settings)

    returns, reaction_dates = [], []
    for _, row in events.iterrows():
        timing = row["timing"] if row["timing"] != "intraday" else "pre_market"
        result = reaction_return(prices, row["company"], row["filed_at"], timing)
        if result is None:
            reaction_dates.append(None)
            returns.append(None)
        else:
            reaction_dates.append(result[0])
            returns.append(result[1])
    events["reaction_date"] = reaction_dates
    events["next_day_return_pct"] = [r * 100 if r is not None else None for r in returns]

    valid = events.dropna(subset=["acceleration_pp", "next_day_return_pct"]).copy()
    console.print(f"  {len(valid)} eventos com aceleração e retorno calculados")

    summary: dict = {"n_events": int(len(valid)), "n_companies": int(valid["company"].nunique())}
    if len(valid) >= 3:
        pearson = valid["acceleration_pp"].corr(valid["next_day_return_pct"])
        spearman = valid["acceleration_pp"].corr(valid["next_day_return_pct"], method="spearman")
        accel_pos = valid[valid["acceleration_pp"] > 0]
        accel_neg = valid[valid["acceleration_pp"] <= 0]
        summary.update(
            {
                "pearson_corr": round(float(pearson), 4),
                "spearman_corr": round(float(spearman), 4),
                "accel_positive": {
                    "n": int(len(accel_pos)),
                    "mean_return_pct": round(float(accel_pos["next_day_return_pct"].mean()), 3)
                    if len(accel_pos)
                    else None,
                    "hit_rate_positive_return": round(
                        float((accel_pos["next_day_return_pct"] > 0).mean()), 3
                    )
                    if len(accel_pos)
                    else None,
                },
                "accel_negative": {
                    "n": int(len(accel_neg)),
                    "mean_return_pct": round(float(accel_neg["next_day_return_pct"].mean()), 3)
                    if len(accel_neg)
                    else None,
                    "hit_rate_positive_return": round(
                        float((accel_neg["next_day_return_pct"] > 0).mean()), 3
                    )
                    if len(accel_neg)
                    else None,
                },
            }
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    events_out = events.drop(columns=["quarter_key"])
    events_out.to_csv(output_dir / "rpo_backtest_events.csv", index=False)
    (output_dir / "rpo_backtest_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )

    table = Table(title="Case C — RPO Acceleration vs Next-Day Return")
    for col in ("company", "quarter", "RPO ($B)", "YoY %", "Accel (pp)", "Return %", "timing"):
        table.add_column(col)
    for _, r in valid.sort_values(["company", "filed_at"]).iterrows():
        table.add_row(
            r["company"],
            str(pd.Timestamp(r["filed_at"]).date()),
            f"{r['rpo_value'] / 1e9:.1f}",
            f"{r['yoy_pct']:.1f}" if pd.notna(r["yoy_pct"]) else "-",
            f"{r['acceleration_pp']:+.1f}",
            f"{r['next_day_return_pct']:+.2f}",
            r["timing"],
        )
    console.print(table)
    console.print(json.dumps(summary, indent=2))
    console.print(f"\n[green]Resultados salvos em {output_dir}[/green]")


if __name__ == "__main__":
    app()
