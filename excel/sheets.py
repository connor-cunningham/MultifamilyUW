"""One function per Excel sheet tab."""
from datetime import datetime
from openpyxl import Workbook
from openpyxl.utils import get_column_letter
from openpyxl.styles import Alignment

from models.property import Property
from models.underwriting import UWAssumptions, UWResults
from excel.styles import (
    apply_cell, style_header_row, style_subheader_row, style_total_row, style_alt_row,
    FILL_HEADER, FILL_SUBHEADER, FILL_INPUT, FILL_GREEN, FILL_RED, FILL_GRAY, FILL_TOTAL,
    FONT_TITLE, FONT_HEADER, FONT_SUBHEADER, FONT_BODY, FONT_TOTAL, FONT_METRIC, FONT_SMALL,
    ALIGN_CENTER, ALIGN_LEFT, ALIGN_RIGHT,
    BORDER_ALL, BORDER_THICK_BOTTOM,
    FMT_DOLLAR, FMT_DOLLAR_DEC, FMT_PCT, FMT_PCT_1, FMT_NUM, FMT_MULT,
    NAVY, WHITE, LIGHT_BLUE, YELLOW,
)


def _set_col_widths(ws, widths: dict):
    for col_letter, width in widths.items():
        ws.column_dimensions[col_letter].width = width


