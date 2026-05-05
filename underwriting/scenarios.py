"""Scenario modeling — base / bull / bear / stress variants."""
from __future__ import annotations

from models.underwriting import UWAssumptions
from models.property import Property

SCENARIO_DELTAS: dict[str, dict] = {
    "base":   {},
    "bull":   {
        "vacancy_rate":          -0.02,
        "rent_growth_annual":    +0.01,
        "exit_cap_spread":       -0.0025,
    },
    "bear":   {
        "vacancy_rate":          +0.03,
        "rent_growth_annual":    -0.01,
        "exit_cap_spread":       +0.005,
        "interest_rate":         +0.01,
    },
    "stress": {
        "vacancy_rate":          +0.05,
        "rent_growth_annual":    -0.02,
        "exit_cap_spread":       +0.01,
        "interest_rate":         +0.015,
        "capex_reserve_per_unit": 150.0,  # absolute add, not delta — handled below
    },
}

_ABSOLUTE_KEYS = {"capex_reserve_per_unit"}


def run_scenarios(prop: Property, base: UWAssumptions) -> dict[str, object]:
    """Return {scenario_name: UWResults} for all four scenarios."""
    from underwriting.engine import underwrite

    results = {}
    for name, deltas in SCENARIO_DELTAS.items():
        if not deltas:
            results[name] = underwrite(prop, base)
            continue

        updates = {}
        for k, v in deltas.items():
            current = getattr(base, k)
            if k in _ABSOLUTE_KEYS:
                updates[k] = current + v
            else:
                updates[k] = current + v

        # Clamp vacancy between 0 and 0.95
        if "vacancy_rate" in updates:
            updates["vacancy_rate"] = max(0.0, min(0.95, updates["vacancy_rate"]))
        # Clamp rate between 0.01 and 0.20
        if "interest_rate" in updates:
            updates["interest_rate"] = max(0.01, min(0.20, updates["interest_rate"]))

        scenario_assumptions = base.model_copy(update=updates)
        results[name] = underwrite(prop, scenario_assumptions)

    return results
