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
from underwriting.scoring import score_deal
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

    quant_score = score_deal(results, working_prop)
    score_color = "#22c55e" if quant_score >= 7.5 else "#f59e0b" if quant_score >= 5.0 else "#ef4444"
    st.markdown(
        f'<span style="background:{score_color};color:white;padding:4px 14px;'
        f'border-radius:6px;font-size:18px;font-weight:bold">Score: {quant_score:.1f}/10</span>',
        unsafe_allow_html=True,
    )
    st.write("")

    def _pct(v): return f"{v:.1%}" if v is not None else "—"
    def _dol(v): return f"${v:,.0f}" if v is not None else "—"

    # ── Row 1: Core return metrics ──
    k1, k2, k3, k4, k5, k6 = st.columns(6)
    k1.metric("Cap Rate", _pct(results.going_in_cap_rate))
    k2.metric("Cash-on-Cash Y1", _pct(results.coc_y1))
    k3.metric("DSCR Y1", f"{results.dscr_y1:.2f}x")
    k4.metric("NOI (Year 1)", _dol(results.noi))
    k5.metric("5yr IRR", _pct(results.irr_5yr))
    k6.metric("10yr IRR", _pct(results.irr_10yr))

    # ── Row 2: Advanced metrics ──
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Debt Yield", _pct(results.debt_yield))
    m2.metric("Breakeven Occ", _pct(results.breakeven_occupancy))
    m3.metric("Unlevered IRR", _pct(results.unlevered_irr))
    m4.metric("5yr Equity Multiple", f"{results.equity_multiple_5yr:.2f}x" if results.equity_multiple_5yr else "—")
    m5.metric("Price / Unit", _dol(results.price_per_unit))

    # ── Returns table + cashflow ──
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("**Investment Summary**")
        summary_data = {
            "Metric": ["Purchase Price", "Loan Amount", "Equity Invested",
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

    # ── Scenario Analysis ─────────────────────────────────────────────────
    with st.expander("🎭 Scenario Analysis (Base / Bull / Bear / Stress)", expanded=False):
        try:
            from underwriting.scenarios import run_scenarios
            with st.spinner("Running scenarios..."):
                scenario_map = run_scenarios(working_prop, uw_assumptions)

            sc_rows = []
            for name, sr in scenario_map.items():
                sc_score = score_deal(sr, working_prop)
                sc_rows.append({
                    "Scenario": name.upper(),
                    "Cap Rate": _pct(sr.going_in_cap_rate),
                    "NOI": _dol(sr.noi),
                    "DSCR": f"{sr.dscr_y1:.2f}x",
                    "CoC Y1": _pct(sr.coc_y1),
                    "5yr IRR": _pct(sr.irr_5yr),
                    "Debt Yield": _pct(sr.debt_yield),
                    "Score": f"{sc_score:.1f}",
                })
            sc_df = pd.DataFrame(sc_rows)
            st.dataframe(sc_df, use_container_width=True, hide_index=True)
        except Exception as e:
            st.warning(f"Scenario error: {e}")

    st.markdown("---")

    # ── AI Analysis ───────────────────────────────────────────────────────
    st.subheader("🤖 AI Deal Analysis")

    if "ai_analysis" not in st.session_state:
        st.session_state.ai_analysis = None

    ai_col1, ai_col2 = st.columns([1, 3])
    with ai_col1:
        if st.button("🤖 Run AI Analysis", type="primary", use_container_width=True):
            with st.spinner("Analyzing deal with Claude..."):
                try:
                    from ai.analyzer import analyze_deal
                    st.session_state.ai_analysis = analyze_deal(working_prop, uw_assumptions, results)
                except Exception as e:
                    st.error(f"AI error: {e}")

    analysis = st.session_state.ai_analysis
    if analysis:
        grade_color = {"A": "#22c55e", "B": "#84cc16", "C": "#f59e0b", "D": "#f97316"}.get(analysis.grade, "#ef4444")
        st.markdown(
            f'<span style="background:{analysis.badge_color};color:white;padding:3px 10px;'
            f'border-radius:4px;font-weight:bold;font-size:16px">Score {analysis.score:.1f}/10 &nbsp;|&nbsp; '
            f'Grade {analysis.grade} &nbsp;|&nbsp; {analysis.recommendation}</span>',
            unsafe_allow_html=True,
        )
        st.write("")

        if analysis.memo:
            st.markdown(f"**Investment Thesis:** {analysis.memo}")

        if analysis.comp_context:
            st.caption(analysis.comp_context)

        ai_s, ai_r = st.columns(2)
        with ai_s:
            if analysis.strengths:
                st.markdown("**✅ Strengths**")
                for s in analysis.strengths:
                    st.markdown(f"- {s}")
        with ai_r:
            if analysis.risks:
                st.markdown("**⚠️ Risks**")
                for r in analysis.risks:
                    st.markdown(f"- {r}")

    st.markdown("---")

    # ── Actions ──────────────────────────────────────────────────────────
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

    with col2:
        settings = load_settings()
        email_to = settings.get("report_email_to", "")
        if email_to:
            if st.button("📧 Email This Report", use_container_width=True):
                with st.spinner("Sending report..."):
                    try:
                        from notifications.email_client import EmailClient
                        from models.analysis import DealAnalysis, grade_from_score, recommendation_from_score

                        if analysis:
                            report_analysis = analysis
                        else:
                            report_analysis = DealAnalysis(
                                score=quant_score,
                                grade=grade_from_score(quant_score),
                                recommendation=recommendation_from_score(quant_score),
                                memo="",
                            )

                        excel_path_str = st.session_state.get("last_excel_path")
                        excel_attach = Path(excel_path_str) if excel_path_str else None

                        EmailClient().send_deal_report(
                            email_to, working_prop, results, report_analysis, excel_attach
                        )
                        st.success(f"Report sent to {email_to}")
                    except Exception as e:
                        st.error(f"Email failed: {e}")
        else:
            st.caption("Set report_email_to in Settings to enable email.")

    with col3:
        pass  # reserved

    # ── Save Decision ─────────────────────────────────────────────────────
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

            deal_data = {
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
                "ai_score": quant_score,
            }

            if analysis:
                from models.analysis import grade_from_score
                deal_data.update({
                    "ai_score": analysis.score,
                    "ai_grade": analysis.grade,
                    "ai_memo": analysis.memo,
                    "ai_risks": analysis.risks,
                    "ai_strengths": analysis.strengths,
                })

            upsert_deal(session, deal_data)
            session.close()
            st.success("Deal saved to tracker!")
