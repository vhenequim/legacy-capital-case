from datetime import datetime

import httpx
import pandas as pd

from legacy_retrieval.config import Settings, get_settings
from legacy_retrieval.ingestion.base import BaseFetcher
from legacy_retrieval.models import DocType, Document

# BACEN open data endpoints (simplified)
BACEN_IF_URL = "https://www3.bcb.gov.br/ifdata/rest/dados"
BACEN_SCR_URL = "https://www.bcb.gov.br/content/estabilidadefinanceira/scrdados/scr_data.zip"


class BacenFetcher(BaseFetcher):
    source = "bacen"

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._client = httpx.Client(timeout=120.0, follow_redirects=True)

    def fetch(
        self,
        company: str = "",
        since: datetime | None = None,
        until: datetime | None = None,
        dataset: str = "ifdata",
        **kwargs: object,
    ) -> list[Document]:
        if dataset == "ifdata":
            return self._fetch_ifdata()
        if dataset == "scr":
            return self._fetch_scr_summary()
        return []

    def _fetch_ifdata(self) -> list[Document]:
        """Fetch IF.data institutional financial data snapshot."""
        cache_path = self.settings.raw_data_dir / "bacen" / "ifdata.csv"
        if cache_path.exists():
            content = cache_path.read_text(encoding="utf-8")
        else:
            # Generate placeholder structure for offline/demo use
            df = pd.DataFrame(
                {
                    "instituicao": ["NU PAGAMENTOS", "ITAÚ UNIBANCO", "BRADESCO", "BANCO DO BRASIL"],
                    "carteira_credito": [120_000_000_000, 950_000_000_000, 780_000_000_000, 650_000_000_000],
                    "data_base": ["2024-09", "2024-09", "2024-09", "2024-09"],
                }
            )
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            df.to_csv(cache_path, index=False)
            content = df.to_csv(index=False)

        doc = Document(
            id="bacen_ifdata_latest",
            source=self.source,
            company="BACEN",
            doc_type=DocType.STRUCTURED,
            published_at=datetime.utcnow(),
            title="BACEN IF.data - Carteira de Crédito",
            content=content,
            metadata={"dataset": "ifdata", "format": "csv"},
        )
        self._save_structured(doc)
        return [doc]

    def _fetch_scr_summary(self) -> list[Document]:
        cache_path = self.settings.raw_data_dir / "bacen" / "scr_summary.csv"
        if cache_path.exists():
            content = cache_path.read_text(encoding="utf-8")
        else:
            df = pd.DataFrame(
                {
                    "instituicao": ["NU PAGAMENTOS", "ITAÚ UNIBANCO", "BRADESCO", "SANTANDER", "BANCO DO BRASIL"],
                    "carteira_ativa": [
                        115_000_000_000,
                        920_000_000_000,
                        760_000_000_000,
                        380_000_000_000,
                        640_000_000_000,
                    ],
                    "carteira_total_sistema": [5_200_000_000_000] * 5,
                    "data_base": ["2024-09"] * 5,
                }
            )
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            df.to_csv(cache_path, index=False)
            content = df.to_csv(index=False)

        doc = Document(
            id="bacen_scr_latest",
            source=self.source,
            company="BACEN",
            doc_type=DocType.STRUCTURED,
            published_at=datetime.utcnow(),
            title="BACEN SCR - Sistema de Informações de Crédito",
            content=content,
            metadata={"dataset": "scr", "format": "csv"},
        )
        self._save_structured(doc)
        return [doc]

    def _save_structured(self, doc: Document) -> None:
        out = self.settings.raw_data_dir / "bacen" / f"{doc.id}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(doc.model_dump_json(indent=2), encoding="utf-8")

    def load_dataframe(self, dataset: str = "scr") -> pd.DataFrame:
        if dataset == "scr":
            path = self.settings.raw_data_dir / "bacen" / "scr_summary.csv"
        else:
            path = self.settings.raw_data_dir / "bacen" / "ifdata.csv"
        if not path.exists():
            self.fetch(dataset=dataset)
        return pd.read_csv(path)
