def recall_at_k(retrieved_ids: list[str], expected_ids: list[str], k: int) -> float:
    if not expected_ids:
        return 1.0
    top_k = set(retrieved_ids[:k])
    hits = sum(1 for eid in expected_ids if eid in top_k)
    return hits / len(expected_ids)


def precision_at_k(retrieved_ids: list[str], expected_ids: list[str], k: int) -> float:
    if k == 0:
        return 0.0
    top_k = retrieved_ids[:k]
    if not top_k:
        return 0.0
    expected = set(expected_ids)
    hits = sum(1 for rid in top_k if rid in expected)
    return hits / k


def mrr(retrieved_ids: list[str], expected_ids: list[str]) -> float:
    expected = set(expected_ids)
    for rank, rid in enumerate(retrieved_ids, start=1):
        if rid in expected:
            return 1.0 / rank
    return 0.0


def refusal_correct(refused: bool, answerable: bool) -> bool:
    if answerable:
        return not refused
    return refused
