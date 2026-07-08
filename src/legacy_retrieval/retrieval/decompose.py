"""Decomposição de perguntas multi-entidade.

Perguntas que comparam N empresas diluem o retrieval: os documentos de cada
empresa competem entre si dentro de um único top-k (falha diagnosticada pelo
eval na q03 — capex anual de Amazon E Meta na mesma pergunta). A solução é
determinística e sem LLM: detectar as empresas mencionadas, gerar uma
sub-query focada por empresa (removendo as menções às demais) e intercalar
os resultados, garantindo cobertura de todas as entidades.
"""

import re

# Aliases seguros: casam sem distinção de caixa (nomes inequívocos).
SAFE_ALIASES: dict[str, list[str]] = {
    "MSFT": ["microsoft"],
    "AMZN": ["amazon"],
    "GOOGL": ["google", "alphabet"],
    "NVDA": ["nvidia"],
    "ORCL": ["oracle"],
    "CRWV": ["coreweave"],
    "NBIS": ["nebius"],
    "CRM": ["salesforce"],
    "NOW": ["servicenow"],
    "HUBS": ["hubspot"],
    "NET": ["cloudflare"],
    "DDOG": ["datadog"],
    "SNOW": ["snowflake"],
    "AKAM": ["akamai"],
    "PANW": ["palo alto networks", "palo alto"],
    "CRWD": ["crowdstrike"],
    "OKTA": ["okta"],
    "TEAM": ["atlassian"],
    "GTLB": ["gitlab"],
    "ZS": ["zscaler"],
    "ITUB": ["itaú", "itau"],
    "BBD": ["bradesco"],
    "BSBR": ["santander"],
    "BBAS": ["banco do brasil"],
    "NU": ["nubank", "nu holdings"],
}

# Aliases ambíguos: são palavras comuns ("meta de crescimento", "sap")
# e só casam com a capitalização exata de nome próprio.
CASED_ALIASES: dict[str, list[str]] = {
    "META": ["Meta", "Facebook"],
    "SAP": ["SAP"],
    "MNDY": ["Monday.com", "monday.com"],
}


def _compile() -> list[tuple[str, re.Pattern]]:
    patterns: list[tuple[str, re.Pattern]] = []
    for ticker, aliases in SAFE_ALIASES.items():
        for alias in aliases:
            patterns.append((ticker, re.compile(rf"\b{re.escape(alias)}\b", re.IGNORECASE)))
        patterns.append((ticker, re.compile(rf"\b{re.escape(ticker)}\b")))
    for ticker, aliases in CASED_ALIASES.items():
        for alias in aliases:
            patterns.append((ticker, re.compile(rf"\b{re.escape(alias)}\b")))
        patterns.append((ticker, re.compile(rf"\b{re.escape(ticker)}\b")))
    return patterns


_PATTERNS = _compile()


def detect_companies(question: str) -> list[str]:
    """Tickers das empresas mencionadas, na ordem da primeira menção."""
    found: dict[str, int] = {}
    for ticker, pattern in _PATTERNS:
        match = pattern.search(question)
        if match and (ticker not in found or match.start() < found[ticker]):
            found[ticker] = match.start()
    return sorted(found, key=found.get)


def _strip_companies(question: str, tickers: list[str]) -> str:
    """Remove as menções aos tickers dados, limpando conectores soltos."""
    text = question
    for ticker, pattern in _PATTERNS:
        if ticker in tickers:
            text = pattern.sub(" ", text)
    text = re.sub(r"\s+(and|e|ou|or)\s+(?=[,.?\s])", " ", text)
    text = re.sub(r"\s*,\s*,", ",", text)
    text = re.sub(r"\s*,\s*([.?])", r"\1", text)
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip()


def build_subqueries(question: str, max_companies: int = 4) -> list[str]:
    """Uma sub-query por empresa quando a pergunta menciona 2+ empresas.

    Cada sub-query mantém o texto original com as OUTRAS empresas removidas,
    enviesando BM25 e embeddings para a entidade em foco. Acima de
    max_companies a decomposição é abortada (pergunta provavelmente setorial,
    não comparativa).
    """
    companies = detect_companies(question)
    if len(companies) < 2 or len(companies) > max_companies:
        return [question]

    subqueries = []
    for ticker in companies:
        others = [t for t in companies if t != ticker]
        subqueries.append(_strip_companies(question, others))
    return subqueries
