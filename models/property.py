from datetime import datetime
from typing import Optional
from pydantic import BaseModel, field_validator


class Property(BaseModel):
    address: str
    city: str
    state: str
    zip_code: str = ""
    units: int
    year_built: Optional[int] = None
    sqft: Optional[int] = None
    purchase_price: float
    asking_price: Optional[float] = None
    monthly_rent_total: Optional[float] = None  # as listed by seller
    annual_taxes: Optional[float] = None
    description: Optional[str] = None
    listing_url: str = ""
    source: str = "manual"  # "crexi" | "zillow" | "manual" | "mock"
    scraped_at: datetime = None
    raw: dict = {}

    @field_validator("state")
    @classmethod
    def state_upper(cls, v: str) -> str:
        return v.upper().strip()

    @field_validator("scraped_at", mode="before")
    @classmethod
    def default_scraped_at(cls, v):
        return v or datetime.utcnow()

    @property
    def price_per_unit(self) -> float:
        return self.purchase_price / self.units if self.units else 0.0

    @property
    def price_per_sqft(self) -> Optional[float]:
        if self.sqft and self.sqft > 0:
            return self.purchase_price / self.sqft
        return None

    @property
    def implied_monthly_rent_per_unit(self) -> Optional[float]:
        if self.monthly_rent_total and self.units:
            return self.monthly_rent_total / self.units
        return None