def build_summary(ws, prop: Property, assumptions: UWAssumptions, results: UWResults):
    ws.sheet_view.showGridLines = False
    _set_col_widths(ws, {"A": 28, "B": 18, "C": 4, "D": 28, "E": 18})

    # Title block
    ws.row_dimensions[1].height = 30
    apply_cell(ws, 1, 1, f"DEAL SUMMARY — {prop.address.upper()}", font=FONT_TITLE, align=ALIGN_LEFT)
    ws.merge_cells("A1:E1")
    apply_cell(ws, 2, 1, f"{prop.city}, {prop.state}  |  {prop.units} Units  |  {prop.year_built or 'N/A'} Built",
               font=FONT_SUBHEADER, align=ALIGN_LEFT)
    ws.merge_cells("A2:E2")
    apply_cell(ws, 3, 1, f"Analyzed: {datetime.now().strftime('%B %d, %Y')}  |  Source: {prop.source.upper()}",
               font=FONT_SMALL, align=ALIGN_LEFT)
    ws.merge_cells("A3:E3")

    # ── Left column: Property & Pricing ──────────────────────────────────
    r = 5
    apply_cell(ws, r, 1, "PROPERTY", font=FONT_HEADER, fill=FILL_HEADER, align=ALIGN_CENTER, border=BORDER_ALL)
    apply_cell(ws, r, 2, "", fill=FILL_HEADER, border=BORDER_ALL)
    ws.merge_cells(f"A{r}:B{r}")
    rows_l = [
        ("Purchase Price", results.price_per_unit * results.price_per_unit / results.price_per_unit
         if False else prop.purchase_price, FMT_DOLLAR),
        ("Units", prop.units, FMT_NUM),
        ("Price / Unit", results.price_per_unit, FMT_DOLLAR),
        ("Price / SF", results.price_per_sqft, FMT_DOLLAR_DEC),
        ("Year Built", prop.year_built, None),
        ("SF (Total)", prop.sqft, FMT_NUM),
        ("State", prop.state, None),
    ]
    for i, (label, val, fmt) in enumerate(rows_l):
        row = r + 1 + i
        alt = i % 2 == 0
        apply_cell(ws, row, 1, label, font=FONT_BODY, fill=FILL_GRAY if alt else None, border=BORDER_ALL, align=ALIGN_LEFT)
        apply_cell(ws, row, 2, val, font=FONT_BODY, fill=FILL_GRAY if alt else None, border=BORDER_ALL, align=ALIGN_RIGHT, fmt=fmt)

    # ── Right column: Financing ───────────────────────────────────────────
    apply_cell(ws, r, 4, "FINANCING", font=FONT_HEADER, fill=FILL_HEADER, align=ALIGN_CENTER, border=BORDER_ALL)
    apply_cell(ws, r, 5, "", fill=FILL_HEADER, border=BORDER_ALL)
    ws.merge_cells(f"D{r}:E{r}")
    rows_r = [
        ("Loan Amount", results.loan_amount, FMT_DOLLAR),
        ("LTV", assumptions.ltv, FMT_PCT),
        ("Interest Rate", assumptions.interest_rate, FMT_PCT),
        ("Structure", f"7/1 IO ARM", None),
        ("IO Period", f"{assumptions.io_years} Years", None),
        ("Annual DS (IO)", results.annual_ds_io, FMT_DOLLAR),
        ("Equity Invested", results.equity_invested, FMT_DOLLAR),
    ]
    for i, (label, val, fmt) in enumerate(rows_r):
        row = r + 1 + i
        alt = i % 2 == 0
        apply_cell(ws, row, 4, label, font=FONT_BODY, fill=FILL_GRAY if alt else None, border=BORDER_ALL, align=ALIGN_LEFT)
        apply_cell(ws, row, 5, val, font=FONT_BODY, fill=FILL_GRAY if alt else None, border=BORDER_ALL, align=ALIGN_RIGHT, fmt=fmt)

    # ── Returns metrics block ─────────────────────────────────────────────
    r2 = r + len(rows_l) + 2
    apply_cell(ws, r2, 1, "KEY RETURNS", font=FONT_HEADER, fill=FILL_HEADER, align=ALIGN_CENTER, border=BORDER_ALL)
    for c in range(2, 6):
        apply_cell(ws, r2, c, "", fill=FILL_HEADER, border=BORDER_ALL)
    ws.merge_cells(f"A{r2}:E{r2}")

    metrics = [
        ("Going-In Cap Rate", results.going_in_cap_rate, FMT_PCT_1),
        ("Year 1 Cash-on-Cash", results.coc_y1, FMT_PCT_1),
        ("DSCR (Year 1)", results.dscr_y1, "0.00x"),
        ("5-Year IRR", results.irr_5yr, FMT_PCT_1),
        ("10-Year IRR", results.irr_10yr, FMT_PCT_1),
        ("5-Year Equity Multiple", results.equity_multiple_5yr, FMT_MULT),
        ("10-Year Equity Multiple", results.equity_multiple_10yr, FMT_MULT),
        ("Exit Cap Rate", results.exit_cap_rate, FMT_PCT_1),
        ("Exit Price", results.exit_price, FMT_DOLLAR),
        ("NOI (Year 1)", results.noi, FMT_DOLLAR),
    ]
    # Split into two columns
    half = (len(metrics) + 1) // 2
    for i, (label, val, fmt) in enumerate(metrics[:half]):
        row = r2 + 1 + i
        alt = i % 2 == 0
        fill = FILL_GRAY if alt else None
        # Color-code returns
        if "IRR" in label or "Cash-on-Cash" in label:
            if isinstance(val, float):
                fill = FILL_GREEN if val >= 0.08 else FILL_RED
        apply_cell(ws, row, 1, label, font=FONT_BODY, fill=fill, border=BORDER_ALL, align=ALIGN_LEFT)
        apply_cell(ws, row, 2, val, font=FONT_TOTAL if "IRR" in label else FONT_BODY,
                   fill=fill, border=BORDER_ALL, align=ALIGN_RIGHT, fmt=fmt)

    for i, (label, val, fmt) in enumerate(metrics[half:]):
        row = r2 + 1 + i
        alt = i % 2 == 0
        fill = FILL_GRAY if alt else None
        if "IRR" in label or "Cash-on-Cash" in label:
            if isinstance(val, float):
                fill = FILL_GREEN if val >= 0.08 else FILL_RED
        apply_cell(ws, row, 4, label, font=FONT_BODY, fill=fill, border=BORDER_ALL, align=ALIGN_LEFT)
        apply_cell(ws, row, 5, val, font=FONT_TOTAL if "IRR" in label else FONT_BODY,
                   fill=fill, border=BORDER_ALL, align=ALIGN_RIGHT, fmt=fmt)

    # DSCR threshold note
    note_row = r2 + half + 2
    apply_cell(ws, note_row, 1,
               f"✓ DSCR ≥ 1.25x is lender minimum  |  CoC target: ≥ 7%  |  IRR target: ≥ 12%",
               font=FONT_SMALL, align=ALIGN_LEFT)
    ws.merge_cells(f"A{note_row}:E{note_row}")


