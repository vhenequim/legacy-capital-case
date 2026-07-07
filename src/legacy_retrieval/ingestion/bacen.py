"""BACEN IF.data via API Olinda (OData) — dados reais de carteira de crédito.

Fonte: https://olinda.bcb.gov.br/olinda/servico/IFDATA/versao/v1/odata/
Relatório 1 (Resumo), TipoInstituicao=3 (instituições individuais), que traz
a coluna "Carteira de Crédito" por instituição. O market share é calculado
como carteira da instituição / soma das carteiras do sistema.
"""

from datetime import datetime

import httpx
import pandas as pd

from legacy_retrieval.config import Settings, get_settings
from legacy_retrieval.ingestion.base import BaseFetcher
from legacy_retrieval.models import DocType, Document

IFDATA_BASE = "https://olinda.bcb.gov.br/olinda/servico/IFDATA/versao/v1/odata"
TIPO_INSTITUICAO = 3  # instituições individuais
RELATORIO_RESUMO = "1"

# Nomes por raiz de CNPJ (CodInst do IF.data) para as instituições relevantes.
# O endpoint IfDataCadastro (que traria os nomes) está instável; este mapa é
# apenas rotulagem de códigos públicos — os VALORES vêm 100% da API.
CNPJ_NAMES: dict[str, str] = {
    "00360305": "CAIXA ECONOMICA FEDERAL",
    "00000000": "BANCO DO BRASIL",
    "60746948": "BRADESCO",
    "60701190": "ITAU UNIBANCO",
    "60872504": "ITAU UNIBANCO HOLDING",
    "90400888": "SANTANDER BRASIL",
    "33657248": "BNDES",
    "18236120": "NU PAGAMENTOS",
    "30680829": "NU FINANCEIRA",
    "58160789": "SAFRA",
    "30306294": "BTG PACTUAL",
    "00416968": "BANCO INTER",
    "31872495": "C6 BANK",
    "10664513": "AGIBANK",
    "07707650": "SICREDI",
    "02038232": "SICOOB",
    "92702067": "BANRISUL",
    "59588111": "BANCO VOTORANTIM",
    "17184037": "BANCO MERCANTIL",
    "04902979": "BANCO DA AMAZONIA",
    "07237373": "BANCO DO NORDESTE",
}

# Agrupamentos para market share por grupo econômico (ex.: Nubank opera
# crédito em duas entidades reguladas distintas).
INSTITUTION_GROUPS: dict[str, list[str]] = {
    "NUBANK": ["18236120", "30680829"],
    "ITAU": ["60701190", "60872504"],
    "BRADESCO": ["60746948"],
    "SANTANDER": ["90400888"],
    "BANCO DO BRASIL": ["00000000"],
    "CAIXA": ["00360305"],
}


