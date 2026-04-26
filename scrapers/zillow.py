"""
Zillow scraper using their unofficial search JSON endpoint.

Zillow's SPA loads results via a JSON endpoint. This scraper uses
requests with browser-like headers to fetch multifamily listings.
Small multifamily on Zillow often appears as 2-4 unit or "multi-family"
home type. We filter conservatively and flag results for review.
"""
import json
import time
import random
from datetime import datetime
from typing import Iterator
from urllib.parse import urlencode

import requests

from scrapers.base import BasePropertyScraper
from models.property import Property

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.zillow.com/",
    "DNT": "1",
    "Connection": "keep-alive",
}

# Zillow wants/needs page queries — each state separately for accuracy
_ZILLOW_SEARCH = "https://www.zillow.com/search/GetSearchPageState.htm"


def _zillow_params(state_abbr: str, max_price: float, page: int = 1) -> dict:
    search_query_state = {
        "pagination": {"currentPage": page},
        "usersSearchTerm": state_abbr,
        "mapBounds": {
            "west": -125.0, "east": -102.0, "south": 31.0, "north": 49.0
        },
        "filterState": {
            "price": {"max": int(max_price)},
            "monthlyPayment": {"max": int(max_price / 240)},
            "homeType": {
                "value": ["MULTI_FAMILY"]
            },
        },
        "isListVisible": True,
        "isMapVisible": False,
        "mapZoom": 6,
    }
    return {
        "searchQueryState": json.dumps(search_query_state),
        "wants": json.dumps({
            "cat1": ["listResults", "mapResults"],
            "cat2": ["total"],
        }),
        "requestId": random.randint(1, 99),
    }


def _parse_zillow_result(item: dict) -> Property | None:
    try:
        price = float(item.get("price") or item.get("unformattedPrice") or 0)
        if price <= 0:
            return None

        beds = int(item.get("beds") or 0)
        baths = float(item.get("baths") or 0)

        # Estimate units from beds — small MF on Zillow is often listed as bedrooms
        # 2/1 duplex → 2 units, 3/2 → maybe triplex, etc.
        units_est = max(2, round(beds / 2)) if beds >= 2 else 2

        address_raw = item.get("addressStreet") or item.get("address") or "Unknown"
        city = item.get("addressCity") or ""
        state = item.get("addressState") or ""
        zipcode = item.get("addressZipcode") or ""

        sqft = item.get("area") or item.get("livingArea")
        year_built = None  # not typically in search results

        zpid = item.get("zpid") or ""
        listing_url = item.get("detailUrl") or f"https://www.zillow.com/homedetails/{zpid}_zpid/"

        return Property(
            address=address_raw,
            city=city,
            state=state,
            zip_code=zipcode,
            units=units_est,
            year_built=year_built,
            sqft=int(sqft) if sqft else None,
            purchase_price=price,
            asking_price=price,
            monthly_rent_total=None,  # not in search results
            description=f"Zillow MULTI_FAMILY listing. Beds: {beds}, Baths: {baths}. Units estimated from bed count — verify.",
            listing_url=listing_url,
            source="zillow",
            scraped_at=datetime.utcnow(),
            raw=item,
        )
    except (ValueError, TypeError, KeyError):
        return None


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
        session = requests.Session()
        session.headers.update(_HEADERS)

        # Prime session with a homepage visit for cookies
        try:
            session.get("https://www.zillow.com/", timeout=10)
            time.sleep(random.uniform(1.5, 3.0))
        except Exception:
            pass

        yielded = 0
        for state in states:
            if yielded >= max_results:
                break
            try:
                params = _zillow_params(state, max_price, page=1)
                resp = session.get(_ZILLOW_SEARCH, params=params, timeout=15)
                resp.raise_for_status()
                data = resp.json()

                cat1 = data.get("cat1", {})
                results = cat1.get("searchResults", {}).get("listResults", [])

                for item in results:
                    if yielded >= max_results:
                        return
                    prop = _parse_zillow_result(item)
                    if prop and min_units <= prop.units <= max_units and prop.purchase_price <= max_price:
                        yield prop
                        yielded += 1

                time.sleep(random.uniform(2.0, 4.0))
            except Exception:
                # Zillow blocks are common — silently continue to next state
                time.sleep(random.uniform(3.0, 6.0))
                continue