def build_assumptions(ws, prop: Property, assumptions: UWAssumptions):
    ws.sheet_view.showGridLines = False
    _set_col_widths(ws, {"A": 32, "B": 20, "C": 20})

    apply_cell(ws, 1, 1, "UNDERWRITING ASSUMPTIONS", font=FONT_TITLE, align=ALIGN_LEFT)
    apply_cell(ws, 1, 2, "(Yellow cells are editable inputs)", font=FONT_SMALL, align=ALIGN_LEFT)
    ws.merge_cells("A1:C1")

    sections = [
        ("PROPERTY", [
            ("Purchase Price", prop.purchase_price, FMT_DOLLAR, False),
            ("Units", prop.units, FMT_NUM, False),
            ("City / State", f"{prop.city}, {prop.state}", None, False),
        ]),
        ("FINANCING", [
            ("LTV", assumptions.ltv, FMT_PCT, True),
            ("Interest Rate", assumptions.interest_rate, FMT_PCT, True),
            ("IO Period (Years)", assumptions.io_years, FMT_NUM, True),
            ("Hold Period (Years)", assumptions.hold_years, FMT_NUM, True),
            ("Closing Cost %", assumptions.closing_cost_pct, FMT_PCT, True),
            ("Transaction Cost %", assumptions.transaction_cost_pct, FMT_PCT, True),
        ]),
        ("INCOME", [
            ("Market Rent / Unit / Month", assumptions.market_rent_per_unit or "From listing", FMT_DOLLAR if assumptions.market_rent_per_unit else None, True),
            ("Vacancy Rate", assumptions.vacancy_rate, FMT_PCT, True),
            ("Other Income / Unit / Month", assumptions.other_income_per_unit_monthly, FMT_DOLLAR_DEC, True),
            ("Rent Growth (Annual)", assumptions.rent_growth_annual, FMT_PCT, True),
        ]),
        ("OPERATING EXPENSES", [
            ("Tax Rate (% of Value)", assumptions.tax_rate_of_value, FMT_PCT, True),
            ("Insurance / Unit / Year", assumptions.insurance_per_unit, FMT_DOLLAR, True),
            ("Utilities / Unit / Month", assumptions.utilities_per_unit_monthly, FMT_DOLLAR, True),
            ("Maintenance / Unit / Year", assumptions.maintenance_per_unit, FMT_DOLLAR, True),
            ("Mgmt Fee (% of EGI)", assumptions.mgmt_pct_of_egi, FMT_PCT, True),
            ("Admin / Unit / Year", assumptions.admin_per_unit, FMT_DOLLAR, True),
            ("CapEx Reserve / Unit / Year", assumptions.capex_reserve_per_unit, FMT_DOLLAR, True),
            ("Expense Growth (Annual)", assumptions.expense_growth_annual, FMT_PCT, True),
        ]),
        ("EXIT", [
            ("Exit Cap Rate Spread (vs. Going-In)", assumptions.exit_cap_spread, FMT_PCT, True),
        ]),
    ]

    r = 3
    for section_name, rows in sections:
        style_header_row(ws, r, 1, 3)
        apply_cell(ws, r, 1, section_name, font=FONT_HEADER, fill=FILL_HEADER, align=ALIGN_LEFT, border=BORDER_ALL)
        r += 1
        for i, (label, val, fmt, is_input) in enumerate(rows):
            alt = i % 2 == 0
            fill = FILL_INPUT if is_input else (FILL_GRAY if alt else None)
            apply_cell(ws, r, 1, label, font=FONT_BODY, fill=fill, border=BORDER_ALL, align=ALIGN_LEFT)
            apply_cell(ws, r, 2, val, font=FONT_BODY, fill=fill, border=BORDER_ALL, align=ALIGN_RIGHT, fmt=fmt)
            r += 1
        r += 1


def build_income(ws, prop: Property, assumptions: UWAssumptions, results: UWResults):
    ws.sheet_view.showGridLines = False
    _set_col_widths(ws, {"A": 32, "B": 18, "C": 16, "D": 16, "E": 14})

    apply_cell(ws, 1, 1, "INCOME & REVENUE ANALYSIS", font=FONT_TITLE, align=ALIGN_LEFT)
    ws.merge_cells("A1:E1")

    # Header row
    r = 3
    headers = ["Line Item", "Annual ($)", "Per Unit ($)", "Per Month ($)", "% EGI"]
    style_header_row(ws, r, 1, 5)
    for i, h in enumerate(headers):
        apply_cell(ws, r, i + 1, h, font=FONT_HEADER, fill=FILL_HEADER, align=ALIGN_CENTER, border=BORDER_ALL)

    eff_egi = results.effective_egi
    rows = [
        ("Gross Potential Rent (GPR)", results.gpr, None),
        ("Vacancy & Credit Loss", -results.vacancy_loss, None),
        ("Effective Gross Income (EGI)", results.egi, "subtotal"),
        ("Other Income (Parking/Laundry)", results.other_income, None),
        ("Total Effective EGI", results.effective_egi, "total"),
    ]

    for i, (label, val, row_type) in enumerate(rows):
        r += 1
        alt = i % 2 == 0
        fill = FILL_TOTAL if row_type == "total" else (FILL_SUBHEADER if row_type == "subtotal" else (FILL_GRAY if alt else None))
        font = FONT_TOTAL if row_type in ("total", "subtotal") else FONT_BODY
        per_unit = val / prop.units if prop.units else 0
        per_month = val / 12
        pct_egi = val / eff_egi if eff_egi else 0

        apply_cell(ws, r, 1, label, font=font, fill=fill, border=BORDER_ALL, align=ALIGN_LEFT)
        apply_cell(ws, r, 2, val, font=font, fill=fill, border=BORDER_ALL, align=ALIGN_RIGHT, fmt=FMT_DOLLAR)
        apply_cell(ws, r, 3, per_unit, font=font, fill=fill, border=BORDER_ALL, align=ALIGN_RIGHT, fmt=FMT_DOLLAR)
        apply_cell(ws, r, 4, per_month, font=font, fill=fill, border=BORDER_ALL, align=ALIGN_RIGHT, fmt=FMT_DOLLAR)
        apply_cell(ws, r, 5, pct_egi if row_type != "total" else 1.0, font=font, fill=fill, border=BORDER_ALL, align=ALIGN_RIGHT, fmt=FMT_PCT_1)


