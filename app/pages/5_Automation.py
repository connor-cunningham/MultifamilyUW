"""Automation — manage the background scheduler and view scrape history."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Automation", page_icon="🤖", layout="wide")
st.title("🤖 Automation")
st.caption("Manage daily automated scraping, view run history, and trigger manual runs.")


# ── Scheduler Status ──────────────────────────────────────────────────────
st.subheader("📅 Scheduler Status")

try:
    import scheduler as sched_module
    from config import load_settings

    settings = load_settings()
    scheduler_obj = sched_module.get_scheduler()
    state = sched_module.get_state()

    enabled = settings.get("auto_scrape_enabled", False)
    scrape_time = settings.get("auto_scrape_time", "06:00")
    source = settings.get("auto_scrape_source", "mock")
    states = settings.get("auto_scrape_states", ["CA", "OR", "WA", "AZ", "CO"])

    is_running = scheduler_obj is not None and scheduler_obj.running

    s1, s2, s3, s4 = st.columns(4)
    s1.metric("Scheduler", "🟢 Running" if is_running else "🔴 Stopped")
    s2.metric("Auto-Scrape", "Enabled" if enabled else "Disabled")
    s3.metric("Scheduled Time", scrape_time)
    s4.metric("Source", source.upper())

    last_run = state.get("last_run")
    last_count = state.get("last_count", 0)
    last_qualifying = state.get("last_qualifying", 0)

    if last_run:
        r1, r2, r3 = st.columns(3)
        r1.metric("Last Run", last_run[:16].replace("T", " "))
        r2.metric("Deals Found", last_count)
        r3.metric("Qualifying Deals", last_qualifying)
    else:
        st.info("No scrape runs recorded yet.")

    if not enabled:
        st.warning(
            "Auto-scrape is disabled. Enable it in **Settings → Automated Scraping** "
            "and restart the app to activate the scheduler."
        )

except ImportError:
    st.error("APScheduler not installed. Run: `pip install apscheduler`")
except Exception as e:
    st.error(f"Scheduler error: {e}")

st.markdown("---")

# ── Manual Run ───────────────────────────────────────────────────────────
st.subheader("▶️ Manual Scrape Run")
st.caption("Trigger an immediate scrape → underwrite → score → save → alert cycle.")

try:
    from config import load_settings, WESTERN_US_STATES

    settings = load_settings()

    mc1, mc2, mc3 = st.columns(3)
    run_source = mc1.selectbox(
        "Source",
        ["mock", "crexi", "zillow", "both"],
        index=["mock", "crexi", "zillow", "both"].index(settings.get("auto_scrape_source", "mock")),
        format_func=lambda x: {"mock": "Mock", "crexi": "Crexi", "zillow": "Zillow", "both": "Both"}[x],
    )
    run_states = mc2.multiselect(
        "States",
        WESTERN_US_STATES,
        default=settings.get("auto_scrape_states", ["CA", "OR", "WA", "AZ", "CO"]),
    )
    run_max = mc3.slider("Max Listings", 10, 100, 25, step=5)

    if st.button("▶️ Run Now", type="primary"):
        with st.spinner("Running scrape pipeline..."):
            try:
                import scheduler as sched_module
                summary = sched_module.run_daily_scrape(
                    source=run_source,
                    states=run_states or None,
                    max_results=run_max,
                )
                st.success(
                    f"Done — {summary['total_found']} deals found, "
                    f"{summary['qualifying']} qualifying (score ≥ alert threshold)."
                )
            except Exception as e:
                st.error(f"Run failed: {e}")

except Exception as e:
    st.error(f"Config error: {e}")

st.markdown("---")

# ── Run History ───────────────────────────────────────────────────────────
st.subheader("📋 Recent Scrape Runs")

try:
    import scheduler as sched_module
    state = sched_module.get_state()
    runs = state.get("runs", [])

    if not runs:
        st.info("No scrape history yet.")
    else:
        history_rows = []
        for run in runs[:20]:
            history_rows.append({
                "Timestamp": run.get("timestamp", "")[:16].replace("T", " "),
                "Source": run.get("source", "—").upper(),
                "States": ", ".join(run.get("states", [])),
                "Deals Found": run.get("total_found", 0),
                "Qualifying": run.get("qualifying", 0),
            })
        st.dataframe(pd.DataFrame(history_rows), use_container_width=True, hide_index=True)

except Exception as e:
    st.error(f"Could not load run history: {e}")

st.markdown("---")

# ── Email Config Quick Check ──────────────────────────────────────────────
st.subheader("📧 Email Configuration")

try:
    from notifications.email_client import EmailClient
    client = EmailClient()

    e1, e2, e3 = st.columns(3)
    e1.metric("SMTP Host", client.smtp_host)
    e2.metric("From Address", client.from_addr or "⚠️ Not set")
    e3.metric("Alert Threshold", f"{client.alert_threshold:.1f}/10")

    if client.alert_to:
        st.caption(f"Alerts → {client.alert_to}")

    if st.button("Test Email Connection"):
        if not client.configured:
            st.warning("Set EMAIL_FROM and EMAIL_PASSWORD env vars first.")
        else:
            ok, msg = client.test_connection()
            if ok:
                st.success(f"Connection OK: {msg}")
            else:
                st.error(f"Failed: {msg}")

except Exception as e:
    st.error(f"Email config error: {e}")

st.markdown("---")
st.markdown("""
**Setup checklist:**
1. Set `ANTHROPIC_API_KEY` in your `.env` for AI deal analysis
2. Set `EMAIL_FROM`, `EMAIL_PASSWORD`, `SMTP_HOST` in `.env` for email alerts
3. Enable **Automated Scraping** in Settings and set your scrape time
4. Restart the app — the scheduler starts automatically on app load
5. Use **Run Now** above to test the full pipeline immediately
""")
