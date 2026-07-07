"""Métricas de retrieval no nível de documento.

`expected` usa semântica de GRUPOS: cada item é um conjunto de documentos
alternativos que contêm o mesmo fato (ex.: o 8-K e o 10-Q do mesmo trimestre).
Um grupo é satisfeito se QUALQUER um dos seus documentos foi recuperado; a
pergunta exige que TODOS os grupos sejam satisfeitos. Uma string simples
equivale a um grupo de um único documento.
"""

ExpectedGroups = list[str | list[str]]


def _normalize(expected: ExpectedGroups) -> list[list[str]]:
    return [[g] if isinstance(g, str) else list(g) for g in expected]


def recall_at_k(retrieved_ids: list[str], expected: ExpectedGroups, k: int) -> float:
    groups = _normalize(expected)
    if not groups:
        return 1.0
    top_k = set(retrieved_ids[:k])
    hits = sum(1 for group in groups if any(doc in top_k for doc in group))
    return hits / len(groups)


def precision_at_k(retrieved_ids: list[str], expected: ExpectedGroups, k: int) -> float:
    if k == 0:
        return 0.0
    top_k = retrieved_ids[:k]
    if not top_k:
        return 0.0
    relevant = {doc for group in _normalize(expected) for doc in group}
    hits = sum(1 for rid in top_k if rid in relevant)
    return hits / k


def mrr(retrieved_ids: list[str], expected: ExpectedGroups) -> float:
    relevant = {doc for group in _normalize(expected) for doc in group}
    for rank, rid in enumerate(retrieved_ids, start=1):
        if rid in relevant:
            return 1.0 / rank
    return 0.0


def refusal_correct(refused: bool, answerable: bool) -> bool:
    if answerable:
        return not refused
    return refused
