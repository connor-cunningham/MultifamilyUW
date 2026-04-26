"""
Zillow scraper using Playwright for full browser automation.

Raw requests to Zillow are blocked — a real browser session is required.
Navigates to Zillow's multi-family search and parses rendered cards.
"""
import re
import time
import random
from datetime import datetime
from typing import Iterator

from scrapers.base import BasePropertyScraper
from models.property import Property

_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
]

# State name → abbreviation for building search queries
_STATE_NAMES = {
    "CA": "california", "OR": "oregon", "WA": "washington",
    "NV": "nevada", "AZ": "arizona", "CO": "colorado",
    "UT": "utah", "ID": "idaho", "MT": "montana",
    "WY": "wyoming", "NM": "new-mexico", "AK": "alaska", "HI": "hawaii",
}


def _parse_price(text: str) -> float | None:
    if not text:
        return None
    text = text.replace(",", "").replace("$", "").strip()
    m = re.search(r"([\d.]+)\s*([MmKk]?)", text)
    if not m:
        return None
    val = float(m.group(1))
    suffix = m.group(2).upper()
    if suffix == "M":
        val *= 1_000_000
    elif suffix == "K":
        val *= 1_000
    return val if val > 0 else None


def _estimate_units_from_text(text: str) -> int:
    """Estimate unit count from listing text — Zillow shows beds not units."""
    m = re.search(r"(\d+)\s*(?:unit|apt|apartment)", text, re.IGNORECASE)
    if m:
        return int(m.group(1))
    # Fall back to beds / 2 estimate
    m = re.search(r"(\d+)\s*bd", text, re.IGNORECASE)
    if m:
        beds = int(m.group(1))
        return max(2, round(beds / 2))
    return 0


class ZillowScraper(BasePropertyScraper):
    source_name = "zillow"

    def fetch(
        self,
        states: list[str],
        min_units: int = 3,
        max_units: int = 10,
        max_price: float = 2_000_000,
        max_results: int = 50,
    ) -> Iterator[Property]:
        try:
            from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
        except ImportError:
            raise RuntimeError("Run: pip install playwright && playwright install chromium")

        yielded = 0

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-blink-features=AutomationControlled"],
            )
            context = browser.new_context(
                user_agent=random.choice(_USER_AGENTS),
                viewport={"width": 1440, "height": 900},
                locale="en-US",
            )
            context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            page = context.new_page()

            for state in states:
                if yielded >= max_results:
                    break

                state_slug = _STATE_NAMES.get(state.upper(), state.lower())
                # Zillow URL for multi-family homes for sale in a state
                url = (
                    f"https://www.zillow.com/{state_slug}/"
                    f"multifamily_homes/?searchQueryState="
                    + re.sub(r'\s+', '', str({
                        "pagination": {"currentPage": 1},
                        "filterState": {
                            "price": {"max": int(max_price)},
                            "mf": {"value": True},
                            "con": {"value": False},
                            "land": {"value": False},
                            "tow": {"value": False},
                            "apa": {"value": False},
                            "sf": {"value": False},
                            "ah": {"value": True},
                        },
                        "isListVisible": True,
                    }))
                )

                # Simpler, more reliable Zillow URL
                url = f"https://www.zillow.com/{state_slug}/multifamily_homes/"

                try:
                    print(f"[Zillow] Loading {state}: {url}")
                    page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    time.sleep(random.uniform(2, 4))

                    # Wait for listing cards
                    card_sel = None
                    for sel in [
                        "[data-test='property-card']",
                        "article.list-card",
                        "[class*='StyledPropertyCard']",
                        "[class*='property-card']",
                        ".zsg-photo-card",
                        "li.ListItem",
                    ]:
                        try:
                            page.wait_for_selector(sel, timeout=6000)
                            cards = page.query_selector_all(sel)
                            if len(cards) >= 2:
                                card_sel = sel
                                break
                        except PWTimeout:
                            continue

                    if not card_sel:
                        print(f"[Zillow] No cards found for {state} — may be blocked")
                        time.sleep(2)
                        continue

                    cards = page.query_selector_all(card_sel)
                    print(f"[Zillow] {state}: {len(cards)} cards found")

                    for card in cards:
                        if yielded >= max_results:
                            break
                        try:
                            full_text = card.inner_text()

                            # Price
                            price = None
                            for price_sel in [
                                "[data-test='property-card-price']",
                                "[class*='Price']",
                                "[class*='price']",
                                "span[class*='zsg-photo-card-price']",
                            ]:
                                el = card.query_selector(price_sel)
                                if el:
                                    price = _parse_price(el.inner_text())
                                    if price:
                                        break
                            if not price:
                                price = _parse_price(full_text)

                            if not price or price > max_price:
                                continue

                            # Units estimate
                            units = _estimate_units_from_text(full_text)
                            if units < min_units:
                                continue

                            # Address
                            address = ""
                            city = ""
                            for addr_sel in [
                                "[data-test='property-card-addr']",
                                "address",
                                "[class*='Address']",
                                "[class*='address']",
                            ]:
                                el = card.query_selector(addr_sel)
                                if el:
                                    addr_text = el.inner_text().strip()
                                    parts = [p.strip() for p in addr_text.split(",")]
                                    address = parts[0] if parts else addr_text[:60]
                                    if len(parts) >= 2:
                                        city = parts[1].strip()
                                    break

                            if not address:
                                lines = [l.strip() for l in full_text.splitlines() if l.strip()]
                                address = lines[0][:60] if lines else "See listing"

                            # Listing URL
                            link = card.query_selector("a[href*='/homedetails/'], a[href*='zillow.com']")
                            listing_url = ""
                            if link:
                                href = link.get_attribute("href") or ""
                                listing_url = f"https://www.zillow.com{href}" if href.startswith("/") else href

                            # SF
                            sqft = None
                            sqft_match = re.search(r"([\d,]+)\s*sqft", full_text, re.IGNORECASE)
                            if sqft_match:
                                sqft = int(sqft_match.group(1).replace(",", ""))

                            prop = Property(
                                address=address,
                                city=city,
                                state=state.upper(),
                                units=units,
                                purchase_price=price,
                                asking_price=price,
                                sqft=sqft,
                                description=f"Zillow listing — unit count estimated from listing text. Verify before underwriting.",
                                listing_url=listing_url,
                                source="zillow",
                                scraped_at=datetime.utcnow(),
                                raw={"text": full_text[:500]},
                            )
                            yielded += 1
                            yield prop

                        except Exception as e:
                            print(f"[Zillow] Card parse error: {e}")
                            continue

                    time.sleep(random.uniform(2, 4))

                except PWTimeout:
                    print(f"[Zillow] Timed out on {state}")
                    continue
                except Exception as e:
                    print(f"[Zillow] Error on {state}: {e}")
                    continue

            browser.close()

        print(f"[Zillow] Done — {yielded} listings extracted")
