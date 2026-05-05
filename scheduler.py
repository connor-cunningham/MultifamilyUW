"""Background scheduler — daily automated scraping, underwriting, and alerts."""
from __future__ import annotations

import os
import json
import logging
from datetime import datetime
from pathlib import Path

log = logging.getLogger("scheduler")

_STATE_FILE = Path("scheduler_state.json")


def _load_state() -> dict:
    if _STATE_FILE.exists():
        try:
            return json.loads(_STATE_FILE.read_text())
        except Exception:
            pass
    return {"last_run": None, "last_count": 0, "last_qualifying": 0, "runs": []}


def _save_state(state: dict):
    _STATE_FILE.write_text(json.dumps(state, indent=2, default=str))


def run_daily_scrape(
    source: str | None = None,
    states: list[str] | None = None,
    min_units: int = 3,
    max_units: int = 10,
    max_price: float = 2_000_000,
    max_results: int = 50,
) -> dict:
    """
    Full scrape → underwrite → AI score → DB save → email alerts pipeline.
    Returns a summary dict with counts.
    """
    from config import load_settings, WESTERN_US_STATES
    from models.database import init_db, get_session, upsert_deal
    from models.underwriting import UWAssumptions
    from underwriting.engine import underwrite
    from underwriting.scoring import score_deal
    from underwriting.assumptions import get_default_assumptions

    settings = load_settings()
    source = source or settings.get("auto_scrape_source", "mock")
    states = states or settings.get("auto_scrape_states", ["CA", "OR", "WA", "AZ", "CO"])
    alert_email = settings.get("alert_email_to") or os.environ.get("ALERT_EMAIL_TO", "")
    alert_threshold = float(settings.get("alert_score_threshold", 7.0))

    init_db()
    assumptions = get_default_assumptions()

    log.info(f"[Scheduler] Starting scrape: source={source} states={states}")
    props = []

    if source in ("mock", "crexi_mock"):
        from scrapers.mock import MockScraper
        props = list(MockScraper().fetch(states, min_units, max_units, max_price, max_results))
    elif source == "crexi":
        try:
            from scrapers.crexi import CrexiScraper
            props = list(CrexiScraper().fetch(states, min_units, max_units, max_price, max_results))
        except Exception as e:
            log.warning(f"Crexi error: {e} — falling back to mock")
            from scrapers.mock import MockScraper
            props = list(MockScraper().fetch(states, min_units, max_units, max_price, 10))
    elif source == "both":
        try:
            from scrapers.crexi import CrexiScraper
            props += list(CrexiScraper().fetch(states, min_units, max_units, max_price, max_results // 2))
        except Exception as e:
            log.warning(f"Crexi error: {e}")
        try:
            from scrapers.zillow import ZillowScraper
            props += list(ZillowScraper().fetch(states, min_units, max_units, max_price, max_results // 2))
        except Exception as e:
            log.warning(f"Zillow error: {e}")

    log.info(f"[Scheduler] Found {len(props)} listings")

    qualifying = 0
    db = get_session()

    try:
        for prop in props:
            try:
                results = underwrite(prop, assumptions)
                score = score_deal(results, prop)

                upsert_deal(db, {
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
                    "ai_score": score,
                })

                if score >= alert_threshold:
                    qualifying += 1
                    if alert_email:
                        try:
                            from models.analysis import DealAnalysis, grade_from_score, recommendation_from_score
                            from notifications.email_client import EmailClient
                            analysis = DealAnalysis(
                                score=score,
                                grade=grade_from_score(score),
                                recommendation=recommendation_from_score(score),
                                memo="",
                            )
                            EmailClient().send_deal_alert(prop, results, analysis)
                        except Exception as e:
                            log.warning(f"Alert email failed: {e}")

            except Exception as e:
                log.warning(f"Error underwriting {getattr(prop, 'address', '?')}: {e}")

        db.commit()
    finally:
        db.close()

    summary = {
        "timestamp": datetime.utcnow().isoformat(),
        "source": source,
        "states": states,
        "total_found": len(props),
        "qualifying": qualifying,
    }

    state = _load_state()
    state["last_run"] = summary["timestamp"]
    state["last_count"] = len(props)
    state["last_qualifying"] = qualifying
    state["runs"] = ([summary] + state.get("runs", []))[:50]
    _save_state(state)

    log.info(f"[Scheduler] Done — {len(props)} found, {qualifying} qualifying")
    return summary


# ── APScheduler integration ───────────────────────────────────────────────────

_scheduler = None


def get_scheduler():
    return _scheduler


def start_scheduler():
    global _scheduler
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from config import load_settings

        settings = load_settings()
        if not settings.get("auto_scrape_enabled", False):
            return

        scrape_time = settings.get("auto_scrape_time", "06:00")
        hour, minute = (int(x) for x in scrape_time.split(":"))

        _scheduler = BackgroundScheduler()
        _scheduler.add_job(run_daily_scrape, "cron", hour=hour, minute=minute,
                           id="daily_scrape", replace_existing=True)
        _scheduler.start()
        log.info(f"[Scheduler] Started — daily scrape at {scrape_time}")

    except ImportError:
        log.warning("[Scheduler] APScheduler not installed — run: pip install apscheduler")
    except Exception as e:
        log.warning(f"[Scheduler] Failed to start: {e}")


def stop_scheduler():
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        _scheduler = None


def get_state() -> dict:
    return _load_state()
