"""
Crexi.com scraper using Playwright DOM parsing.

Navigates to the search results page and extracts listing data
directly from the rendered HTML — more reliable than XHR interception.
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


def _parse_price(text: str) -> float | None:
    """Extract numeric price from strings like '$1,250,000' or '1.25M'."""
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


def _parse_units(text: str) -> int | None:
    """Extract unit count from strings like '6 Units' or '6-Unit'."""
    if not text:
        return None
    m = re.search(r"(\d+)\s*[Uu]nit", text)
    return int(m.group(1)) if m else None


def _parse_sqft(text: str) -> int | None:
    if not text:
        return None
    text = text.replace(",", "")
    m = re.search(r"([\d,]+)\s*(?:sf|sqft|sq\.?\s*ft)", text, re.IGNORECASE)
    return int(m.group(1).replace(",", "")) if m else None


class CrexiScraper(BasePropertyScraper):
    source_name = "crexi"

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

        # Build search URL — Crexi accepts comma-separated state abbreviations
        states_param = ",".join(states)
        url = (
            f"https://www.crexi.com/properties"
            f"?type=multifamily"
            f"&propertyTypes=multifamily"
            f"&minUnits={min_units}"
            f"&maxUnits={max_units}"
            f"&priceMax={int(max_price)}"
            f"&states={states_param}"
            f"&sort=RecentlyListed"
        )

        yielded = 0

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-blink-features=AutomationControlled"],
            )
            context = browser.new_context(
                user_agent=random.choice(_USER_AGENTS),
                viewport={"width": 1280, "height": 900},
                locale="en-US",
            )
            # Mask automation signals
            context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            page = context.new_page()

            try:
                print(f"[Crexi] Loading: {url}")
                page.goto(url, wait_until="domcontentloaded", timeout=30000)

                # Wait for listing cards to appear — try multiple selectors
                card_sel = None
                for sel in [
                    ".property-card",
                    "[class*='PropertyCard']",
                    "[class*='property-card']",
                    "[class*='asset-card']",
                    "[data-testid*='property']",
                    "article",
                ]:
                    try:
                        page.wait_for_selector(sel, timeout=8000)
                        cards = page.query_selector_all(sel)
                        if len(cards) >= 2:
                            card_sel = sel
                            break
                    except PWTimeout:
                        continue

                if not card_sel:
                    # Fallback: wait a bit longer and try to grab any JSON in page
                    time.sleep(4)
                    cards = []
                else:
                    # Scroll to load more
                    for _ in range(3):
                        page.evaluate("window.scrollBy(0, window.innerHeight)")
                        time.sleep(1)
                    cards = page.query_selector_all(card_sel)

                print(f"[Crexi] Found {len(cards)} cards with selector '{card_sel}'")

                for card in cards:
                    if yielded >= max_results:
                        break
                    try:
                        full_text = card.inner_text()
                        html = card.inner_html()

                        # Extract href for listing URL
                        link = card.query_selector("a[href*='/properties/']")
                        listing_url = ""
                        if link:
                            href = link.get_attribute("href") or ""
                            listing_url = f"https://www.crexi.com{href}" if href.startswith("/") else href

                        # Price
                        price = None
                        for price_sel in ["[class*='price']", "[class*='Price']", "[class*='asking']"]:
                            el = card.query_selector(price_sel)
                            if el:
                                price = _parse_price(el.inner_text())
                                if price:
                                    break
                        if not price:
                            price = _parse_price(full_text)

                        if not price or price > max_price:
                            continue

                        # Units
                        units = _parse_units(full_text)
                        if not units or not (min_units <= units <= max_units):
                            continue

                        # Address — look for address-like element
                        address = ""
                        city = ""
                        state = ""
                        for addr_sel in ["[class*='address']", "[class*='Address']", "[class*='location']", "[class*='title']"]:
                            el = card.query_selector(addr_sel)
                            if el:
                                addr_text = el.inner_text().strip()
                                if addr_text:
                                    # Try to split "123 Main St, Phoenix, AZ"
                                    parts = [p.strip() for p in addr_text.split(",")]
                                    if len(parts) >= 3:
                                        address = parts[0]
                                        city = parts[-2].strip()
                                        state_zip = parts[-1].strip().split()
                                        state = state_zip[0] if state_zip else ""
                                    elif len(parts) == 2:
                                        address = parts[0]
                                        city = parts[1].strip()
                                    else:
                                        address = addr_text[:60]
                                    break

                        if not address:
                            # Grab first line of card text as address
                            lines = [l.strip() for l in full_text.splitlines() if l.strip()]
                            address = lines[0][:60] if lines else "Unknown"

                        if not state:
                            for s in states:
                                if s.upper() in full_text.upper():
                                    state = s
                                    break

                        # SF
                        sqft = _parse_sqft(full_text)

                        # Cap rate sometimes listed
                        cap_match = re.search(r"(\d+\.?\d*)\s*%\s*Cap", full_text, re.IGNORECASE)
                        cap_note = f"Listed cap: {cap_match.group(1)}%" if cap_match else ""

                        prop = Property(
                            address=address or "See listing",
                            city=city or "",
                            state=state or (states[0] if states else ""),
                            units=units,
                            purchase_price=price,
                            asking_price=price,
                            sqft=sqft,
                            description=cap_note,
                            listing_url=listing_url,
                            source="crexi",
                            scraped_at=datetime.utcnow(),
                            raw={"text": full_text[:500]},
                        )
                        yielded += 1
                        yield prop

                    except Exception as e:
                        print(f"[Crexi] Card parse error: {e}")
                        continue

            except PWTimeout:
                print("[Crexi] Page load timed out — site may be slow or blocking")
            except Exception as e:
                print(f"[Crexi] Error: {e}")
            finally:
                browser.close()

        print(f"[Crexi] Done — {yielded} listings extracted")
