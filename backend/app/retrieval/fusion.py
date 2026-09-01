from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from app.retrieval.queries import ChunkHit


def reciprocal_rank_fusion(
    dense_hits: Iterable[ChunkHit],
    sparse_hits: Iterable[ChunkHit],
    *,
    k: int = 60,
) -> list[ChunkHit]:
    fused: dict[str, ChunkHit] = {}
    scores: dict[str, float] = defaultdict(float)

    for rank, hit in enumerate(dense_hits, start=1):
        fused.setdefault(hit.chunk_id, hit)
        scores[hit.chunk_id] += 1.0 / (k + rank)

    for rank, hit in enumerate(sparse_hits, start=1):
        fused.setdefault(hit.chunk_id, hit)
        scores[hit.chunk_id] += 1.0 / (k + rank)

    ranked = sorted(fused.values(), key=lambda hit: scores[hit.chunk_id], reverse=True)
    for idx, hit in enumerate(ranked, start=1):
        hit.score = scores[hit.chunk_id]
    return ranked
