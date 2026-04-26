"""Multi-year cash flow model and return calculations."""
from typing import Optional
import numpy_financial as npf

from models.property import Property
from models.underwriting import UWAssumptions, YearlyMetrics


def _monthly_am_payment(loan: float, rate: float, n_months: int) -> float:
    """Standard amortizing monthly payment."""
    r = rate / 12
    return loan * r * (1 + r) ** n_months / ((1 + r) ** n_months - 1)


def build_yearly_metrics(
    prop: Property,
    assumptions: UWAssumptions,
) -> list[YearlyMetrics]:
    """Return YearlyMetrics for years 1..hold_years."""
    units = prop.units
    pp = prop.purchase_price
    loan = pp * assumptions.ltv
    rate = assumptions.interest_rate

    # Base rent per unit (monthly)
    if assumptions.market_rent_per_unit:
        base_rent_pu = assumptions.market_rent_per_unit
    elif prop.monthly_rent_total and units:
        base_rent_pu = prop.monthly_rent_total / units
    else:
        # Fallback: estimate from price/unit at a ~7% gross yield
        base_rent_pu = (pp / units * 0.07) / 12

    # Annual IO debt service
    io_ds = loan * rate

    # Post-IO amortizing payment (30yr am on remaining balance — same rate for modeling simplicity)
    am_payment_monthly = _monthly_am_payment(loan, rate, 360)
    am_ds = am_payment_monthly * 12

    metrics = []
    for yr in range(1, assumptions.hold_years + 1):
        growth_r = (1 + assumptions.rent_growth_annual) ** (yr - 1)
        growth_e = (1 + assumptions.expense_growth_annual) ** (yr - 1)

        rent_pu = base_rent_pu * growth_r
        gpr = rent_pu * units * 12
        vacancy_loss = gpr * assumptions.vacancy_rate
        egi = gpr - vacancy_loss
        other = assumptions.other_income_per_unit_monthly * units * 12 * growth_r
        eff_egi = egi + other

        taxes = pp * assumptions.tax_rate_of_value * growth_e
        insurance = assumptions.insurance_per_unit * units * growth_e
        utilities = assumptions.utilities_per_unit_monthly * units * 12 * growth_e
        maintenance = assumptions.maintenance_per_unit * units * growth_e
        mgmt = eff_egi * assumptions.mgmt_pct_of_egi
        admin = assumptions.admin_per_unit * units * growth_e
        capex = assumptions.capex_reserve_per_unit * units * growth_e
        total_opex = taxes + insurance + utilities + maintenance + mgmt + admin + capex

        noi = eff_egi - total_opex
        is_io = yr <= assumptions.io_years
        ds = io_ds if is_io else am_ds
        ncf = noi - ds

        metrics.append(YearlyMetrics(
            year=yr,
            gpr=round(gpr, 2),
            vacancy_loss=round(vacancy_loss, 2),
            egi=round(egi, 2),
            other_income=round(other, 2),
            effective_egi=round(eff_egi, 2),
            taxes=round(taxes, 2),
            insurance=round(insurance, 2),
            utilities=round(utilities, 2),
            maintenance=round(maintenance, 2),
            mgmt=round(mgmt, 2),
            admin=round(admin, 2),
            capex=round(capex, 2),
            total_opex=round(total_opex, 2),
            noi=round(noi, 2),
            debt_service=round(ds, 2),
            net_cash_flow=round(ncf, 2),
            is_io=is_io,
        ))

    return metrics


def _exit_proceeds(
    prop: Property,
    assumptions: UWAssumptions,
    yearly_metrics: list[YearlyMetrics],
    exit_year: int,
) -> tuple[float, float, float]:
    """Return (exit_price, exit_cap_rate, net_proceeds) at exit_year."""
    going_in_cap = yearly_metrics[0].noi / prop.purchase_price
    exit_cap = going_in_cap + assumptions.exit_cap_spread
    exit_noi = yearly_metrics[exit_year - 1].noi
    exit_price = exit_noi / exit_cap if exit_cap > 0 else 0.0

    loan = prop.purchase_price * assumptions.ltv
    # Loan balance at exit — IO period: principal unchanged; post-IO: amortized
    if exit_year <= assumptions.io_years:
        loan_balance = loan
    else:
        am_months_elapsed = (exit_year - assumptions.io_years) * 12
        rate_m = assumptions.interest_rate / 12
        monthly_pmt = _monthly_am_payment(loan, assumptions.interest_rate, 360)
        loan_balance = loan * (1 + rate_m) ** am_months_elapsed - monthly_pmt * ((1 + rate_m) ** am_months_elapsed - 1) / rate_m

    net_proceeds = exit_price * (1 - assumptions.transaction_cost_pct) - loan_balance
    return exit_price, exit_cap, net_proceeds


def build_cash_flows(
    prop: Property,
    assumptions: UWAssumptions,
    yearly_metrics: list[YearlyMetrics],
    exit_year: int,
) -> list[float]:
    """Build cash flow array [year0, year1, ..., exit_year] for IRR."""
    equity = prop.purchase_price * (1 - assumptions.ltv) * (1 + assumptions.closing_cost_pct)
    flows = [-equity]
    for yr in range(1, exit_year + 1):
        m = yearly_metrics[yr - 1]
        if yr == exit_year:
            _, _, net_proceeds = _exit_proceeds(prop, assumptions, yearly_metrics, exit_year)
            flows.append(m.net_cash_flow + net_proceeds)
        else:
            flows.append(m.net_cash_flow)
    return flows


def compute_irr(cash_flows: list[float]) -> Optional[float]:
    try:
        irr = npf.irr(cash_flows)
        import math
        if irr is None or math.isnan(irr) or math.isinf(irr) or abs(irr) > 10:
            return None
        return round(float(irr), 6)
    except Exception:
        return None


def compute_equity_multiple(cash_flows: list[float]) -> float:
    equity_in = abs(cash_flows[0])
    total_out = sum(max(0.0, cf) for cf in cash_flows[1:])
    return round(total_out / equity_in, 3) if equity_in > 0 else 0.0
