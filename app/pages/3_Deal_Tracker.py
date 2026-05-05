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


def _grade_from_score(score) -> str:
    if score is None or pd.isna(score):
        return "—"
    if score >= 8.0:
        return "A"
    if score >= 6.0:
        return "B"
    if score >= 4.0:
        return "C"
    if score >= 2.0:
        return "D"
    return "F"


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
    filter_grades = st.multiselect("AI Grade", ["A", "B", "C", "D", "F"])

filters = {
    "states": filter_states or None,
    "status": filter_status or None,
    "decision": filter_decision or None,
}

df = load_deals(filters)

if df.empty:
    st.info("No deals in tracker yet. Run the scraper and underwrite some properties first!")
else:
    # Apply grade filter client-side (derived field)
    if "ai_score" in df.columns:
        df["_grade"] = df["ai_score"].apply(_grade_from_score)
    else:
        df["_grade"] = "—"

    if filter_grades:
        df = df[df["_grade"].isin(filter_grades)]
        if df.empty:
            st.info("No deals match the selected grade filter.")
            st.stop()

    # ── Summary KPIs ────────────────────────────────────────────────────
    total = len(df)
    pursuing = (df["status"] == "pursuing").sum() if "status" in df else 0
    passed = (df["decision"] == "pass").sum() if "decision" in df else 0
    watching = (df["decision"] == "watch").sum() if "decision" in df else 0

    k1, k2, k3, k4, k5, k6, k7 = st.columns(7)
    k1.metric("Total Deals", total)
    k2.metric("Pursuing", int(pursuing))
    k3.metric("Passed", int(passed))
    k4.metric("Watching", int(watching))
    avg_score = df["ai_score"].dropna().mean() if "ai_score" in df else None
    avg_coc = df["coc_y1"].dropna().mean() if "coc_y1" in df else None
    avg_irr = df["irr_5yr"].dropna().mean() if "irr_5yr" in df else None
    k5.metric("Avg Score", f"{avg_score:.1f}/10" if avg_score and not pd.isna(avg_score) else "—")
    k6.metric("Avg CoC Y1", f"{avg_coc:.1%}" if avg_coc and not pd.isna(avg_coc) else "—")
    k7.metric("Avg 5yr IRR", f"{avg_irr:.1%}" if avg_irr and not pd.isna(avg_irr) else "—")

    # ── Deal Funnel Chart ─────────────────────────────────────────────────
    with st.expander("📊 Deal Funnel & Charts", expanded=False):
        try:
            import altair as alt

            ch1, ch2 = st.columns(2)

            with ch1:
                st.markdown("**Deal Funnel by Status**")
                if "status" in df:
                    funnel_counts = df["status"].value_counts().reset_index()
                    funnel_counts.columns = ["Status", "Count"]
                    status_order = ["pipeline", "underwritten", "pursuing", "pass", "closed"]
                    funnel_counts["Status"] = pd.Categorical(funnel_counts["Status"],
                                                              categories=status_order, ordered=True)
                    funnel_counts = funnel_counts.sort_values("Status")
                    funnel_chart = alt.Chart(funnel_counts).mark_bar().encode(
                        x=alt.X("Count:Q"),
                        y=alt.Y("Status:N", sort=status_order),
                        color=alt.Color("Status:N", scale=alt.Scale(
                            domain=status_order,
                            range=["#94a3b8", "#60a5fa", "#22c55e", "#ef4444", "#a855f7"]
                        ), legend=None),
                        tooltip=["Status", "Count"],
                    ).properties(height=200)
                    st.altair_chart(funnel_chart, use_container_width=True)

            with ch2:
                st.markdown("**Score Distribution**")
                if "ai_score" in df and df["ai_score"].notna().any():
                    score_df = df[df["ai_score"].notna()].copy()
                    score_chart = alt.Chart(score_df).mark_bar().encode(
                        x=alt.X("ai_score:Q", bin=alt.Bin(step=1.0), title="AI Score"),
                        y="count()",
                        color=alt.condition(
                            alt.datum.ai_score >= 7.5,
                            alt.value("#22c55e"),
                            alt.condition(
                                alt.datum.ai_score >= 5.0,
                                alt.value("#f59e0b"),
                                alt.value("#ef4444")
                            )
                        ),
                        tooltip=["count()"],
                    ).properties(title="Score Distribution", height=200)
                    st.altair_chart(score_chart, use_container_width=True)

        except ImportError:
            st.info("Install altair for charts: pip install altair")

    st.markdown("---")

    # ── Deal table ───────────────────────────────────────────────────────
    display_cols = {
        "ai_score": "Score", "address": "Address", "city": "City", "state": "State",
        "units": "Units", "purchase_price": "Price", "going_in_cap_rate": "Cap Rate",
        "coc_y1": "CoC Y1", "dscr_y1": "DSCR", "irr_5yr": "5yr IRR",
        "equity_multiple_5yr": "EM 5yr", "status": "Status", "decision": "Decision",
        "underwritten_at": "Underwritten",
    }
    available = [c for c in display_cols.keys() if c in df.columns]
    show_df = df[available].copy()
    show_df = show_df.rename(columns=display_cols)

    if "Score" in show_df:
        show_df["Score"] = show_df["Score"].apply(
            lambda x: f"{x:.1f}" if pd.notna(x) else "—"
        )
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

        # Score badge
        score_val = row.get("ai_score")
        if score_val and not pd.isna(score_val):
            score_val = float(score_val)
            sc_color = "#22c55e" if score_val >= 7.5 else "#f59e0b" if score_val >= 5.0 else "#ef4444"
            grade_str = _grade_from_score(score_val)
            st.markdown(
                f'<span style="background:{sc_color};color:white;padding:3px 12px;'
                f'border-radius:5px;font-weight:bold">Score: {score_val:.1f}/10 &nbsp;|&nbsp; Grade: {grade_str}</span>',
                unsafe_allow_html=True,
            )
            st.write("")

        # AI memo if available
        ai_memo = row.get("ai_memo")
        if ai_memo:
            st.markdown(f"**AI Memo:** {ai_memo}")

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
    export_cols = [c for c in display_cols.keys() if c in df.columns]
    csv = df[export_cols].to_csv(index=False)
    st.download_button(
        "⬇️ Export All Deals as CSV",
        data=csv,
        file_name=f"deal_tracker_{datetime.now().strftime('%Y%m%d')}.csv",
        mime="text/csv",
    )
