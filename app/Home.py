"""Deal Pipeline — scrape listings, underwrite, rank by score."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
import pandas as pd
from datetime import datetime

from config import WESTERN_US_STATES, load_settings
from models.database import init_db, get_session, upsert_deal, Deal
from models.property import Property
from underwriting.engine import underwrite
from underwriting.assumptions import get_default_assumptions
from underwriting.scoring import score_deal

st.set_page_config(
    page_title="Multifamily Deal Analyzer",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded",
)

init_db()

# ── Start background scheduler (if enabled) ─────────────────────────────────
try:
    import scheduler as sched_module
    if sched_module.get_scheduler() is None:
        sched_module.start_scheduler()
except Exception:
    pass


def run_scraper(source, states, min_units, max_units, max_price, max_results) -> list[Property]:
    props = []
    if source in ("mock", "crexi_mock"):
        from scrapers.mock import MockScraper
        return list(MockScraper().fetch(states, min_units, max_units, max_price, max_results))

    if source in ("crexi", "both"):
        try:
            from scrapers.crexi import CrexiScraper
            props += list(CrexiScraper().fetch(states, min_units, max_units, max_price,
                          max_results // 2 if source == "both" else max_results))
        except Exception as e:
            st.warning(f"Crexi error: {e}. Falling back to mock.")
            from scrapers.mock import MockScraper
            props += list(MockScraper().fetch(states, min_units, max_units, max_price, 10))

    if source in ("zillow", "both"):
        try:
            from scrapers.zillow import ZillowScraper
            props += list(ZillowScraper().fetch(states, min_units, max_units, max_price,
                          max_results // 2 if source == "both" else max_results))
        except Exception as e:
            st.warning(f"Zillow error: {e}.")

    return props


def props_to_df(props: list[Property], assumptions) -> pd.DataFrame:
    rows = []
    for p in props:
        try:
            r = underwrite(p, assumptions)
            score = score_deal(r, p)
            rows.append({
                "Score": score,
                "Address": p.address,
                "City": p.city,
                "State": p.state,
                "Units": p.units,
                "Price": p.purchase_price,
                "Price/Unit": r.price_per_unit,
                "Rent/Unit/Mo": (p.monthly_rent_total / p.units) if p.monthly_rent_total else None,
                "Cap Rate": r.going_in_cap_rate,
                "NOI": r.noi,
                "CoC Y1": r.coc_y1,
                "DSCR": r.dscr_y1,
                "Debt Yield": r.debt_yield,
                "5yr IRR": r.irr_5yr,
                "10yr IRR": r.irr_10yr,
                "Breakeven Occ": r.breakeven_occupancy,
                "Source": p.source,
                "URL": p.listing_url,
                "_prop": p,
                "_results": r,
            })
        except Exception:
            pass
    return pd.DataFrame(rows)


# ── Sidebar ──────────────────────────────────────────────────────────────────
st.sidebar.title("🏢 Multifamily UW")
st.sidebar.markdown("---")

with st.sidebar.expander("🔍 Search Filters", expanded=True):
    selected_states = st.multiselect(
        "States", WESTERN_US_STATES,
        default=["CA", "OR", "WA", "AZ", "CO", "NV"],
    )
    min_units, max_units = st.slider("Unit Count", 3, 10, (3, 10))
    max_price = st.number_input("Max Price ($)", value=2_000_000, step=100_000, format="%d")
    source = st.selectbox(
        "Data Source",
        ["mock", "both", "crexi", "zillow"],
        format_func=lambda x: {
            "mock": "Mock Data (instant)",
            "both": "Crexi + Zillow (live)",
            "crexi": "Crexi (live)",
            "zillow": "Zillow (live)",
        }[x],
    )
    max_results = st.slider("Max Listings", 10, 100, 25, step=5)

try:
    import scheduler as sched_module
    state = sched_module.get_state()
    if state.get("last_run"):
        st.sidebar.caption(f"Last auto-scrape: {state['last_run'][:16]}")
except Exception:
    pass

# ── Main ─────────────────────────────────────────────────────────────────────
st.title("🏢 Multifamily Deal Pipeline")
st.caption(f"Western US | 3–10 Units | ≤${max_price:,.0f} | Source: {source.upper()}")

assumptions = get_default_assumptions()

if "pipeline_df" not in st.session_state:
    st.session_state.pipeline_df = None

col1, col2, col3 = st.columns([2, 1, 1])
with col1:
    if st.button("🔄 Run Scraper & Underwrite All", type="primary", use_container_width=True):
        with st.spinner(f"Scraping {source.upper()} listings..."):
            props = run_scraper(source, selected_states, min_units, max_units, max_price, max_results)
        if not props:
            st.warning("No listings found. Try different filters or mock data.")
        else:
            with st.spinner(f"Underwriting {len(props)} properties..."):
                df = props_to_df(props, assumptions)
            st.session_state.pipeline_df = df
            st.success(f"Found and underwrote {len(df)} properties.")

with col2:
    if st.button("🗑️ Clear Results", use_container_width=True):
        st.session_state.pipeline_df = None

df = st.session_state.pipeline_df

if df is not None and not df.empty:
    st.markdown("---")

    sort_col = st.selectbox("Sort by", ["Score", "Cap Rate", "CoC Y1", "5yr IRR", "DSCR", "Price/Unit"], index=0)
    df_sorted = df.sort_values(sort_col, ascending=False).reset_index(drop=True)

    # ── KPI summary ──────────────────────────────────────────────────────────
    st.subheader(f"📊 {len(df_sorted)} Properties Found")
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Avg Score", f"{df['Score'].mean():.1f}/10")
    k2.metric("Avg Cap Rate", f"{df['Cap Rate'].mean():.1%}")
    k3.metric("Avg CoC Y1", f"{df['CoC Y1'].mean():.1%}")
    k4.metric("Avg DSCR", f"{df['DSCR'].mean():.2f}x")
    k5.metric("Avg 5yr IRR", f"{df['5yr IRR'].mean():.1%}" if df["5yr IRR"].notna().any() else "—")

    # ── Charts ───────────────────────────────────────────────────────────────
    with st.expander("📈 Charts", expanded=False):
        try:
            import altair as alt
            ch1, ch2 = st.columns(2)
            with ch1:
                cap_chart = alt.Chart(df_sorted).mark_bar().encode(
                    x=alt.X("Cap Rate:Q", bin=alt.Bin(maxbins=10), title="Cap Rate"),
                    y="count()",
                    color=alt.value("#1F3864"),
                ).properties(title="Cap Rate Distribution", height=200)
                st.altair_chart(cap_chart, use_container_width=True)
            with ch2:
                scatter = alt.Chart(df_sorted.dropna(subset=["5yr IRR"])).mark_circle(size=60).encode(
                    x=alt.X("Price:Q", title="Price ($)"),
                    y=alt.Y("5yr IRR:Q", title="5yr IRR"),
                    color=alt.Color("Score:Q", scale=alt.Scale(scheme="redyellowgreen")),
                    tooltip=["Address", "City", "State", "Score", "Cap Rate", "5yr IRR"],
                ).properties(title="Price vs 5yr IRR", height=200)
                st.altair_chart(scatter, use_container_width=True)
        except ImportError:
            st.info("Install altair for charts: pip install altair")

    st.markdown("---")

    # ── Display table ────────────────────────────────────────────────────────
    display_cols = ["Score", "Address", "City", "State", "Units", "Price", "Price/Unit",
                    "Cap Rate", "CoC Y1", "DSCR", "5yr IRR", "Source"]
    display_df = df_sorted[display_cols].copy()
    display_df["Price"] = display_df["Price"].apply(lambda x: f"${x:,.0f}" if pd.notna(x) else "—")
    display_df["Price/Unit"] = display_df["Price/Unit"].apply(lambda x: f"${x:,.0f}" if pd.notna(x) else "—")
    display_df["Cap Rate"] = display_df["Cap Rate"].apply(lambda x: f"{x:.1%}" if pd.notna(x) else "—")
    display_df["CoC Y1"] = display_df["CoC Y1"].apply(lambda x: f"{x:.1%}" if pd.notna(x) else "—")
    display_df["DSCR"] = display_df["DSCR"].apply(lambda x: f"{x:.2f}x" if pd.notna(x) else "—")
    display_df["5yr IRR"] = display_df["5yr IRR"].apply(lambda x: f"{x:.1%}" if pd.notna(x) else "—")

    event = st.dataframe(
        display_df,
        use_container_width=True,
        height=400,
        on_select="rerun",
        selection_mode="single-row",
    )

    selected_rows = event.selection.rows if hasattr(event, "selection") else []
    if selected_rows:
        idx = selected_rows[0]
        selected = df_sorted.iloc[idx]
        prop: Property = selected["_prop"]
        results = selected["_results"]
        score_val = float(selected["Score"])

        st.markdown("---")
        st.subheader(f"📋 Quick View: {prop.address}, {prop.city}, {prop.state}")

        score_color = "#22c55e" if score_val >= 7.5 else "#f59e0b" if score_val >= 5.0 else "#ef4444"
        st.markdown(
            f'<span style="background:{score_color};color:white;padding:4px 12px;'
            f'border-radius:6px;font-size:18px;font-weight:bold">Score: {score_val:.1f}/10</span>',
            unsafe_allow_html=True,
        )
        st.write("")

        col_a, col_b, col_c, col_d, col_e = st.columns(5)
        col_a.metric("Cap Rate", f"{results.going_in_cap_rate:.1%}")
        col_b.metric("CoC Year 1", f"{results.coc_y1:.1%}")
        col_c.metric("DSCR Year 1", f"{results.dscr_y1:.2f}x")
        col_d.metric("5yr IRR", f"{results.irr_5yr:.1%}" if results.irr_5yr else "—")
        col_e.metric("Debt Yield", f"{results.debt_yield:.1%}" if results.debt_yield else "—")

        c1, c2, c3 = st.columns(3)
        with c1:
            if st.button("📊 Full Underwrite This Deal", type="primary", use_container_width=True):
                st.session_state.selected_prop = prop
                st.session_state.selected_results = results
                st.switch_page("pages/2_Underwrite.py")

        with c2:
            if st.button("💾 Save to Pipeline", use_container_width=True):
                session = get_session()
                upsert_deal(session, {
                    "address": prop.address, "city": prop.city, "state": prop.state,
                    "zip_code": prop.zip_code, "units": prop.units,
                    "year_built": prop.year_built, "sqft": prop.sqft,
                    "purchase_price": prop.purchase_price, "asking_price": prop.asking_price,
                    "monthly_rent_total": prop.monthly_rent_total,
                    "listing_url": prop.listing_url, "source": prop.source,
                    "scraped_at": prop.scraped_at, "status": "pipeline",
                    "gpr": results.gpr, "egi": results.egi,
                    "total_opex": results.total_opex, "noi": results.noi,
                    "going_in_cap_rate": results.going_in_cap_rate,
                    "loan_amount": results.loan_amount, "equity_invested": results.equity_invested,
                    "annual_ds": results.annual_ds_io, "net_cash_flow_y1": results.net_cash_flow_y1,
                    "coc_y1": results.coc_y1, "dscr_y1": results.dscr_y1,
                    "price_per_unit": results.price_per_unit,
                    "irr_5yr": results.irr_5yr, "irr_10yr": results.irr_10yr,
                    "equity_multiple_5yr": results.equity_multiple_5yr,
                    "equity_multiple_10yr": results.equity_multiple_10yr,
                    "vacancy_rate": assumptions.vacancy_rate,
                    "uw_assumptions_json": assumptions.model_dump(),
                    "ai_score": score_val,
                })
                session.close()
                st.success("Saved to pipeline!")

        with c3:
            settings = load_settings()
            email_to = settings.get("report_email_to", "")
            if email_to:
                if st.button("📧 Email This Deal", use_container_width=True):
                    try:
                        from notifications.email_client import EmailClient
                        from models.analysis import DealAnalysis, grade_from_score, recommendation_from_score
                        analysis = DealAnalysis(
                            score=score_val,
                            grade=grade_from_score(score_val),
                            recommendation=recommendation_from_score(score_val),
                            memo="",
                        )
                        EmailClient().send_deal_report(email_to, prop, results, analysis)
                        st.success(f"Sent to {email_to}")
                    except Exception as e:
                        st.error(f"Email failed: {e}")

else:
    st.info("👆 Click **Run Scraper & Underwrite All** to fetch listings, or paste one manually below.")
    st.markdown("---")
    st.subheader("📋 Paste a Listing Manually")
    st.caption("Found a deal on Crexi, Zillow, Redfin, or LoopNet? Enter the details and underwrite instantly.")

    with st.form("manual_entry"):
        col1, col2, col3 = st.columns(3)
        m_address = col1.text_input("Address", placeholder="123 Main St")
        m_city = col2.text_input("City", placeholder="Phoenix")
        m_state = col3.text_input("State", placeholder="AZ", max_chars=2)
        col4, col5, col6 = st.columns(3)
        m_units = col4.number_input("Units", min_value=1, max_value=50, value=4)
        m_price = col5.number_input("Asking Price ($)", min_value=50_000, max_value=10_000_000,
                                     value=900_000, step=25_000)
        m_rent = col6.number_input("Monthly Rent Total ($, 0 if unknown)", min_value=0,
                                    max_value=100_000, value=0, step=100)
        col7, col8 = st.columns(2)
        m_year = col7.number_input("Year Built", min_value=1900, max_value=2024, value=1985)
        m_url = col8.text_input("Listing URL (optional)")
        submitted = st.form_submit_button("⚡ Underwrite This Deal", type="primary", use_container_width=True)

    if submitted and m_address:
        manual_prop = Property(
            address=m_address, city=m_city, state=m_state.upper() or "CA",
            units=int(m_units), purchase_price=float(m_price),
            monthly_rent_total=float(m_rent) if m_rent else None,
            year_built=int(m_year), listing_url=m_url or "", source="manual",
            scraped_at=datetime.utcnow(),
        )
        st.session_state.selected_prop = manual_prop
        st.switch_page("pages/2_Underwrite.py")

    st.markdown("---")
    st.markdown("""
**How the scraper works:**
1. Select your target states and filters in the sidebar
2. Click Run Scraper — it opens a real browser to pull live listings
3. Every listing is automatically underwritten using institutional PE assumptions
4. Deals are scored 0–10 across cap rate, DSCR, IRR, CoC, and price/unit
5. Click any row to deep-dive, run AI analysis, generate Excel, or save to your tracker

**Default financing:** 7/1 IO ARM · 5.75% · 75% LTV (Ascent US Bank terms)

> **Note:** Crexi and Zillow occasionally block automated browsers. If the scraper returns 0 results,
> use Mock Data to test the tool, or paste listings manually using the form above.
    """)
