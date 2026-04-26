"""Core underwriting engine — takes a Property + UWAssumptions, returns UWResults."""
from models.property import Property
from models.underwriting import UWAssumptions, UWResults, YearlyMetrics
from underwriting.cashflow import (
    build_yearly_metrics,
    build_cash_flows,
    compute_irr,
    compute_equity_multiple,
    _exit_proceeds,
)


def underwrite(prop: Property, assumptions: UWAssumptions) -> UWResults:
    yearly = build_yearly_metrics(prop, assumptions)
    y1 = yearly[0]

    pp = prop.purchase_price
    loan = pp * assumptions.ltv
    equity = pp * (1 - assumptions.ltv) * (1 + assumptions.closing_cost_pct)
    going_in_cap = y1.noi / pp if pp else 0.0

    # 5-year returns
    hold5 = min(5, assumptions.hold_years)
    cf5 = build_cash_flows(prop, assumptions, yearly, hold5)
    irr5 = compute_irr(cf5)
    em5 = compute_equity_multiple(cf5)

    # 10-year returns
    hold10 = assumptions.hold_years
    cf10 = build_cash_flows(prop, assumptions, yearly, hold10)
    irr10 = compute_irr(cf10)
    em10 = compute_equity_multiple(cf10)

    exit_price, exit_cap, _ = _exit_proceeds(prop, assumptions, yearly, hold10)

    return UWResults(
        gpr=y1.gpr,
        vacancy_loss=y1.vacancy_loss,
        egi=y1.egi,
        other_income=y1.other_income,
        effective_egi=y1.effective_egi,
        taxes=y1.taxes,
        insurance=y1.insurance,
        utilities=y1.utilities,
        maintenance=y1.maintenance,
        mgmt=y1.mgmt,
        admin=y1.admin,
        capex=y1.capex,
        total_opex=y1.total_opex,
        noi=y1.noi,
        going_in_cap_rate=round(going_in_cap, 6),
        price_per_unit=round(prop.price_per_unit, 2),
        price_per_sqft=round(prop.price_per_sqft, 2) if prop.price_per_sqft else None,
        loan_amount=round(loan, 2),
        equity_invested=round(equity, 2),
        annual_ds_io=round(y1.debt_service, 2),
        net_cash_flow_y1=round(y1.net_cash_flow, 2),
        coc_y1=round(y1.net_cash_flow / equity, 6) if equity else 0.0,
        dscr_y1=round(y1.noi / y1.debt_service, 4) if y1.debt_service else 0.0,
        irr_5yr=irr5,
        irr_10yr=irr10,
        equity_multiple_5yr=em5,
        equity_multiple_10yr=em10,
        cash_flows=cf10,
        yearly_metrics=[m.model_dump() for m in yearly],
        exit_price=round(exit_price, 2),
        exit_cap_rate=round(exit_cap, 6),
    )
