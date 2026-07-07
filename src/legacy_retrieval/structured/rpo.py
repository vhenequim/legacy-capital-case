"""Extração de RPO (Remaining Performance Obligations) de press releases 8-K.

Calibrado nas variações reais observadas na base:
- "Total Remaining Performance Obligation $63B, up 11% Y/Y"
- "Current remaining performance obligation of $29.6 billion, up 12% Y/Y"
- "Remaining performance obligation grew 21% year over year to $13.0 billion"
- Guidance em faixa ("$15.2B - $15.3B") é descartado.
"""

import re
from dataclasses import dataclass
from datetime import datetime

from legacy_retrieval.models import Document

_UNIT = {"billion": 1e9, "million": 1e6, "b": 1e9, "m": 1e6}

# "$63B", "$29.6 billion", "$13,0 billion"
_MONEY = r"\$\s*([\d][\d,.]*)\s*(billion|million|B|M)\b"

# (rank, pattern) — rank menor = mais confiável para o valor REPORTADO
RPO_VALUE_PATTERNS: list[tuple[int, re.Pattern]] = [
    # "remaining performance obligation grew 21% year over year to $13.0 billion"
    (
        0,
        re.compile(
            r"remaining performance obligations?\s+grew\s+([\d.]+)%[^.$]{0,80}?to\s*" + _MONEY,
            re.I,
        ),
    ),
    # "remaining performance obligation(s) [("RPO")] [of|was|totaled|:] $X billion"
    (
        1,
        re.compile(
            r"remaining performance obligations?\s*(?:\([^)]{0,20}\))?\s*"
            r"(?:of|was|were|totaled|totaling|:)?\s*" + _MONEY,
            re.I,
        ),
    ),
    # 10-Q/10-K: "$X billion of revenue (is|was) expected to be recognized from
    # remaining performance obligations"
    (
        2,
        re.compile(
            _MONEY
            + r"\s*of\s*(?:total\s*)?revenue\s*(?:is|was)?\s*expected to be recognized"
            r"\s*from\s*(?:the\s*)?remaining performance obligations",
            re.I,
        ),
    ),
]

# "up 11% Y/Y", "up 12% year-over-year", "grew 21% year over year"
_YOY_NEAR = re.compile(r"(?:up|grew|increased|growth of)\s+([\d.]+)\s*%", re.I)

_GUIDANCE_NEAR = re.compile(r"guidance|outlook|expect|forecast|will be|estimated", re.I)


@dataclass
class RpoObservation:
    company: str
    event_date: datetime
    document_id: str
    accession: str
    metric: str  # "rpo" (total) | "crpo" (current)
    value: float
    stated_yoy_pct: float | None
    pattern_rank: int = 9  # menor = extraído de frase mais inequívoca


def _to_value(raw: str, unit: str) -> float:
    return float(raw.replace(",", "")) * _UNIT[unit.lower()]


def extract_rpo_observations(doc: Document) -> list[RpoObservation]:
    text = doc.content
    seen: set[str] = set()
    observations: list[RpoObservation] = []

    for rank, pattern in RPO_VALUE_PATTERNS:
        for match in pattern.finditer(text):
            start, end = match.start(), match.end()
            before = text[max(0, start - 150) : start]
            after = text[end : end + 150]

            # Descarta guidance/faixas: "$15.2B - $15.3B" ou contexto de outlook
            if re.match(r"\s*[-–]\s*\$", after):
                continue
            if _GUIDANCE_NEAR.search(before[-100:]) or _GUIDANCE_NEAR.search(after[:80]):
                continue

            groups = match.groups()
            if rank == 0:  # padrão "grew X% ... to $Y"
                yoy = float(groups[0])
                value = _to_value(groups[1], groups[2])
            else:
                value = _to_value(groups[0], groups[1])
                yoy_match = _YOY_NEAR.search(after[:80]) or _YOY_NEAR.search(before[-60:])
                yoy = float(yoy_match.group(1)) if yoy_match else None

            metric = "crpo" if re.search(r"current\s*$", before[-30:], re.I) else "rpo"

            key = f"{metric}:{value:.0f}"
            if key in seen:
                continue
            seen.add(key)

            observations.append(
                RpoObservation(
                    company=doc.company,
                    event_date=doc.published_at,
                    document_id=doc.id,
                    accession=str(doc.metadata.get("accession", "")),
                    metric=metric,
                    value=value,
                    stated_yoy_pct=yoy,
                    pattern_rank=rank,
                )
            )

    return observations


def best_total_rpo(observations: list[RpoObservation]) -> RpoObservation | None:
    """Melhor observação de RPO total de um mesmo documento."""
    totals = [o for o in observations if o.metric == "rpo"]
    if not totals:
        return None
    with_yoy = [o for o in totals if o.stated_yoy_pct is not None]
    pool = with_yoy or totals
    return min(pool, key=lambda o: o.pattern_rank)
