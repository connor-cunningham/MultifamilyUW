"""
Crexi.com scraper using Playwright to intercept XHR API responses.

Crexi loads listings via an internal REST API. This scraper launches a
headless browser, navigates to the search page, and captures the JSON
payload from the internal listing search endpoint.
"""
import json
import time
import random
from datetime import datetime
from typing import Iterator

from scrapers.base import BasePropertyScraper
from models.property import Property

CREXI_SEARCH_URL = (
    "https://www.crexi.com/properties"
    "?type=multifamily&propertyTypes=multifamily"
    "&minUnits={min_units}&maxUnits={max_units}&maxPrice={max_price}"
    "&states={states}&sort=recent"
)

_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]


def _parse_crexi_listing(item: dict) -> Property | None:
    try:
        address = item.get("address", {})
        full_addr = address.get("streetAddress") or address.get("street") or item.get("name", "Unknown")
        city = address.get("city") or item.get("city", "")
        state = address.get("state") or item.get("state", "")
        zipcode = address.get("postalCode") or item.get("zipCode", "")

        price = float(item.get("askingPrice") or item.get("price") or 0)
        if price <= 0:
            return None

        units = int(item.get("units") or item.get("numberOfUnits") or 0)
        if units <= 0:
            units_str = str(item.get("totalUnits") or "")
            units = int(units_str) if units_str.isdigit() else 0

        sqft = item.get("squareFeet") or item.get("buildingSize")
        year_built = item.get("yearBuilt")
        monthly_rent = item.get("monthlyIncome") or item.get("scheduledMonthlyIncome")

        listing_id = item.get("id") or item.get("listingId") or ""
        listing_url = f"https://www.crexi.com/properties/{listing_id}" if listing_id else ""

        return Property(
            address=full_addr,
            city=city,
            state=state,
            zip_code=zipcode,
            units=max(1, units),
            year_built=int(year_built) if year_built else None,
            sqft=int(sqft) if sqft else None,
            purchase_price=price,
            asking_price=price,
            monthly_rent_total=float(monthly_rent) if monthly_rent else None,
            listing_url=listing_url,
            source="crexi",
            scraped_at=datetime.utcnow(),
            raw=item,
        )
    except (ValueError, TypeError, KeyError):
        return None


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
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise RuntimeError("playwright not installed. Run: pip install playwright && playwright install chromium")

        states_param = "%2C".join(states)
        url = CREXI_SEARCH_URL.format(
            min_units=min_units,
            max_units=max_units,
            max_price=int(max_price),
            states=states_param,
        )

        captured_responses = []

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
            context = browser.new_context(
                user_agent=random.choice(_USER_AGENTS),
                viewport={"width": 1280, "height": 900},
            )
            page = context.new_page()

            def _capture_response(response):
                url_r = response.url
                # Crexi's internal search API
                if ("api.crexi.com" in url_r or "crexi.com/api" in url_r) and response.status == 200:
                    if any(kw in url_r for kw in ["properties", "listings", "search"]):
                        try:
                            body = response.json()
                            captured_responses.append(body)
                        except Exception:
                            pass

            page.on("response", _capture_response)

            try:
                page.goto(url, wait_until="networkidle", timeout=30000)
                time.sleep(random.uniform(2, 4))
            except Exception:
                pass
            finally:
                browser.close()

        yielded = 0
        for body in captured_responses:
            items = []
            if isinstance(body, list):
                items = body
            elif isinstance(body, dict):
                for key in ("data", "properties", "listings", "results", "items"):
                    if key in body and isinstance(body[key], list):
                        items = body[key]
                        break
                if not items and "properties" not in body:
                    items = [body]

            for item in items:
                if yielded >= max_results:
                    return
                prop = _parse_crexi_listing(item)
                if prop and prop.units >= min_units and prop.units <= max_units:
                    yielded += 1
                    yield prop
                time.sleep(0.05)
