"""Deal Tracker — view and manage all underwritten deals."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st
import pandas as pd
from datetime import datetime

from models.database import get_session, Deal, init_db

st.set_page_config(page_title="Deal Tracker", page_icon="📁", layout="wide")
st.title("📁 Deal Tracker")
st.caption("All underwritten deals — track decisions and performance")

init_db()


def load_deals(filters: dict) -> pd.DataFrame:
    session = get_session()
    q = session.query(Deal)

    if filters.get("states"):
        q = q.filter(Deal.state.in_(filters["states"]))
    if filters.get("status"):
        q = q.filter(Deal.status.in_(filters["status"]))
    if filters.get("decision"):
        q = q.filter(Deal.decision.in_(filters["decision"]))

    deals = q.order_by(Deal.underwritten_at.desc().nullslast()).all()
    session.close()

    if not deals:
        return pd.DataFrame()

    rows = [d.to_dict() for d in deals]
    return pd.DataFrame(rows)


# ── Sidebar filters ───────────────────────────────────────────────────────
with st.sidebar.expander("🔍 Filters", expanded=True):
    from config import WESTERN_US_STATES
    filter_states = st.multiselect("State", WESTERN_US_STATES)
    filter_status = st.multiselect("Status", ["pipeline", "underwritten", "pursuing", "pass", "closed"])
    filter_decision = st.multiselect("Decision", ["buy", "pass", "watch"])

filters = {
    "states": filter_states or None,
    "status": filter_status or None,
    "decision": filter_decision or None,
}

df = load_deals(filters)

if df.empty:
    st.info("No deals in tracker yet. Run the scraper and underwrite some properties first!")
else:
    # ── Summary KPIs ────────────────────────────────────────────────────
    total = len(df)
    pursuing = (df["status"] == "pursuing").sum()
    passed = (df["decision"] == "pass").sum()
    watching = (df["decision"] == "watch").sum()

    k1, k2, k3, k4, k5, k6 = st.columns(6)
    k1.metric("Total Deals", total)
    k2.metric("Pursuing", pursuing)
    k3.metric("Passed", passed)
    k4.metric("Watching", watching)
    avg_coc = df["coc_y1"].dropna().mean()
    avg_irr = df["irr_5yr"].dropna().mean()
    k5.metric("Avg CoC Y1", f"{avg_coc:.1%}" if not pd.isna(avg_coc) else "—")
    k6.metric("Avg 5yr IRR", f"{avg_irr:.1%}" if not pd.isna(avg_irr) else "—")

    st.markdown("---")

    # ── Deal table ───────────────────────────────────────────────────────
    display_cols = {
        "address": "Address", "city": "City", "state": "State", "units": "Units",
        "purchase_price": "Price", "going_in_cap_rate": "Cap Rate",
        "coc_y1": "CoC Y1", "dscr_y1": "DSCR", "irr_5yr": "5yr IRR",
        "irr_10yr": "10yr IRR", "equity_multiple_5yr": "EM 5yr",
        "status": "Status", "decision": "Decision", "underwritten_at": "Underwritten",
    }
    show_df = df[[c for c in display_cols.keys() if c in df.columns]].copy()
    show_df = show_df.rename(columns=display_cols)

    if "Price" in show_df:
        show_df["Price"] = show_df["Price"].apply(lambda x: f"${x:,.0f}" if pd.notna(x) else "—")
    if "Cap Rate" in show_df:
        show_df["Cap Rate"] = show_df["Cap Rate"].apply(lambda x: f"{x:.1%}" if pd.notna(x) else "—")
    if "CoC Y1" in show_df:
        show_df["CoC Y1"] = show_df["CoC Y1"].apply(lambda x: f"{x:.1%}" if pd.notna(x) else "—")
    if "DSCR" in show_df:
        show_df["DSCR"] = show_df["DSCR"].apply(lambda x: f"{x:.2f}x" if pd.notna(x) else "—")
    if "5yr IRR" in show_df:
        show_df["5yr IRR"] = show_df["5yr IRR"].apply(lambda x: f"{x:.1%}" if pd.notna(x) else "—")
    if "10yr IRR" in show_df:
        show_df["10yr IRR"] = show_df["10yr IRR"].apply(lambda x: f"{x:.1%}" if pd.notna(x) else "—")
    if "EM 5yr" in show_df:
        show_df["EM 5yr"] = show_df["EM 5yr"].apply(lambda x: f"{x:.2f}x" if pd.notna(x) else "—")
    if "Underwritten" in show_df:
        show_df["Underwritten"] = pd.to_datetime(show_df["Underwritten"]).dt.strftime("%Y-%m-%d")

    event = st.dataframe(
        show_df,
        use_container_width=True,
        height=500,
        on_select="rerun",
        selection_mode="single-row",
    )

    selected_rows = event.selection.rows if hasattr(event, "selection") else []
    if selected_rows:
        idx = selected_rows[0]
        row = df.iloc[idx]

        st.markdown("---")
        st.subheader(f"📋 {row.get('address', '')}, {row.get('city', '')}, {row.get('state', '')}")

        with st.expander("📝 Notes & Decision", expanded=True):
            col1, col2, col3 = st.columns(3)
            col1.markdown(f"**Status:** `{row.get('status', '—')}`")
            col2.markdown(f"**Decision:** `{row.get('decision', '—')}`")
            col3.markdown(f"**Source:** `{row.get('source', '—')}`")

            pass_reason = row.get("pass_reason")
            if pass_reason:
                st.markdown(f"**Pass Reason:** {pass_reason}")

            notes = row.get("notes")
            if notes:
                st.markdown(f"**Notes:**\n{notes}")

        with st.expander("💰 Underwriting Detail"):
            detail_cols = {
                "NOI": f"${row.get('noi', 0):,.0f}" if pd.notna(row.get("noi")) else "—",
                "Cap Rate": f"{row.get('going_in_cap_rate', 0):.1%}" if pd.notna(row.get("going_in_cap_rate")) else "—",
                "DSCR": f"{row.get('dscr_y1', 0):.2f}x" if pd.notna(row.get("dscr_y1")) else "—",
                "Loan": f"${row.get('loan_amount', 0):,.0f}" if pd.notna(row.get("loan_amount")) else "—",
                "Equity": f"${row.get('equity_invested', 0):,.0f}" if pd.notna(row.get("equity_invested")) else "—",
                "NCF Y1": f"${row.get('net_cash_flow_y1', 0):,.0f}" if pd.notna(row.get("net_cash_flow_y1")) else "—",
                "5yr IRR": f"{row.get('irr_5yr', 0):.1%}" if pd.notna(row.get("irr_5yr")) else "—",
                "10yr IRR": f"{row.get('irr_10yr', 0):.1%}" if pd.notna(row.get("irr_10yr")) else "—",
                "EM 5yr": f"{row.get('equity_multiple_5yr', 0):.2f}x" if pd.notna(row.get("equity_multiple_5yr")) else "—",
                "EM 10yr": f"{row.get('equity_multiple_10yr', 0):.2f}x" if pd.notna(row.get("equity_multiple_10yr")) else "—",
            }
            det_df = pd.DataFrame({"Metric": detail_cols.keys(), "Value": detail_cols.values()})
            st.dataframe(det_df, use_container_width=True, hide_index=True)

        # Update status/decision inline
        with st.expander("✏️ Update Decision"):
            new_status = st.selectbox("Status", ["pipeline", "underwritten", "pursuing", "pass", "closed"],
                                       index=["pipeline", "underwritten", "pursuing", "pass", "closed"].index(
                                           row.get("status", "pipeline")))
            new_decision = st.radio("Decision", ["buy", "pass", "watch"], horizontal=True,
                                     index=["buy", "pass", "watch"].index(row.get("decision") or "watch"))
            new_notes = st.text_area("Notes", value=row.get("notes") or "")
            new_pass_reason = st.text_input("Pass Reason", value=row.get("pass_reason") or "")

            if st.button("💾 Update", use_container_width=True):
                session = get_session()
                deal = session.query(Deal).filter_by(id=int(row["id"])).first()
                if deal:
                    deal.status = new_status
                    deal.decision = new_decision
                    deal.notes = new_notes or None
                    deal.pass_reason = new_pass_reason or None
                    session.commit()
                session.close()
                st.success("Updated!")
                st.rerun()

    # ── Export ───────────────────────────────────────────────────────────
    st.markdown("---")
    csv = df[[c for c in display_cols.keys() if c in df.columns]].to_csv(index=False)
    st.download_button(
        "⬇️ Export All Deals as CSV",
        data=csv,
        file_name=f"deal_tracker_{datetime.now().strftime('%Y%m%d')}.csv",
        mime="text/csv",
    )
