"""Realistic mock listing generator — used when live scrapers are unavailable."""
import random
from datetime import datetime
from typing import Iterator

from scrapers.base import BasePropertyScraper
from models.property import Property

_WESTERN_CITIES = {
    "CA": [("Los Angeles", "90001"), ("Oakland", "94601"), ("Sacramento", "95814"),
           ("Fresno", "93701"), ("San Bernardino", "92401"), ("Bakersfield", "93301"),
           ("Stockton", "95201"), ("Long Beach", "90802"), ("Riverside", "92501")],
    "OR": [("Portland", "97201"), ("Eugene", "97401"), ("Salem", "97301"),
           ("Medford", "97501"), ("Bend", "97701")],
    "WA": [("Seattle", "98101"), ("Tacoma", "98401"), ("Spokane", "99201"),
           ("Bellevue", "98004"), ("Yakima", "98901")],
    "NV": [("Las Vegas", "89101"), ("Reno", "89501"), ("Henderson", "89002")],
    "AZ": [("Phoenix", "85001"), ("Tucson", "85701"), ("Mesa", "85201"),
           ("Tempe", "85281"), ("Chandler", "85224")],
    "CO": [("Denver", "80201"), ("Colorado Springs", "80901"), ("Aurora", "80010"),
           ("Fort Collins", "80521"), ("Pueblo", "81001")],
    "UT": [("Salt Lake City", "84101"), ("Provo", "84601"), ("Ogden", "84401")],
    "ID": [("Boise", "83701"), ("Nampa", "83651"), ("Meridian", "83642")],
    "MT": [("Billings", "59101"), ("Missoula", "59801"), ("Great Falls", "59401")],
    "WY": [("Cheyenne", "82001"), ("Casper", "82601")],
    "NM": [("Albuquerque", "87101"), ("Santa Fe", "87501"), ("Las Cruces", "88001")],
}

_STREET_NAMES = [
    "Oak St", "Maple Ave", "Cedar Blvd", "Pine St", "Elm St", "Washington Ave",
    "Lincoln Blvd", "Park Ave", "Main St", "Broadway", "Highland Ave", "Valley Rd",
    "Sunset Blvd", "Pacific Ave", "Mountain View Dr", "River Rd", "Lakeview Ave",
]

_PROPERTY_TYPES = ["Triplex", "Fourplex", "5-Unit Apartment", "6-Unit Building",
                   "8-Unit Apartment", "10-Unit Apartment"]


def _rand_address() -> str:
    num = random.randint(100, 9999)
    street = random.choice(_STREET_NAMES)
    return f"{num} {street}"


class MockScraper(BasePropertyScraper):
    source_name = "mock"

    def fetch(
        self,
        states: list[str],
        min_units: int = 3,
        max_units: int = 10,
        max_price: float = 2_000_000,
        max_results: int = 50,
    ) -> Iterator[Property]:
        target_states = [s for s in states if s in _WESTERN_CITIES]
        if not target_states:
            target_states = list(_WESTERN_CITIES.keys())

        generated = 0
        attempts = 0
        while generated < max_results and attempts < max_results * 10:
            attempts += 1
            state = random.choice(target_states)
            city, zipcode = random.choice(_WESTERN_CITIES[state])

            units = random.randint(min_units, max_units)

            # Market rent per unit varies by market
            rent_pu = {
                "CA": random.uniform(1400, 2800),
                "WA": random.uniform(1200, 2200),
                "OR": random.uniform(1100, 1900),
                "CO": random.uniform(1100, 1800),
                "NV": random.uniform(1000, 1700),
                "AZ": random.uniform(900, 1500),
                "UT": random.uniform(1000, 1600),
                "ID": random.uniform(900, 1400),
                "MT": random.uniform(800, 1300),
                "WY": random.uniform(800, 1200),
                "NM": random.uniform(750, 1200),
            }.get(state, random.uniform(900, 1600))

            gross_rent_annual = rent_pu * units * 12
            # Price at a 5.5–8.5% gross yield (market-dependent)
            gross_yield = random.uniform(0.055, 0.085)
            purchase_price = gross_rent_annual / gross_yield

            if purchase_price > max_price:
                continue

            sqft_per_unit = random.randint(650, 1100)
            year_built = random.randint(1955, 2015)

            # Occasional listings with known taxes
            annual_taxes = purchase_price * random.uniform(0.010, 0.015) if random.random() > 0.4 else None

            prop = Property(
                address=_rand_address(),
                city=city,
                state=state,
                zip_code=zipcode,
                units=units,
                year_built=year_built,
                sqft=sqft_per_unit * units,
                purchase_price=round(purchase_price / 1000) * 1000,
                asking_price=round(purchase_price / 1000) * 1000,
                monthly_rent_total=round(rent_pu * units, -1),
                annual_taxes=round(annual_taxes, -2) if annual_taxes else None,
                description=f"{units}-unit {random.choice(_PROPERTY_TYPES)} in {city}, {state}. "
                            f"Built {year_built}. {sqft_per_unit * units:,} SF total.",
                listing_url=f"https://mock.example.com/listing/{random.randint(100000, 999999)}",
                source="mock",
                scraped_at=datetime.utcnow(),
                raw={},
            )
            generated += 1
            yield prop
