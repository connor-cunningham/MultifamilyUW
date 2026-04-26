"""Settings — configure default underwriting assumptions."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st
from config import load_settings, save_settings, DEFAULT_ASSUMPTIONS

st.set_page_config(page_title="Settings", page_icon="⚙️", layout="wide")
st.title("⚙️ Default Underwriting Assumptions")
st.caption("These defaults apply to all new underwritings. You can override per-deal on the Underwrite page.")

settings = load_settings()

with st.form("settings_form"):
    st.subheader("Financing (7/1 IO ARM)")
    col1, col2, col3 = st.columns(3)
    ltv = col1.number_input("LTV", min_value=0.50, max_value=0.90, value=settings["ltv"],
                              step=0.01, format="%.2f")
    rate = col2.number_input("Interest Rate", min_value=0.01, max_value=0.20,
                               value=settings["interest_rate"], step=0.0025, format="%.4f")
    io_years = col3.number_input("IO Period (Years)", min_value=1, max_value=10,
                                  value=settings["io_years"], step=1)
    col4, col5 = st.columns(2)
    hold_years = col4.number_input("Hold Period (Years)", min_value=1, max_value=30,
                                    value=settings["hold_years"], step=1)
    closing_cost_pct = col5.number_input("Closing Cost %", min_value=0.0, max_value=0.10,
                                          value=settings["closing_cost_pct"], step=0.005, format="%.3f")

    st.subheader("Income")
    col1, col2, col3 = st.columns(3)
    vacancy_rate = col1.number_input("Vacancy Rate", 0.0, 0.50, settings["vacancy_rate"],
                                      step=0.01, format="%.2f")
    other_income = col2.number_input("Other Income / Unit / Month ($)",
                                      value=settings["other_income_per_unit_monthly"], step=10.0)
    rent_growth = col3.number_input("Rent Growth (Annual)", 0.0, 0.15,
                                     settings["rent_growth_annual"], step=0.005, format="%.3f")

    st.subheader("Operating Expenses")
    col1, col2, col3 = st.columns(3)
    tax_rate = col1.number_input("Tax Rate (% of value)", 0.005, 0.03,
                                  settings["tax_rate_of_value"], step=0.001, format="%.3f")
    insurance_pu = col2.number_input("Insurance / Unit / Year ($)",
                                      value=settings["insurance_per_unit"], step=50.0)
    utilities_pu = col3.number_input("Utilities / Unit / Month ($)",
                                      value=settings["utilities_per_unit_monthly"], step=10.0)
    col4, col5, col6 = st.columns(3)
    maintenance_pu = col4.number_input("Maintenance / Unit / Year ($)",
                                        value=settings["maintenance_per_unit"], step=50.0)
    mgmt_pct = col5.number_input("Mgmt Fee (% EGI)", 0.0, 0.20,
                                  settings["mgmt_pct_of_egi"], step=0.005, format="%.3f")
    capex_pu = col6.number_input("CapEx Reserve / Unit / Year ($)",
                                  value=settings["capex_reserve_per_unit"], step=25.0)
    admin_pu = st.number_input("Admin / Unit / Year ($)", value=settings["admin_per_unit"], step=25.0)
    expense_growth = st.number_input("Expense Growth (Annual)", 0.0, 0.15,
                                      settings["expense_growth_annual"], step=0.005, format="%.3f")

    st.subheader("Exit")
    exit_cap_spread = st.number_input("Exit Cap Spread (vs. going-in)", -0.02, 0.05,
                                       settings["exit_cap_spread"], step=0.0025, format="%.4f")

    col_a, col_b = st.columns(2)
    save = col_a.form_submit_button("💾 Save Settings", type="primary", use_container_width=True)
    reset = col_b.form_submit_button("🔄 Reset to Defaults", use_container_width=True)

if save:
    new_settings = {
        "ltv": ltv, "interest_rate": rate, "io_years": int(io_years),
        "hold_years": int(hold_years), "closing_cost_pct": closing_cost_pct,
        "vacancy_rate": vacancy_rate, "other_income_per_unit_monthly": other_income,
        "rent_growth_annual": rent_growth, "tax_rate_of_value": tax_rate,
        "insurance_per_unit": insurance_pu, "utilities_per_unit_monthly": utilities_pu,
        "maintenance_per_unit": maintenance_pu, "mgmt_pct_of_egi": mgmt_pct,
        "capex_reserve_per_unit": capex_pu, "admin_per_unit": admin_pu,
        "expense_growth_annual": expense_growth, "exit_cap_spread": exit_cap_spread,
        "closing_cost_pct": closing_cost_pct, "transaction_cost_pct": closing_cost_pct,
    }
    save_settings(new_settings)
    st.success("Settings saved!")

if reset:
    save_settings(DEFAULT_ASSUMPTIONS)
    st.success("Reset to defaults!")
    st.rerun()

# Show current settings
with st.expander("📋 Current Effective Settings"):
    import json
    current = load_settings()
    st.code(json.dumps(current, indent=2))