def build_opex(ws, prop: Property, assumptions: UWAssumptions, results: UWResults):
    ws.sheet_view.showGridLines = False
    _set_col_widths(ws, {"A": 32, "B": 18, "C": 16, "D": 16, "E": 14})

    apply_cell(ws, 1, 1, "OPERATING EXPENSES", font=FONT_TITLE, align=ALIGN_LEFT)
    ws.merge_cells("A1:E1")

    r = 3
    headers = ["Expense Line", "Annual ($)", "Per Unit ($)", "Per Month ($)", "% EGI"]
    style_header_row(ws, r, 1, 5)
    for i, h in enumerate(headers):
        apply_cell(ws, r, i + 1, h, font=FONT_HEADER, fill=FILL_HEADER, align=ALIGN_CENTER, border=BORDER_ALL)

    eff_egi = results.effective_egi
    opex_rows = [
        ("Property Taxes", results.taxes),
        ("Insurance", results.insurance),
        ("Utilities (Common Area)", results.utilities),
        ("Maintenance & Repairs", results.maintenance),
        ("Property Management", results.mgmt),
        ("Admin / Legal / Accounting", results.admin),
        ("Capital Expenditure Reserve", results.capex),
    ]

    for i, (label, val) in enumerate(opex_rows):
        r += 1
        alt = i % 2 == 0
        fill = FILL_GRAY if alt else None
        per_unit = val / prop.units if prop.units else 0
        per_month = val / 12
        pct_egi = val / eff_egi if eff_egi else 0
        apply_cell(ws, r, 1, label, font=FONT_BODY, fill=fill, border=BORDER_ALL, align=ALIGN_LEFT)
        apply_cell(ws, r, 2, val, font=FONT_BODY, fill=fill, border=BORDER_ALL, align=ALIGN_RIGHT, fmt=FMT_DOLLAR)
        apply_cell(ws, r, 3, per_unit, font=FONT_BODY, fill=fill, border=BORDER_ALL, align=ALIGN_RIGHT, fmt=FMT_DOLLAR)
        apply_cell(ws, r, 4, per_month, font=FONT_BODY, fill=fill, border=BORDER_ALL, align=ALIGN_RIGHT, fmt=FMT_DOLLAR)
        apply_cell(ws, r, 5, pct_egi, font=FONT_BODY, fill=fill, border=BORDER_ALL, align=ALIGN_RIGHT, fmt=FMT_PCT_1)

    # Total OpEx
    r += 1
    style_total_row(ws, r, 1, 5)
    total_per_unit = results.total_opex / prop.units if prop.units else 0
    apply_cell(ws, r, 1, "Total Operating Expenses", font=FONT_TOTAL, fill=FILL_TOTAL, border=BORDER_ALL, align=ALIGN_LEFT)
    apply_cell(ws, r, 2, results.total_opex, font=FONT_TOTAL, fill=FILL_TOTAL, border=BORDER_ALL, align=ALIGN_RIGHT, fmt=FMT_DOLLAR)
    apply_cell(ws, r, 3, total_per_unit, font=FONT_TOTAL, fill=FILL_TOTAL, border=BORDER_ALL, align=ALIGN_RIGHT, fmt=FMT_DOLLAR)
    apply_cell(ws, r, 4, results.total_opex / 12, font=FONT_TOTAL, fill=FILL_TOTAL, border=BORDER_ALL, align=ALIGN_RIGHT, fmt=FMT_DOLLAR)
    apply_cell(ws, r, 5, results.total_opex / eff_egi if eff_egi else 0, font=FONT_TOTAL, fill=FILL_TOTAL, border=BORDER_ALL, align=ALIGN_RIGHT, fmt=FMT_PCT_1)

    # NOI
    r += 1
    style_header_row(ws, r, 1, 5)
    noi_per_unit = results.noi / prop.units if prop.units else 0
    apply_cell(ws, r, 1, "Net Operating Income (NOI)", font=FONT_HEADER, fill=FILL_HEADER, border=BORDER_ALL, align=ALIGN_LEFT)
    apply_cell(ws, r, 2, results.noi, font=FONT_HEADER, fill=FILL_HEADER, border=BORDER_ALL, align=ALIGN_RIGHT, fmt=FMT_DOLLAR)
    apply_cell(ws, r, 3, noi_per_unit, font=FONT_HEADER, fill=FILL_HEADER, border=BORDER_ALL, align=ALIGN_RIGHT, fmt=FMT_DOLLAR)
    apply_cell(ws, r, 4, results.noi / 12, font=FONT_HEADER, fill=FILL_HEADER, border=BORDER_ALL, align=ALIGN_RIGHT, fmt=FMT_DOLLAR)
    apply_cell(ws, r, 5, results.noi / eff_egi if eff_egi else 0, font=FONT_HEADER, fill=FILL_HEADER, border=BORDER_ALL, align=ALIGN_RIGHT, fmt=FMT_PCT_1)

    # Cap rate callout
    r += 2
    apply_cell(ws, r, 1, f"Going-In Cap Rate:", font=FONT_SUBHEADER, align=ALIGN_LEFT)
    apply_cell(ws, r, 2, results.going_in_cap_rate, font=FONT_METRIC, align=ALIGN_RIGHT, fmt=FMT_PCT_1)


