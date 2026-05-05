"""Settings — configure default underwriting assumptions, email, and scheduler."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st
from config import load_settings, save_settings, DEFAULT_ASSUMPTIONS, WESTERN_US_STATES

st.set_page_config(page_title="Settings", page_icon="⚙️", layout="wide")
st.title("⚙️ Settings")
st.caption("Configure underwriting defaults, email notifications, and automated scraping.")

settings = load_settings()

with st.form("settings_form"):
    # ── Underwriting Defaults ─────────────────────────────────────────────
    st.subheader("📐 Underwriting Defaults")
    st.markdown("**Financing (7/1 IO ARM)**")
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

    st.markdown("**Income**")
    col1, col2, col3 = st.columns(3)
    vacancy_rate = col1.number_input("Vacancy Rate", 0.0, 0.50, settings["vacancy_rate"],
                                      step=0.01, format="%.2f")
    other_income = col2.number_input("Other Income / Unit / Month ($)",
                                      value=settings["other_income_per_unit_monthly"], step=10.0)
    rent_growth = col3.number_input("Rent Growth (Annual)", 0.0, 0.15,
                                     settings["rent_growth_annual"], step=0.005, format="%.3f")

    st.markdown("**Operating Expenses**")
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

    st.markdown("**Exit**")
    exit_cap_spread = st.number_input("Exit Cap Spread (vs. going-in)", -0.02, 0.05,
                                       settings["exit_cap_spread"], step=0.0025, format="%.4f")

    st.markdown("---")

    # ── Email Configuration ───────────────────────────────────────────────
    st.subheader("📧 Email Notifications")
    st.caption("Configure SMTP credentials to enable deal report emails and automated alerts.")

    em1, em2 = st.columns(2)
    report_email_to = em1.text_input(
        "Report Recipient Email",
        value=settings.get("report_email_to", ""),
        placeholder="you@example.com",
        help="Who receives manual 'Email This Deal' reports from the pipeline and underwrite pages.",
    )
    alert_email_to = em2.text_input(
        "Alert Recipient Email",
        value=settings.get("alert_email_to", ""),
        placeholder="you@example.com",
        help="Who receives automatic alerts when a scraped deal scores above the threshold.",
    )

    em3, em4 = st.columns(2)
    alert_threshold = em3.number_input(
        "Alert Score Threshold (0–10)",
        min_value=0.0, max_value=10.0,
        value=float(settings.get("alert_score_threshold", 7.0)),
        step=0.5, format="%.1f",
        help="Deals scoring at or above this value trigger an automatic email alert.",
    )
    digest_email_to = em4.text_input(
        "Daily Digest Recipient",
        value=settings.get("digest_email_to", ""),
        placeholder="you@example.com",
        help="Optional: receives a daily summary of top deals found in the automated scrape.",
    )

    st.info(
        "SMTP credentials (EMAIL_FROM, EMAIL_PASSWORD, SMTP_HOST, SMTP_PORT) are set via environment "
        "variables or your .env file — not stored here for security. See .env.example."
    )

    st.markdown("---")

    # ── Scheduler / Auto-Scrape ───────────────────────────────────────────
    st.subheader("🤖 Automated Scraping")
    st.caption("Runs a daily background scrape, underwrites all deals, and sends alerts.")

    sch1, sch2 = st.columns(2)
    auto_scrape_enabled = sch1.checkbox(
        "Enable Automated Daily Scrape",
        value=bool(settings.get("auto_scrape_enabled", False)),
    )
    auto_scrape_time = sch2.text_input(
        "Scrape Time (HH:MM, 24h)",
        value=settings.get("auto_scrape_time", "06:00"),
        help="Time of day to run the automated scrape (server local time).",
    )

    auto_scrape_source = st.selectbox(
        "Auto-Scrape Data Source",
        ["mock", "crexi", "zillow", "both"],
        index=["mock", "crexi", "zillow", "both"].index(
            settings.get("auto_scrape_source", "mock")
        ),
        format_func=lambda x: {
            "mock": "Mock Data (safe for testing)",
            "crexi": "Crexi (live)",
            "zillow": "Zillow (live)",
            "both": "Crexi + Zillow (live)",
        }[x],
    )

    auto_scrape_states = st.multiselect(
        "States to Auto-Scrape",
        WESTERN_US_STATES,
        default=settings.get("auto_scrape_states", ["CA", "OR", "WA", "AZ", "CO"]),
    )

    st.markdown("---")

    col_a, col_b = st.columns(2)
    save = col_a.form_submit_button("💾 Save Settings", type="primary", use_container_width=True)
    reset = col_b.form_submit_button("🔄 Reset to Defaults", use_container_width=True)

if save:
    new_settings = {
        # UW defaults
        "ltv": ltv, "interest_rate": rate, "io_years": int(io_years),
        "hold_years": int(hold_years), "closing_cost_pct": closing_cost_pct,
        "vacancy_rate": vacancy_rate, "other_income_per_unit_monthly": other_income,
        "rent_growth_annual": rent_growth, "tax_rate_of_value": tax_rate,
        "insurance_per_unit": insurance_pu, "utilities_per_unit_monthly": utilities_pu,
        "maintenance_per_unit": maintenance_pu, "mgmt_pct_of_egi": mgmt_pct,
        "capex_reserve_per_unit": capex_pu, "admin_per_unit": admin_pu,
        "expense_growth_annual": expense_growth, "exit_cap_spread": exit_cap_spread,
        "transaction_cost_pct": closing_cost_pct,
        # Email
        "report_email_to": report_email_to,
        "alert_email_to": alert_email_to,
        "alert_score_threshold": alert_threshold,
        "digest_email_to": digest_email_to,
        # Scheduler
        "auto_scrape_enabled": auto_scrape_enabled,
        "auto_scrape_time": auto_scrape_time,
        "auto_scrape_source": auto_scrape_source,
        "auto_scrape_states": auto_scrape_states,
    }
    save_settings(new_settings)
    st.success("Settings saved!")

if reset:
    save_settings(DEFAULT_ASSUMPTIONS)
    st.success("Reset underwriting defaults. Email/scheduler settings preserved.")
    st.rerun()

# ── Email Connection Test ─────────────────────────────────────────────────
st.markdown("---")
st.subheader("🔌 Email Connection Test")
if st.button("Test SMTP Connection", use_container_width=False):
    try:
        from notifications.email_client import EmailClient
        client = EmailClient()
        if not client.configured:
            st.warning("EMAIL_FROM and EMAIL_PASSWORD env vars are not set. Cannot test.")
        else:
            ok, msg = client.test_connection()
            if ok:
                st.success(f"SMTP connection successful: {msg}")
            else:
                st.error(f"SMTP connection failed: {msg}")
    except Exception as e:
        st.error(f"Error: {e}")

# ── Current Settings View ─────────────────────────────────────────────────
with st.expander("📋 Current Effective Settings"):
    import json
    current = load_settings()
    st.code(json.dumps(current, indent=2))
