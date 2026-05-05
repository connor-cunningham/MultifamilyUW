from pathlib import Path
import json
import os

BASE_DIR = Path(__file__).parent

# Cloud deployments override these via environment variables so data lands on
# a persistent volume instead of the ephemeral container filesystem.
DB_PATH = Path(os.environ.get("DB_PATH", str(BASE_DIR / "deals.db")))
SETTINGS_PATH = Path(os.environ.get("SETTINGS_PATH", str(BASE_DIR / "settings.json")))
OUTPUTS_DIR = Path(os.environ.get("OUTPUTS_DIR", str(BASE_DIR / "outputs")))
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

WESTERN_US_STATES = [
    "CA", "OR", "WA", "NV", "AZ", "CO", "UT", "ID", "MT", "WY", "NM", "AK", "HI"
]

DEFAULT_ASSUMPTIONS = {
    "ltv": 0.75,
    "interest_rate": 0.0575,
    "io_years": 7,
    "hold_years": 10,
    "vacancy_rate": 0.05,
    "other_income_per_unit_monthly": 75.0,
    "rent_growth_annual": 0.03,
    "tax_rate_of_value": 0.0125,
    "insurance_per_unit": 1200.0,
    "utilities_per_unit_monthly": 75.0,
    "maintenance_per_unit": 850.0,
    "mgmt_pct_of_egi": 0.09,
    "admin_per_unit": 300.0,
    "capex_reserve_per_unit": 275.0,
    "expense_growth_annual": 0.03,
    "exit_cap_spread": 0.0025,
    "closing_cost_pct": 0.03,
    "transaction_cost_pct": 0.03,
}


def load_settings() -> dict:
    if SETTINGS_PATH.exists():
        with open(SETTINGS_PATH) as f:
            saved = json.load(f)
        merged = DEFAULT_ASSUMPTIONS.copy()
        merged.update(saved)
        return merged
    return DEFAULT_ASSUMPTIONS.copy()


def save_settings(settings: dict) -> None:
    with open(SETTINGS_PATH, "w") as f:
        json.dump(settings, f, indent=2)