def build_debt_schedule(ws, prop: Property, assumptions: UWAssumptions, results: UWResults):
    ws.sheet_view.showGridLines = False
    _set_col_widths(ws, {"A": 10, "B": 14, "C": 14, "D": 14, "E": 14, "F": 14, "G": 14, "H": 16})

    apply_cell(ws, 1, 1, "DEBT SCHEDULE — 7/1 IO ARM", font=FONT_TITLE, align=ALIGN_LEFT)
    ws.merge_cells("A1:H1")

    # Loan summary
    r = 3
    loan_info = [
        ("Loan Amount", results.loan_amount, FMT_DOLLAR),
        ("LTV", assumptions.ltv, FMT_PCT),
        ("Interest Rate", assumptions.interest_rate, FMT_PCT),
        ("Structure", "7/1 Interest-Only ARM", None),
        ("IO Period", f"{assumptions.io_years} Years", None),
        ("Annual IO Payment", results.annual_ds_io, FMT_DOLLAR),
        ("Monthly IO Payment", results.annual_ds_io / 12, FMT_DOLLAR),
    ]
    for i, (label, val, fmt) in enumerate(loan_info):
        alt = i % 2 == 0
        fill = FILL_GRAY if alt else None
        apply_cell(ws, r, 1, label, font=FONT_BODY, fill=fill, border=BORDER_ALL, align=ALIGN_LEFT)
        apply_cell(ws, r, 2, val, font=FONT_BODY, fill=fill, border=BORDER_ALL, align=ALIGN_RIGHT, fmt=fmt)
        ws.merge_cells(f"A{r}:A{r}")
        r += 1

    r += 1
    headers = ["Year", "Period", "Interest", "Principal", "Debt Service", "Loan Balance", "DSCR", "Net Cash Flow"]
    style_header_row(ws, r, 1, 8)
    for i, h in enumerate(headers):
        apply_cell(ws, r, i + 1, h, font=FONT_HEADER, fill=FILL_HEADER, align=ALIGN_CENTER, border=BORDER_ALL)

    loan = results.loan_amount
    rate = assumptions.interest_rate

    from underwriting.cashflow import _monthly_am_payment
    am_monthly = _monthly_am_payment(loan, rate, 360)
    am_annual = am_monthly * 12

    yearly = results.yearly_metrics
    for ym in yearly:
        r += 1
        yr = ym["year"]
        is_io = ym["is_io"]
        noi = ym["noi"]
        ncf = ym["net_cash_flow"]
        ds = ym["debt_service"]
        interest = loan * rate if is_io else (ds - (am_monthly * 12 - loan * rate))
        principal = 0.0 if is_io else (am_monthly * 12 - loan * rate)
        dscr = noi / ds if ds else 0.0
        period = "Interest Only" if is_io else "Amortizing"
        alt = yr % 2 == 0
        fill = FILL_GRAY if alt else None
        # Highlight IO period
        if is_io:
            from openpyxl.styles import PatternFill
            fill = PatternFill("solid", fgColor="EBF3FB")

        apply_cell(ws, r, 1, yr, font=FONT_BODY, fill=fill, border=BORDER_ALL, align=ALIGN_CENTER)
        apply_cell(ws, r, 2, period, font=FONT_BODY, fill=fill, border=BORDER_ALL, align=ALIGN_CENTER)
        apply_cell(ws, r, 3, interest, font=FONT_BODY, fill=fill, border=BORDER_ALL, align=ALIGN_RIGHT, fmt=FMT_DOLLAR)
        apply_cell(ws, r, 4, principal, font=FONT_BODY, fill=fill, border=BORDER_ALL, align=ALIGN_RIGHT, fmt=FMT_DOLLAR)
        apply_cell(ws, r, 5, ds, font=FONT_BODY, fill=fill, border=BORDER_ALL, align=ALIGN_RIGHT, fmt=FMT_DOLLAR)
        apply_cell(ws, r, 6, loan, font=FONT_BODY, fill=fill, border=BORDER_ALL, align=ALIGN_RIGHT, fmt=FMT_DOLLAR)
        dscr_fill = FILL_GREEN if dscr >= 1.25 else FILL_RED
        apply_cell(ws, r, 7, dscr, font=FONT_BODY, fill=dscr_fill, border=BORDER_ALL, align=ALIGN_RIGHT, fmt="0.00x")
        apply_cell(ws, r, 8, ncf, font=FONT_BODY, fill=fill, border=BORDER_ALL, align=ALIGN_RIGHT, fmt=FMT_DOLLAR)

        if not is_io:
            loan = max(0.0, loan - principal)