class BacenFetcher(BaseFetcher):
    source = "bacen"

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._client = httpx.Client(timeout=120.0, follow_redirects=True)

    def close(self) -> None:
        self._client.close()

    def _candidate_quarters(self, count: int = 8) -> list[int]:
        """Trimestres IF.data (mar/jun/set/dez) do mais recente ao mais antigo."""
        now = datetime.utcnow()
        year, month = now.year, now.month
        quarters: list[int] = []
        qmonths = [12, 9, 6, 3]
        while len(quarters) < count:
            for qm in qmonths:
                if year < now.year or qm <= month:
                    quarters.append(year * 100 + qm)
                    if len(quarters) >= count:
                        break
            year -= 1
            month = 12
        return quarters

    def _fetch_valores(self, ano_mes: int) -> list[dict]:
        url = (
            f"{IFDATA_BASE}/IfDataValores("
            f"AnoMes=@AnoMes,TipoInstituicao=@TipoInstituicao,Relatorio=@Relatorio)"
        )
        response = self._client.get(
            url,
            params={
                "@AnoMes": str(ano_mes),
                "@TipoInstituicao": str(TIPO_INSTITUICAO),
                "@Relatorio": f"'{RELATORIO_RESUMO}'",
                "$format": "json",
            },
        )
        response.raise_for_status()
        payload = response.json()
        return payload.get("value", [])

    def fetch_ifdata_dataframe(self, ano_mes: int | None = None) -> pd.DataFrame:
        """Baixa (ou lê do cache) o Resumo IF.data como DataFrame."""
        quarters = [ano_mes] if ano_mes else self._candidate_quarters()

        for quarter in quarters:
            cache = self.settings.raw_data_dir / "bacen" / f"ifdata_{quarter}.csv"
            if cache.exists():
                return pd.read_csv(cache, dtype={"cod_inst": str})

            try:
                rows = self._fetch_valores(quarter)
            except httpx.HTTPError:
                continue
            carteira = [r for r in rows if "Carteira" in (r.get("NomeColuna") or "")]
            if not carteira:
                continue

            df = pd.DataFrame(
                {
                    "cod_inst": [r["CodInst"] for r in carteira],
                    "instituicao": [
                        CNPJ_NAMES.get(r["CodInst"], r["CodInst"]) for r in carteira
                    ],
                    "carteira_credito": [float(r["Saldo"] or 0) for r in carteira],
                    "data_base": [str(quarter)] * len(carteira),
                }
            )
            df["carteira_total_sistema"] = df["carteira_credito"].sum()
            cache.parent.mkdir(parents=True, exist_ok=True)
            df.to_csv(cache, index=False)
            return df

        raise RuntimeError(
            "IF.data indisponível: nenhum trimestre retornou dados da API Olinda "
            f"({IFDATA_BASE}). Tente novamente mais tarde."
        )

    def fetch(
        self,
        company: str = "",
        since: datetime | None = None,
        until: datetime | None = None,
        dataset: str = "ifdata",
        ano_mes: int | None = None,
        **kwargs: object,
    ) -> list[Document]:
        if dataset != "ifdata":
            raise ValueError(f"Dataset BACEN não suportado: {dataset}")

        df = self.fetch_ifdata_dataframe(ano_mes)
        quarter = str(df["data_base"].iloc[0])
        total = float(df["carteira_total_sistema"].iloc[0])

        top = df.nlargest(30, "carteira_credito").copy()
        top["market_share_pct"] = 100 * top["carteira_credito"] / total

        lines = [
            f"BACEN IF.data — Carteira de Crédito por instituição (data-base {quarter}).",
            f"Fonte: API Olinda IFDATA, TipoInstituicao={TIPO_INSTITUICAO}, Relatório Resumo.",
            f"Carteira total do sistema financeiro: R$ {total:,.0f}.",
            "",
            "Top 30 instituições por carteira de crédito (R$ e % do sistema):",
        ]
        for _, row in top.iterrows():
            lines.append(
                f"- {row['instituicao']}: R$ {row['carteira_credito']:,.0f} "
                f"({row['market_share_pct']:.2f}% do sistema)"
            )
        lines.append("")
        lines.append("Grupos econômicos (soma das entidades reguladas):")
        for group, codes in INSTITUTION_GROUPS.items():
            value = df[df["cod_inst"].isin(codes)]["carteira_credito"].sum()
            lines.append(
                f"- {group}: R$ {value:,.0f} ({100 * value / total:.2f}% do sistema)"
            )

        year, month = int(quarter[:4]), int(quarter[4:])
        doc = Document(
            id=f"bacen_ifdata_{quarter}",
            source=self.source,
            company="BACEN",
            doc_type=DocType.STRUCTURED,
            published_at=datetime(year, month, 1),
            title=f"BACEN IF.data — Carteira de Crédito ({quarter})",
            url=IFDATA_BASE,
            content="\n".join(lines),
            metadata={"dataset": "ifdata", "ano_mes": quarter, "tipo_instituicao": TIPO_INSTITUICAO},
        )
        self._save_structured(doc)
        return [doc]

    def _save_structured(self, doc: Document) -> None:
        out = self.settings.raw_data_dir / "bacen" / f"{doc.id}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(doc.model_dump_json(indent=2), encoding="utf-8")

    def load_dataframe(self, dataset: str = "ifdata", ano_mes: int | None = None) -> pd.DataFrame:
        if dataset != "ifdata":
            raise ValueError(f"Dataset BACEN não suportado: {dataset}")
        return self.fetch_ifdata_dataframe(ano_mes)
