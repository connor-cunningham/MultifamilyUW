"""Deal Pipeline — scrape listings and browse candidates."""
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
from underwriting.assumptions import get_default_assumptions, assumptions_from_dict

st.set_page_config(
    page_title="Multifamily Deal Analyzer",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Initialize DB
init_db()


def run_scraper(source: str, states: list[str], min_units: int, max_units: int,
                max_price: float, max_results: int) -> list[Property]:
    props = []

    if source in ("mock", "crexi_mock"):
        from scrapers.mock import MockScraper
        scraper = MockScraper()
        for p in scraper.fetch(states, min_units, max_units, max_price, max_results):
            props.append(p)
        return props

    if source in ("crexi", "both"):
        try:
            from scrapers.crexi import CrexiScraper
            for p in CrexiScraper().fetch(states, min_units, max_units, max_price, max_results // 2 if source == "both" else max_results):
                props.append(p)
        except Exception as e:
            st.warning(f"Crexi scraper error: {e}. Falling back to mock data.")
            from scrapers.mock import MockScraper
            for p in MockScraper().fetch(states, min_units, max_units, max_price, 10):
                props.append(p)

    if source in ("zillow", "both"):
        try:
            from scrapers.zillow import ZillowScraper
            for p in ZillowScraper().fetch(states, min_units, max_units, max_price, max_results // 2 if source == "both" else max_results):
                props.append(p)
        except Exception as e:
            st.warning(f"Zillow scraper error: {e}.")

    return props


def props_to_df(props: list[Property], assumptions) -> pd.DataFrame:
    rows = []
    for p in props:
        try:
            r = underwrite(p, assumptions)
            rows.append({
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
                "5yr IRR": r.irr_5yr,
                "10yr IRR": r.irr_10yr,
                "Source": p.source,
                "URL": p.listing_url,
                "_prop": p,
                "_results": r,
            })
        except Exception:
            pass
    return pd.DataFrame(rows)


# ── Sidebar ────────────────────────────────────────────────────────────────
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
            "mock": "Mock Data (instant, no network)",
            "both": "Crexi + Zillow (live)",
            "crexi": "Crexi (live)",
            "zillow": "Zillow (live)",
        }[x],
    )
    max_results = st.slider("Max Listings", 10, 100, 25, step=5)

# ── Main ────────────────────────────────────────────────────────────────────
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

    # Sort + rank
    sort_col = st.selectbox("Sort by", ["Cap Rate", "CoC Y1", "5yr IRR", "DSCR", "Price/Unit"], index=0)
    df_sorted = df.sort_values(sort_col, ascending=False).reset_index(drop=True)

    display_cols = ["Address", "City", "State", "Units", "Price", "Price/Unit",
                    "Rent/Unit/Mo", "Cap Rate", "CoC Y1", "DSCR", "5yr IRR", "Source"]
    display_df = df_sorted[display_cols].copy()

    # Format
    display_df["Price"] = display_df["Price"].apply(lambda x: f"${x:,.0f}" if pd.notna(x) else "—")
    display_df["Price/Unit"] = display_df["Price/Unit"].apply(lambda x: f"${x:,.0f}" if pd.notna(x) else "—")
    display_df["Rent/Unit/Mo"] = display_df["Rent/Unit/Mo"].apply(lambda x: f"${x:,.0f}" if pd.notna(x) else "—")
    display_df["Cap Rate"] = display_df["Cap Rate"].apply(lambda x: f"{x:.1%}" if pd.notna(x) else "—")
    display_df["CoC Y1"] = display_df["CoC Y1"].apply(lambda x: f"{x:.1%}" if pd.notna(x) else "—")
    display_df["DSCR"] = display_df["DSCR"].apply(lambda x: f"{x:.2f}x" if pd.notna(x) else "—")
    display_df["5yr IRR"] = display_df["5yr IRR"].apply(lambda x: f"{x:.1%}" if pd.notna(x) else "—")

    # Summary KPIs
    st.subheader(f"📊 {len(df_sorted)} Properties Found")
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Avg Cap Rate", f"{df['Cap Rate'].mean():.1%}")
    k2.metric("Avg CoC Y1", f"{df['CoC Y1'].mean():.1%}")
    k3.metric("Avg DSCR", f"{df['DSCR'].mean():.2f}x")
    k4.metric("Avg 5yr IRR", f"{df['5yr IRR'].mean():.1%}" if df["5yr IRR"].notna().any() else "—")

    st.markdown("---")

    # Table with row selection
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

        st.markdown("---")
        st.subheader(f"📋 Quick View: {prop.address}, {prop.city}, {prop.state}")

        col_a, col_b, col_c, col_d = st.columns(4)
        col_a.metric("Cap Rate", f"{results.going_in_cap_rate:.1%}")
        col_b.metric("CoC Year 1", f"{results.coc_y1:.1%}")
        col_c.metric("DSCR Year 1", f"{results.dscr_y1:.2f}x")
        col_d.metric("5yr IRR", f"{results.irr_5yr:.1%}" if results.irr_5yr else "—")

        c1, c2 = st.columns(2)
        with c1:
            if st.button("📊 Full Underwrite This Deal", type="primary", use_container_width=True):
                st.session_state.selected_prop = prop
                st.session_state.selected_results = results
                st.switch_page("pages/2_Underwrite.py")

        with c2:
            # Quick save to DB
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
                })
                session.close()
                st.success("Saved to pipeline!")

else:
    st.info("👆 Click **Run Scraper & Underwrite All** to fetch and analyze listings.")
    st.markdown("""
    **How it works:**
    1. Select your target states and filters in the sidebar
    2. Click Run Scraper to pull active listings
    3. Every listing is automatically underwritten using institutional PE assumptions
    4. Click any row to deep-dive, generate Excel, or save to your deal tracker

    **Default financing:** 7/1 IO ARM · 5.75% · 75% LTV (Ascent US Bank terms)
    """)