def build_returns(ws, prop: Property, assumptions: UWAssumptions, results: UWResults):
    ws.sheet_view.showGridLines = False

    hold = len(results.yearly_metrics)
    col_count = hold + 1
    widths = {"A": 30}
    for i in range(1, hold + 1):
        widths[get_column_letter(i + 1)] = 14
    _set_col_widths(ws, widths)

    apply_cell(ws, 1, 1, "10-YEAR CASH FLOW & RETURNS", font=FONT_TITLE, align=ALIGN_LEFT)
    ws.merge_cells(f"A1:{get_column_letter(col_count + 1)}1")

    # Header row: Year 0, Year 1 .. Year N
    r = 3
    style_header_row(ws, r, 1, col_count + 1)
    apply_cell(ws, r, 1, "Line Item", font=FONT_HEADER, fill=FILL_HEADER, align=ALIGN_LEFT, border=BORDER_ALL)
    for yr in range(1, hold + 1):
        apply_cell(ws, r, yr + 1, f"Year {yr}", font=FONT_HEADER, fill=FILL_HEADER, align=ALIGN_CENTER, border=BORDER_ALL)

    def data_row(label, values, fmt, row_type="normal", row_num=None):
        nonlocal r
        r += 1
        alt = (r % 2 == 0)
        if row_type == "header":
            fill, font = FILL_SUBHEADER, FONT_SUBHEADER
        elif row_type == "total":
            fill, font = FILL_TOTAL, FONT_TOTAL
        elif row_type == "section":
            fill, font = FILL_HEADER, FONT_HEADER
        else:
            fill = FILL_GRAY if alt else None
            font = FONT_BODY
        apply_cell(ws, r, 1, label, font=font, fill=fill, border=BORDER_ALL, align=ALIGN_LEFT)
        for i, v in enumerate(values):
            apply_cell(ws, r, i + 2, v, font=font, fill=fill, border=BORDER_ALL, align=ALIGN_RIGHT, fmt=fmt)

    ym_list = results.yearly_metrics

    data_row("REVENUE", [""] * hold, None, "section")
    data_row("Gross Potential Rent", [y["gpr"] for y in ym_list], FMT_DOLLAR)
    data_row("Vacancy Loss", [-y["vacancy_loss"] for y in ym_list], FMT_DOLLAR)
    data_row("Effective Gross Income", [y["egi"] for y in ym_list], FMT_DOLLAR, "header")
    data_row("Other Income", [y["other_income"] for y in ym_list], FMT_DOLLAR)
    data_row("Total Revenue", [y["effective_egi"] for y in ym_list], FMT_DOLLAR, "total")

    data_row("OPERATING EXPENSES", [""] * hold, None, "section")
    data_row("Property Taxes", [y["taxes"] for y in ym_list], FMT_DOLLAR)
    data_row("Insurance", [y["insurance"] for y in ym_list], FMT_DOLLAR)
    data_row("Utilities", [y["utilities"] for y in ym_list], FMT_DOLLAR)
    data_row("Maintenance", [y["maintenance"] for y in ym_list], FMT_DOLLAR)
    data_row("Property Management", [y["mgmt"] for y in ym_list], FMT_DOLLAR)
    data_row("Admin / Legal", [y["admin"] for y in ym_list], FMT_DOLLAR)
    data_row("CapEx Reserve", [y["capex"] for y in ym_list], FMT_DOLLAR)
    data_row("Total OpEx", [y["total_opex"] for y in ym_list], FMT_DOLLAR, "total")

    data_row("NET OPERATING INCOME", [y["noi"] for y in ym_list], FMT_DOLLAR, "section")
    data_row("Cap Rate (going-in basis)", [y["noi"] / prop.purchase_price for y in ym_list], FMT_PCT_1)

    data_row("DEBT SERVICE", [""] * hold, None, "section")
    data_row("Annual Debt Service", [y["debt_service"] for y in ym_list], FMT_DOLLAR)
    data_row("Period", ["IO" if y["is_io"] else "Am" for y in ym_list], None)

    data_row("NET CASH FLOW", [y["net_cash_flow"] for y in ym_list], FMT_DOLLAR, "section")
    data_row("DSCR", [y["noi"] / y["debt_service"] if y["debt_service"] else 0 for y in ym_list], "0.00x")

    # Cash flows + returns summary
    r += 2
    apply_cell(ws, r, 1, "RETURN SUMMARY", font=FONT_TITLE, align=ALIGN_LEFT)
    r += 1
    return_rows = [
        ("5-Year IRR", results.irr_5yr, FMT_PCT_1),
        ("10-Year IRR", results.irr_10yr, FMT_PCT_1),
        ("5-Year Equity Multiple", results.equity_multiple_5yr, FMT_MULT),
        ("10-Year Equity Multiple", results.equity_multiple_10yr, FMT_MULT),
        ("Year 1 Cash-on-Cash", results.coc_y1, FMT_PCT_1),
        ("Equity Invested", results.equity_invested, FMT_DOLLAR),
        ("Exit Price", results.exit_price, FMT_DOLLAR),
        ("Exit Cap Rate", results.exit_cap_rate, FMT_PCT_1),
    ]
    for i, (label, val, fmt) in enumerate(return_rows):
        alt = i % 2 == 0
        fill = FILL_GRAY if alt else None
        if "IRR" in label and isinstance(val, float):
            fill = FILL_GREEN if val >= 0.12 else FILL_RED
        apply_cell(ws, r, 1, label, font=FONT_BODY, fill=fill, border=BORDER_ALL, align=ALIGN_LEFT)
        apply_cell(ws, r, 2, val, font=FONT_TOTAL, fill=fill, border=BORDER_ALL, align=ALIGN_RIGHT, fmt=fmt)
        r += 1


