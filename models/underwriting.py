from typing import Optional
from pydantic import BaseModel, Field


class UWAssumptions(BaseModel):
    # Financing — 7/1 IO ARM defaults
    ltv: float = Field(0.75, ge=0.5, le=0.95)
    interest_rate: float = Field(0.0575, ge=0.01, le=0.20)
    io_years: int = Field(7, ge=1, le=10)
    hold_years: int = Field(10, ge=1, le=30)
    closing_cost_pct: float = Field(0.03, ge=0.0, le=0.10)
    transaction_cost_pct: float = Field(0.03, ge=0.0, le=0.10)

    # Income
    market_rent_per_unit: Optional[float] = None  # monthly; None = use listing data
    vacancy_rate: float = Field(0.05, ge=0.0, le=0.50)
    other_income_per_unit_monthly: float = Field(75.0, ge=0.0)
    rent_growth_annual: float = Field(0.03, ge=-0.10, le=0.20)

    # Expenses (annual per unit unless noted)
    tax_rate_of_value: float = Field(0.0125, ge=0.0, le=0.05)
    insurance_per_unit: float = Field(1200.0, ge=0.0)
    utilities_per_unit_monthly: float = Field(75.0, ge=0.0)
    maintenance_per_unit: float = Field(850.0, ge=0.0)
    mgmt_pct_of_egi: float = Field(0.09, ge=0.0, le=0.25)
    admin_per_unit: float = Field(300.0, ge=0.0)
    capex_reserve_per_unit: float = Field(275.0, ge=0.0)
    expense_growth_annual: float = Field(0.03, ge=-0.10, le=0.20)

    # Exit
    exit_cap_spread: float = Field(0.0025, ge=-0.05, le=0.05)


class YearlyMetrics(BaseModel):
    year: int
    gpr: float
    vacancy_loss: float
    egi: float
    other_income: float
    effective_egi: float
    taxes: float
    insurance: float
    utilities: float
    maintenance: float
    mgmt: float
    admin: float
    capex: float
    total_opex: float
    noi: float
    debt_service: float
    net_cash_flow: float
    is_io: bool


class UWResults(BaseModel):
    # Year 1 snapshot
    gpr: float
    vacancy_loss: float
    egi: float
    other_income: float
    effective_egi: float
    taxes: float
    insurance: float
    utilities: float
    maintenance: float
    mgmt: float
    admin: float
    capex: float
    total_opex: float
    noi: float
    going_in_cap_rate: float
    price_per_unit: float
    price_per_sqft: Optional[float]

    # Debt
    loan_amount: float
    equity_invested: float
    annual_ds_io: float

    # Year 1 performance
    net_cash_flow_y1: float
    coc_y1: float
    dscr_y1: float

    # Multi-year returns
    irr_5yr: Optional[float]
    irr_10yr: Optional[float]
    equity_multiple_5yr: float
    equity_multiple_10yr: float

    # Raw series
    cash_flows: list  # year 0 (negative equity) through hold_years
    yearly_metrics: list  # list of YearlyMetrics dicts

    # Exit
    exit_price: float
    exit_cap_rate: float

    # Extended metrics (v2)
    debt_yield: Optional[float] = None          # NOI / loan amount (lender metric, target >8%)
    unlevered_irr: Optional[float] = None       # IRR on NOI cash flows without debt
    breakeven_occupancy: Optional[float] = None # occupancy at which DSCR = 1.0x
