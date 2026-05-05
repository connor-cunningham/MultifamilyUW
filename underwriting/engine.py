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


def _compute_unlevered_irr(prop, assumptions, yearly_metrics, hold_years) -> float | None:
    """IRR using NOI (pre-debt) cash flows — measures asset-level return."""
    from underwriting.cashflow import _exit_proceeds
    pp = prop.purchase_price
    # Year-0 = full purchase price (unlevered)
    flows = [-pp * (1 + assumptions.closing_cost_pct)]
    for yr in range(1, hold_years + 1):
        noi = yearly_metrics[yr - 1].noi
        if yr == hold_years:
            ep, _, _ = _exit_proceeds(prop, assumptions, yearly_metrics, hold_years)
            flows.append(noi + ep * (1 - assumptions.transaction_cost_pct))
        else:
            flows.append(noi)
    return compute_irr(flows)


def _compute_breakeven_occupancy(y1) -> float | None:
    """Occupancy at which NOI = debt service (DSCR = 1.0x)."""
    if not y1.gpr or not y1.debt_service:
        return None
    # NOI = EGI_adjusted - OpEx = GPR*(1-occ)*adj - opex = DS
    # Simplified: (gpr * occ_eff - mgmt_adj) - opex_fixed = ds
    # Use: required_egi = opex + ds; required_occ = required_egi / gpr
    opex_ex_mgmt = (y1.total_opex - y1.mgmt)
    mgmt_rate = y1.mgmt / y1.effective_egi if y1.effective_egi else 0.0
    # required_total_egi * (1 - mgmt_rate) = opex_ex_mgmt + ds
    required_egi = (opex_ex_mgmt + y1.debt_service) / (1 - mgmt_rate) if mgmt_rate < 1 else None
    if required_egi is None:
        return None
    # effective_egi = gpr * occ + other; other income assumed constant
    other = y1.other_income
    required_gpr_portion = required_egi - other
    occ = required_gpr_portion / y1.gpr if y1.gpr else None
    if occ is None or occ < 0:
        return None
    return round(min(occ, 1.0), 4)


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

    debt_yield = round(y1.noi / loan, 4) if loan else None
    unlevered_irr = _compute_unlevered_irr(prop, assumptions, yearly, hold10)
    breakeven_occ = _compute_breakeven_occupancy(y1)

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
        debt_yield=debt_yield,
        unlevered_irr=unlevered_irr,
        breakeven_occupancy=breakeven_occ,
    )