def build_sensitivity(ws, prop: Property, assumptions: UWAssumptions, results: UWResults):
    ws.sheet_view.showGridLines = False
    _set_col_widths(ws, {"A": 22, "B": 12, "C": 12, "D": 12, "E": 12, "F": 12, "G": 12})

    apply_cell(ws, 1, 1, "SENSITIVITY ANALYSIS", font=FONT_TITLE, align=ALIGN_LEFT)
    ws.merge_cells("A1:G1")

    from underwriting.engine import underwrite
    from underwriting.assumptions import assumptions_from_dict

    def _quick_uw(overrides: dict) -> UWResults:
        a = assumptions_from_dict({**assumptions.model_dump(), **overrides})
        return underwrite(prop, a)

    # ── Grid 1: CoC Year 1 vs Vacancy × Rent (% of base) ────────────────
    r = 3
    apply_cell(ws, r, 1, "Year 1 Cash-on-Cash vs. Vacancy Rate & Rent Level", font=FONT_SUBHEADER, align=ALIGN_LEFT)
    ws.merge_cells(f"A{r}:G{r}")
    r += 1

    vacancies = [0.03, 0.05, 0.08, 0.10, 0.15]
    rent_changes = [-0.10, -0.05, 0.00, 0.05, 0.10]
    base_rent = assumptions.market_rent_per_unit or (prop.monthly_rent_total / prop.units if prop.monthly_rent_total else None)

    # Header row
    apply_cell(ws, r, 1, "Vacancy →", font=FONT_SUBHEADER, fill=FILL_SUBHEADER, border=BORDER_ALL, align=ALIGN_CENTER)
    for j, v in enumerate(vacancies):
        apply_cell(ws, r, j + 2, f"{v:.0%}", font=FONT_SUBHEADER, fill=FILL_SUBHEADER, border=BORDER_ALL, align=ALIGN_CENTER)
    r += 1

    for rc in rent_changes:
        apply_cell(ws, r, 1, f"Rent {rc:+.0%}", font=FONT_BODY, fill=FILL_GRAY, border=BORDER_ALL, align=ALIGN_CENTER)
        for j, v in enumerate(vacancies):
            overrides = {"vacancy_rate": v}
            if base_rent:
                overrides["market_rent_per_unit"] = base_rent * (1 + rc)
            res = _quick_uw(overrides)
            coc = res.coc_y1
            fill = FILL_GREEN if coc >= 0.07 else FILL_RED
            apply_cell(ws, r, j + 2, coc, font=FONT_BODY, fill=fill, border=BORDER_ALL, align=ALIGN_CENTER, fmt=FMT_PCT_1)
        r += 1

    # ── Grid 2: 5yr IRR vs Entry Cap × Exit Cap ───────────────────────────
    r += 2
    apply_cell(ws, r, 1, "5-Year IRR vs. Entry Cap Rate & Exit Cap Rate", font=FONT_SUBHEADER, align=ALIGN_LEFT)
    ws.merge_cells(f"A{r}:G{r}")
    r += 1

    going_in = results.going_in_cap_rate
    entry_caps = [going_in - 0.01, going_in - 0.005, going_in, going_in + 0.005, going_in + 0.01]
    exit_spreads = [-0.005, 0.0, 0.0025, 0.005, 0.01]

    apply_cell(ws, r, 1, "Exit Spread →", font=FONT_SUBHEADER, fill=FILL_SUBHEADER, border=BORDER_ALL, align=ALIGN_CENTER)
    for j, es in enumerate(exit_spreads):
        apply_cell(ws, r, j + 2, f"{es:+.2%}", font=FONT_SUBHEADER, fill=FILL_SUBHEADER, border=BORDER_ALL, align=ALIGN_CENTER)
    r += 1

    for ec in entry_caps:
        label = f"Entry {ec:.2%}"
        apply_cell(ws, r, 1, label, font=FONT_BODY, fill=FILL_GRAY, border=BORDER_ALL, align=ALIGN_CENTER)
        for j, es in enumerate(exit_spreads):
            implied_pp = results.noi / ec if ec > 0 else prop.purchase_price
            overrides = {"exit_cap_spread": es}
            test_prop = prop.model_copy(update={"purchase_price": implied_pp})
            try:
                res = underwrite(test_prop, assumptions_from_dict({**assumptions.model_dump(), **overrides}))
                irr = res.irr_5yr
                fill = FILL_GREEN if irr and irr >= 0.12 else FILL_RED
                apply_cell(ws, r, j + 2, irr, font=FONT_BODY, fill=fill, border=BORDER_ALL, align=ALIGN_CENTER, fmt=FMT_PCT_1)
            except Exception:
                apply_cell(ws, r, j + 2, "N/A", font=FONT_BODY, border=BORDER_ALL, align=ALIGN_CENTER)
        r += 1

    # ── Grid 3: DSCR vs Purchase Price × NOI ─────────────────────────────
    r += 2
    apply_cell(ws, r, 1, "DSCR vs. Purchase Price Variance", font=FONT_SUBHEADER, align=ALIGN_LEFT)
    ws.merge_cells(f"A{r}:G{r}")
    r += 1

    price_changes = [-0.10, -0.05, 0.00, 0.05, 0.10]
    noi_changes = [-0.10, -0.05, 0.00, 0.05, 0.10]

    apply_cell(ws, r, 1, "NOI Δ →", font=FONT_SUBHEADER, fill=FILL_SUBHEADER, border=BORDER_ALL, align=ALIGN_CENTER)
    for j, nc in enumerate(noi_changes):
        apply_cell(ws, r, j + 2, f"NOI {nc:+.0%}", font=FONT_SUBHEADER, fill=FILL_SUBHEADER, border=BORDER_ALL, align=ALIGN_CENTER)
    r += 1

    for pc in price_changes:
        label = f"Price {pc:+.0%}"
        apply_cell(ws, r, 1, label, font=FONT_BODY, fill=FILL_GRAY, border=BORDER_ALL, align=ALIGN_CENTER)
        for j, nc in enumerate(noi_changes):
            new_price = prop.purchase_price * (1 + pc)
            new_noi = results.noi * (1 + nc)
            new_loan = new_price * assumptions.ltv
            ds = new_loan * assumptions.interest_rate
            dscr = new_noi / ds if ds else 0.0
            fill = FILL_GREEN if dscr >= 1.25 else FILL_RED
            apply_cell(ws, r, j + 2, dscr, font=FONT_BODY, fill=fill, border=BORDER_ALL, align=ALIGN_CENTER, fmt="0.00x")
        r += 1

    # Legend
    r += 2
    from openpyxl.styles import PatternFill, Font
    apply_cell(ws, r, 1, "■ Green = meets target threshold     ■ Red = below target", font=FONT_SMALL, align=ALIGN_LEFT)
    ws.merge_cells(f"A{r}:G{r}")
    apply_cell(ws, r + 1, 1, "Targets: CoC ≥ 7%  |  IRR ≥ 12%  |  DSCR ≥ 1.25x", font=FONT_SMALL, align=ALIGN_LEFT)
    ws.merge_cells(f"A{r+1}:G{r+1}")
