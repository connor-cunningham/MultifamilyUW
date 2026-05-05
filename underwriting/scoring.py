"""Quantitative deal scoring — returns 0.0–10.0."""
from __future__ import annotations

from models.analysis import grade_from_score, recommendation_from_score, DealAnalysis


# Scoring targets
_CAP_TARGET = 0.06       # 6% going-in cap rate
_DSCR_TARGET = 1.25      # 1.25x DSCR
_IRR_TARGET = 0.12       # 12% 5-year IRR
_COC_TARGET = 0.07       # 7% cash-on-cash
_PPU_TARGET = 250_000    # $250k / unit efficiency ceiling


def score_deal(results, prop) -> float:
    """
    Score a deal 0–10 based on five equally-weighted financial metrics.

    Each component is capped at its max weight; partial credit awarded
    proportionally up to 2x the target.
    """
    pts = 0.0

    # 1. Cap rate (max 2.0 pts)
    pts += min(2.0, (results.going_in_cap_rate / _CAP_TARGET) * 2.0)

    # 2. DSCR (max 2.0 pts)
    pts += min(2.0, (results.dscr_y1 / _DSCR_TARGET) * 2.0)

    # 3. 5yr IRR (max 2.0 pts)
    irr = results.irr_5yr or 0.0
    pts += min(2.0, (irr / _IRR_TARGET) * 2.0)

    # 4. Cash-on-cash Y1 (max 2.0 pts)
    pts += min(2.0, (results.coc_y1 / _COC_TARGET) * 2.0)

    # 5. Price/unit efficiency (max 1.0 pts — inverse: lower is better)
    ppu = results.price_per_unit
    pts += min(1.0, (_PPU_TARGET / ppu) * 1.0) if ppu and ppu > 0 else 0.0

    # Bonus: NOI yield (debt yield proxy) if available
    if hasattr(results, "debt_yield") and results.debt_yield:
        pts += min(1.0, (results.debt_yield / 0.08) * 0.5)

    return min(10.0, round(pts, 1))


def analyze_score(results, prop) -> DealAnalysis:
    """Return a lightweight DealAnalysis with quantitative score only (no AI)."""
    from models.analysis import DealAnalysis
    s = score_deal(results, prop)
    return DealAnalysis(
        score=s,
        grade=grade_from_score(s),
        recommendation=recommendation_from_score(s),
        memo="",
        strengths=[],
        risks=[],
    )
