"""Full underwriting deep-dive for a single property."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st
import pandas as pd
from datetime import datetime

from config import load_settings, OUTPUTS_DIR
from models.property import Property
from models.underwriting import UWAssumptions
from models.database import get_session, upsert_deal
from underwriting.engine import underwrite
from underwriting.assumptions import get_default_assumptions, assumptions_from_dict
from excel.generator import generate_excel

st.set_page_config(page_title="Underwrite Deal", page_icon="📊", layout="wide")
st.title("📊 Underwrite a Deal")

# ── Property Input ────────────────────────────────────────────────────────
if "selected_prop" in st.session_state:
    prop: Property = st.session_state.selected_prop
    st.success(f"Loaded from pipeline: **{prop.address}, {prop.city}, {prop.state}**")
else:
    st.info("No property selected from pipeline. Enter details manually below.")
    prop = None

with st.expander("📍 Property Details", expanded=prop is None):
    col1, col2, col3 = st.columns(3)
    address = col1.text_input("Address", value=prop.address if prop else "")
    city = col2.text_input("City", value=prop.city if prop else "")
    state = col3.text_input("State (2-letter)", value=prop.state if prop else "CA", max_chars=2)
    col4, col5, col6 = st.columns(3)
    units = col4.number_input("Units", min_value=1, max_value=50, value=prop.units if prop else 4)
    purchase_price = col5.number_input("Purchase Price ($)", min_value=50_000, max_value=10_000_000,
                                        value=int(prop.purchase_price) if prop else 1_200_000, step=25_000)
    monthly_rent_total = col6.number_input("Monthly Rent Total ($)", min_value=0, max_value=100_000,
                                            value=int(prop.monthly_rent_total) if prop and prop.monthly_rent_total else 0,
                                            step=100)
    col7, col8 = st.columns(2)
    year_built = col7.number_input("Year Built", min_value=1900, max_value=2024,
                                    value=prop.year_built if prop and prop.year_built else 1980)
    sqft = col8.number_input("Total SF", min_value=0, max_value=50_000,
                               value=prop.sqft if prop and prop.sqft else 0)
    listing_url = st.text_input("Listing URL", value=prop.listing_url if prop else "")

# ── Underwriting Assumptions ──────────────────────────────────────────────
defaults = get_default_assumptions()

with st.expander("⚙️ Underwriting Assumptions", expanded=False):
    st.markdown("**Financing (7/1 IO ARM)**")
    col1, col2, col3 = st.columns(3)
    ltv = col1.slider("LTV", 0.50, 0.90, defaults.ltv, step=0.01, format="%.0f%%")
    rate = col2.slider("Interest Rate", 0.03, 0.12, defaults.interest_rate, step=0.0025, format="%.3f%%")
    io_years = col3.slider("IO Period (Years)", 1, 10, defaults.io_years)

    col4, col5 = st.columns(2)
    hold_years = col4.slider("Hold Period (Years)", 3, 15, defaults.hold_years)
    closing_cost_pct = col5.slider("Closing Cost %", 0.0, 0.08, defaults.closing_cost_pct, step=0.005, format="%.1f%%")

    st.markdown("**Income**")
    col1, col2, col3 = st.columns(3)
    market_rent_override = col1.number_input(
        "Rent Override / Unit / Month ($, 0 = use listing)",
        min_value=0, max_value=10_000,
        value=int(defaults.market_rent_per_unit) if defaults.market_rent_per_unit else 0,
        step=50,
    )
    vacancy = col2.slider("Vacancy Rate", 0.0, 0.25, defaults.vacancy_rate, step=0.01, format="%.0f%%")
    other_income = col3.number_input("Other Income / Unit / Month ($)", value=defaults.other_income_per_unit_monthly, step=10.0)
    rent_growth = st.slider("Rent Growth (Annual)", 0.0, 0.10, defaults.rent_growth_annual, step=0.005, format="%.1f%%")

    st.markdown("**Operating Expenses**")
    col1, col2, col3 = st.columns(3)
    tax_rate = col1.slider("Tax Rate (% of value)", 0.005, 0.03, defaults.tax_rate_of_value, step=0.001, format="%.2f%%")
    insurance_pu = col2.number_input("Insurance / Unit / Year ($)", value=defaults.insurance_per_unit, step=50.0)
    utilities_pu = col3.number_input("Utilities / Unit / Month ($)", value=defaults.utilities_per_unit_monthly, step=10.0)
    col4, col5, col6 = st.columns(3)
    maintenance_pu = col4.number_input("Maintenance / Unit / Year ($)", value=defaults.maintenance_per_unit, step=50.0)
    mgmt_pct = col5.slider("Mgmt Fee (% EGI)", 0.0, 0.15, defaults.mgmt_pct_of_egi, step=0.005, format="%.1f%%")
    capex_pu = col6.number_input("CapEx Reserve / Unit / Year ($)", value=defaults.capex_reserve_per_unit, step=25.0)
    admin_pu = st.number_input("Admin / Unit / Year ($)", value=defaults.admin_per_unit, step=25.0)

    st.markdown("**Exit**")
    exit_spread = st.slider("Exit Cap Spread (vs. going-in)", -0.02, 0.05, defaults.exit_cap_spread,
                             step=0.0025, format="%.2f%%")

# Build working property object
working_prop = Property(
    address=address or "Unknown",
    city=city or "",
    state=(state or "CA").upper(),
    units=int(units),
    purchase_price=float(purchase_price),
    monthly_rent_total=float(monthly_rent_total) if monthly_rent_total else None,
    year_built=int(year_built) if year_built else None,
    sqft=int(sqft) if sqft else None,
    listing_url=listing_url or "",
    source=prop.source if prop else "manual",
    scraped_at=prop.scraped_at if prop else datetime.utcnow(),
)

# Build assumptions
uw_assumptions = UWAssumptions(
    ltv=ltv,
    interest_rate=rate,
    io_years=io_years,
    hold_years=hold_years,
    closing_cost_pct=closing_cost_pct,
    market_rent_per_unit=float(market_rent_override) if market_rent_override > 0 else None,
    vacancy_rate=vacancy,
    other_income_per_unit_monthly=other_income,
    rent_growth_annual=rent_growth,
    tax_rate_of_value=tax_rate,
    insurance_per_unit=insurance_pu,
    utilities_per_unit_monthly=utilities_pu,
    maintenance_per_unit=maintenance_pu,
    mgmt_pct_of_egi=mgmt_pct,
    capex_reserve_per_unit=capex_pu,
    admin_per_unit=admin_pu,
    exit_cap_spread=exit_spread,
)

# ── Run Underwriting ──────────────────────────────────────────────────────
try:
    results = underwrite(working_prop, uw_assumptions)
    uw_error = None
except Exception as e:
    results = None
    uw_error = str(e)

if uw_error:
    st.error(f"Underwriting error: {uw_error}")
elif results:
    st.markdown("---")
    st.subheader("📈 Results")

    # ── Key Metrics ──
    k1, k2, k3, k4, k5, k6 = st.columns(6)
    def _pct(v): return f"{v:.1%}" if v is not None else "—"
    def _dol(v): return f"${v:,.0f}" if v is not None else "—"

    cap_color = "normal" if results.going_in_cap_rate >= 0.06 else "inverse"
    coc_color = "normal" if results.coc_y1 >= 0.07 else "inverse"
    dscr_color = "normal" if results.dscr_y1 >= 1.25 else "inverse"
    irr_color = "normal" if (results.irr_5yr or 0) >= 0.12 else "inverse"

    k1.metric("Cap Rate", _pct(results.going_in_cap_rate), delta="vs 6% target" if results.going_in_cap_rate < 0.06 else None)
    k2.metric("Cash-on-Cash Y1", _pct(results.coc_y1))
    k3.metric("DSCR Y1", f"{results.dscr_y1:.2f}x")
    k4.metric("NOI (Year 1)", _dol(results.noi))
    k5.metric("5yr IRR", _pct(results.irr_5yr))
    k6.metric("10yr IRR", _pct(results.irr_10yr))

    # ── Returns table ──
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("**Investment Summary**")
        summary_data = {
            "Metric": ["Purchase Price", "Loan Amount (75% LTV)", "Equity Invested",
                       "Annual IO Debt Service", "NOI Year 1", "Net Cash Flow Y1",
                       "Exit Price (Year 10)", "Equity Multiple 5yr", "Equity Multiple 10yr"],
            "Value": [
                _dol(working_prop.purchase_price), _dol(results.loan_amount),
                _dol(results.equity_invested), _dol(results.annual_ds_io),
                _dol(results.noi), _dol(results.net_cash_flow_y1),
                _dol(results.exit_price),
                f"{results.equity_multiple_5yr:.2f}x", f"{results.equity_multiple_10yr:.2f}x",
            ]
        }
        st.dataframe(pd.DataFrame(summary_data), use_container_width=True, hide_index=True)

    with col_b:
        st.markdown("**Year-by-Year Cash Flows**")
        ym_data = []
        for ym in results.yearly_metrics:
            ym_data.append({
                "Year": ym["year"],
                "NOI": f"${ym['noi']:,.0f}",
                "Debt Svc": f"${ym['debt_service']:,.0f}",
                "Net CF": f"${ym['net_cash_flow']:,.0f}",
                "DSCR": f"{ym['noi']/ym['debt_service']:.2f}x" if ym['debt_service'] else "—",
                "Period": "IO" if ym["is_io"] else "Am",
            })
        st.dataframe(pd.DataFrame(ym_data), use_container_width=True, hide_index=True)

    st.markdown("---")

    # ── Actions ──
    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("📥 Generate Excel Report", type="primary", use_container_width=True):
            with st.spinner("Generating Excel workbook..."):
                try:
                    excel_path = generate_excel(working_prop, uw_assumptions, results)
                    with open(excel_path, "rb") as f:
                        st.download_button(
                            label="⬇️ Download Excel",
                            data=f,
                            file_name=excel_path.name,
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            use_container_width=True,
                        )
                    st.session_state["last_excel_path"] = str(excel_path)
                    st.success(f"Excel saved: {excel_path.name}")
                except Exception as e:
                    st.error(f"Excel error: {e}")

    # ── Save Decision ──
    with st.expander("💾 Save Decision to Tracker", expanded=False):
        dec_col1, dec_col2 = st.columns(2)
        decision = dec_col1.radio("Decision", ["buy", "pass", "watch"], horizontal=True)
        status = dec_col2.selectbox("Status", ["pipeline", "underwritten", "pursuing", "pass", "closed"])
        pass_reason = st.text_input("Pass Reason (if passing)",
                                     placeholder="e.g., Cap rate too thin, too much deferred maintenance")
        notes = st.text_area("Notes", placeholder="Observations, comp rents, seller motivation, etc.")

        if st.button("💾 Save to Deal Tracker", use_container_width=True):
            session = get_session()
            excel_path_str = st.session_state.get("last_excel_path")
            upsert_deal(session, {
                "address": working_prop.address, "city": working_prop.city,
                "state": working_prop.state, "zip_code": working_prop.zip_code,
                "units": working_prop.units, "year_built": working_prop.year_built,
                "sqft": working_prop.sqft, "purchase_price": working_prop.purchase_price,
                "asking_price": working_prop.asking_price,
                "monthly_rent_total": working_prop.monthly_rent_total,
                "listing_url": working_prop.listing_url, "source": working_prop.source,
                "scraped_at": working_prop.scraped_at,
                "gpr": results.gpr, "vacancy_rate": uw_assumptions.vacancy_rate,
                "egi": results.egi, "other_income": results.other_income,
                "total_opex": results.total_opex, "noi": results.noi,
                "going_in_cap_rate": results.going_in_cap_rate,
                "loan_amount": results.loan_amount, "equity_invested": results.equity_invested,
                "annual_ds": results.annual_ds_io, "net_cash_flow_y1": results.net_cash_flow_y1,
                "coc_y1": results.coc_y1, "dscr_y1": results.dscr_y1,
                "price_per_unit": results.price_per_unit,
                "irr_5yr": results.irr_5yr, "irr_10yr": results.irr_10yr,
                "equity_multiple_5yr": results.equity_multiple_5yr,
                "equity_multiple_10yr": results.equity_multiple_10yr,
                "status": status, "decision": decision,
                "pass_reason": pass_reason or None, "notes": notes or None,
                "excel_path": excel_path_str,
                "underwritten_at": datetime.utcnow(),
                "uw_assumptions_json": uw_assumptions.model_dump(),
            })
            session.close()
            st.success("Deal saved to tracker!")
