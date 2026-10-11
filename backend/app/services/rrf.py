"""Reciprocal Rank Fusion.

Combines ranked lists by rank only: ``score(d) = sum(1 / (k + rank))`` with ranks from 1.
Raw BM25 and cosine scores are never mixed.
"""
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field


@dataclass
class FusedHit:
    id: str
    score: float
    ranks: dict[str, int] = field(default_factory=dict)


def reciprocal_rank_fusion(rankings: Mapping[str, Sequence[str]], k: int = 60) -> list[FusedHit]:
    fused: dict[str, FusedHit] = {}
    for channel, ranked_ids in rankings.items():
        seen: set[str] = set()
        rank = 0
        for candidate in ranked_ids:
            if candidate in seen:
                continue
            seen.add(candidate)
            rank += 1
            hit = fused.setdefault(candidate, FusedHit(id=candidate, score=0.0))
            hit.score += 1.0 / (k + rank)
            hit.ranks[channel] = rank
    return sorted(fused.values(), key=lambda h: (-h.score, min(h.ranks.values()), h.id))
