"""AI-powered deal analysis using the Claude API."""
from __future__ import annotations

import os
import json
import re
from dataclasses import dataclass

from models.analysis import DealAnalysis, grade_from_score, recommendation_from_score
from underwriting.scoring import score_deal


_SYSTEM = """You are a senior real estate private equity analyst at a top-tier REPE firm.
You evaluate multifamily investment opportunities with institutional rigor.
Respond ONLY with valid JSON matching the schema provided — no markdown fences, no prose."""

_SCHEMA = {
    "memo": "string (3-4 sentence investment thesis)",
    "strengths": ["array of 2-4 brief bullet strings"],
    "risks": ["array of 3-5 brief bullet strings"],
    "comp_context": "string (1-2 sentences comparing metrics to typical market ranges)",
}


def _build_prompt(prop, assumptions, results) -> str:
    quant_score = score_deal(results, prop)
    return f"""Analyze this multifamily investment opportunity and return JSON only.

PROPERTY
--------
Address:       {prop.address}, {prop.city}, {prop.state}
Units:         {prop.units}
Year Built:    {getattr(prop, 'year_built', 'Unknown')}
Purchase Price: ${prop.purchase_price:,.0f}
Price/Unit:    ${results.price_per_unit:,.0f}
Source:        {prop.source}

UNDERWRITING METRICS
--------------------
Going-in Cap Rate:    {results.going_in_cap_rate:.2%}
Year-1 NOI:           ${results.noi:,.0f}
Year-1 CoC:           {results.coc_y1:.2%}
DSCR Year-1:          {results.dscr_y1:.2f}x
5-Year IRR:           {f"{results.irr_5yr:.2%}" if results.irr_5yr else "N/A"}
10-Year IRR:          {f"{results.irr_10yr:.2%}" if results.irr_10yr else "N/A"}
5yr Equity Multiple:  {results.equity_multiple_5yr:.2f}x
Debt Yield:           {f"{results.debt_yield:.2%}" if results.debt_yield else "N/A"}
Breakeven Occupancy:  {f"{results.breakeven_occupancy:.1%}" if results.breakeven_occupancy else "N/A"}
Unlevered IRR:        {f"{results.unlevered_irr:.2%}" if results.unlevered_irr else "N/A"}
Quantitative Score:   {quant_score}/10

FINANCING
---------
LTV:           {assumptions.ltv:.0%}
Rate:          {assumptions.interest_rate:.2%}
IO Period:     {assumptions.io_years} years
Hold Period:   {assumptions.hold_years} years

Return this JSON and nothing else:
{{
  "memo": "<3-4 sentence investment thesis covering property overview, key strengths, risks, and recommendation>",
  "strengths": ["<strength 1>", "<strength 2>", "<strength 3>"],
  "risks": ["<risk 1>", "<risk 2>", "<risk 3>", "<risk 4>"],
  "comp_context": "<1-2 sentences comparing these metrics to typical {prop.state} multifamily benchmarks>"
}}"""


def analyze_deal(prop, assumptions, results) -> DealAnalysis:
    """
    Call Claude API for AI-powered deal analysis.
    Falls back to quantitative-only scoring if ANTHROPIC_API_KEY is missing.
    """
    quant_score = score_deal(results, prop)

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return DealAnalysis(
            score=quant_score,
            grade=grade_from_score(quant_score),
            recommendation=recommendation_from_score(quant_score),
            memo="AI analysis unavailable — set ANTHROPIC_API_KEY in .env to enable.",
            strengths=[],
            risks=[],
            comp_context="",
        )

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)

        response = client.messages.create(
            model="claude-opus-4-7",
            max_tokens=1024,
            system=_SYSTEM,
            messages=[{"role": "user", "content": _build_prompt(prop, assumptions, results)}],
        )

        text = next((b.text for b in response.content if b.type == "text"), "{}")
        # Strip accidental markdown fences
        text = re.sub(r"^```(?:json)?\s*", "", text.strip())
        text = re.sub(r"\s*```$", "", text.strip())
        data = json.loads(text)

        return DealAnalysis(
            score=quant_score,
            grade=grade_from_score(quant_score),
            recommendation=recommendation_from_score(quant_score),
            memo=data.get("memo", ""),
            strengths=data.get("strengths", []),
            risks=data.get("risks", []),
            comp_context=data.get("comp_context", ""),
        )

    except Exception as e:
        return DealAnalysis(
            score=quant_score,
            grade=grade_from_score(quant_score),
            recommendation=recommendation_from_score(quant_score),
            memo=f"AI analysis error: {e}",
            strengths=[],
            risks=[],
            comp_context="",
        )
