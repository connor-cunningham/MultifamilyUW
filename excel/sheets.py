"""
Formula-based Excel sheet builders.

All calculated cells use Excel formula strings rather than hard-coded Python
values. The Assumptions sheet has a fixed cell layout (column B, known rows)
so every other sheet can cross-reference it with stable addresses.
"""
from datetime import datetime
from openpyxl.utils import get_column_letter

from models.property import Property
from models.underwriting import UWAssumptions, UWResults
from excel.styles import (
    apply_cell, style_header_row, style_total_row,
    FILL_HEADER, FILL_SUBHEADER, FILL_INPUT, FILL_GREEN, FILL_RED,
    FILL_GRAY, FILL_TOTAL, FILL_ALT,
    FONT_TITLE, FONT_HEADER, FONT_SUBHEADER, FONT_BODY, FONT_TOTAL,
    FONT_METRIC, FONT_SMALL,
    ALIGN_CENTER, ALIGN_LEFT, ALIGN_RIGHT,
    BORDER_ALL,
    FMT_DOLLAR, FMT_DOLLAR_DEC, FMT_PCT, FMT_PCT_1, FMT_NUM, FMT_MULT,
)

# ── Assumptions sheet — fixed row positions (column B holds values) ────────
_A = "'2. Assumptions'"  # sheet name for cross-sheet refs

# Property
R_PP    = 5   # Purchase Price
R_UNITS = 6   # Units

# Financing
R_LTV        = 10
R_RATE       = 11
R_IO_YRS     = 12
R_HOLD_YRS   = 13
R_CLOSE_COST = 14
R_TRANS_COST = 15

# Income
R_RENT      = 18
R_VAC       = 19
R_OTHER     = 20
R_RENT_GRW  = 21

# Expenses
R_TAX     = 24
R_INS     = 25
R_UTIL    = 26
R_MAINT   = 27
R_MGMT    = 28
R_ADMIN   = 29
R_CAPEX   = 30
R_EXP_GRW = 31

# Exit
R_EXIT_SPR = 34

# Derived (these rows contain formulas in the Assumptions sheet itself)
R_LOAN   = 37   # =B5*B10
R_EQUITY = 38   # =B5*(1-B10)*(1+B14)
R_IO_DS  = 39   # =B37*B11
R_MTH_DS = 40   # =B39/12


def a(row: int) -> str:
    """Cross-sheet reference to Assumptions column B at given row."""
    return f"{_A}!B{row}"


# ── Returns sheet — fixed row positions ───────────────────────────────────
R_YR_ROW  = 3   # year numbers: 1, 2, …, N
R_GPR     = 6
R_VAC_R   = 7
R_EGI     = 8
R_OTHER_R = 9
R_REV     = 10
R_TAX_R   = 13
R_INS_R   = 14
R_UTIL_R  = 15
R_MAINT_R = 16
R_MGMT_R  = 17
R_ADMIN_R = 18
R_CAPEX_R = 19
R_OPEX    = 20
R_NOI     = 22
R_CAP_R   = 23
R_DS      = 26
R_PERIOD  = 27
R_NCF     = 29
R_DSCR    = 30
R_LNBAL   = 33
R_EXIT5   = 35   # exit proceeds if sold at year 5
R_EXIT10  = 36   # exit proceeds if sold at hold_years
R_IRR5    = 38   # cash-flow row for 5-yr IRR  (col A = yr0, B-F = yr1-5)
R_IRR10   = 39   # cash-flow row for 10-yr IRR (col A = yr0, B-K = yr1-10)


def _set_col_widths(ws, widths: dict):
    for col_letter, width in widths.items():
        ws.column_dimensions[col_letter].width = width


# ══════════════════════════════════════════════════════════════════════════
# Sheet 1 — Summary
# ══════════════════════════════════════════════════════════════════════════
def build_summary(ws, prop: Property, assumptions: UWAssumptions, results: UWResults):
    ws.sheet_view.showGridLines = False
    _set_col_widths(ws, {"A": 30, "B": 20, "C": 4, "D": 30, "E": 20})

    # Title
    ws.row_dimensions[1].height = 30
    apply_cell(ws, 1, 1, f"DEAL SUMMARY — {prop.address.upper()}",
               font=FONT_TITLE, align=ALIGN_LEFT)
    ws.merge_cells("A1:E1")
    apply_cell(ws, 2, 1,
               f"{prop.city}, {prop.state}  |  {prop.units} Units  |  {prop.year_built or 'N/A'} Built",
               font=FONT_SUBHEADER, align=ALIGN_LEFT)
    ws.merge_cells("A2:E2")
    apply_cell(ws, 3, 1,
               f"Analyzed: {datetime.now().strftime('%B %d, %Y')}  |  Source: {prop.source.upper()}",
               font=FONT_SMALL, align=ALIGN_LEFT)
    ws.merge_cells("A3:E3")

    # ── Left: Property & Pricing ──
    r = 5
    apply_cell(ws, r, 1, "PROPERTY", font=FONT_HEADER, fill=FILL_HEADER, align=ALIGN_CENTER, border=BORDER_ALL)
    apply_cell(ws, r, 2, "", fill=FILL_HEADER, border=BORDER_ALL)
    ws.merge_cells(f"A{r}:B{r}")

    prop_rows = [
        ("Purchase Price",  f"={a(R_PP)}",             FMT_DOLLAR),
        ("Units",           f"={a(R_UNITS)}",           FMT_NUM),
        ("Price / Unit",    f"={a(R_PP)}/{a(R_UNITS)}", FMT_DOLLAR),
        ("Price / SF",      prop.price_per_sqft,        FMT_DOLLAR_DEC),
        ("Year Built",      prop.year_built,            None),
        ("SF (Total)",      prop.sqft,                  FMT_NUM),
        ("State",           prop.state,                 None),
    ]
    for i, (label, val, fmt) in enumerate(prop_rows):
        row = r + 1 + i
        fill = FILL_GRAY if i % 2 == 0 else None
        apply_cell(ws, row, 1, label, font=FONT_BODY, fill=fill, border=BORDER_ALL, align=ALIGN_LEFT)
        apply_cell(ws, row, 2, val,   font=FONT_BODY, fill=fill, border=BORDER_ALL, align=ALIGN_RIGHT, fmt=fmt)

    # ── Right: Financing ──
    apply_cell(ws, r, 4, "FINANCING", font=FONT_HEADER, fill=FILL_HEADER, align=ALIGN_CENTER, border=BORDER_ALL)
    apply_cell(ws, r, 5, "", fill=FILL_HEADER, border=BORDER_ALL)
    ws.merge_cells(f"D{r}:E{r}")

    fin_rows = [
        ("Loan Amount",       f"={a(R_LOAN)}",   FMT_DOLLAR),
        ("LTV",               f"={a(R_LTV)}",    FMT_PCT_1),
        ("Interest Rate",     f"={a(R_RATE)}",   FMT_PCT),
        ("Structure",         "7/1 Interest-Only ARM", None),
        ("IO Period",         f'={a(R_IO_YRS)}&" Years"', None),
        ("Annual IO Payment", f"={a(R_IO_DS)}",  FMT_DOLLAR),
        ("Equity Invested",   f"={a(R_EQUITY)}", FMT_DOLLAR),
    ]
    for i, (label, val, fmt) in enumerate(fin_rows):
        row = r + 1 + i
        fill = FILL_GRAY if i % 2 == 0 else None
        apply_cell(ws, row, 4, label, font=FONT_BODY, fill=fill, border=BORDER_ALL, align=ALIGN_LEFT)
        apply_cell(ws, row, 5, val,   font=FONT_BODY, fill=fill, border=BORDER_ALL, align=ALIGN_RIGHT, fmt=fmt)

    # ── Returns metrics ──
    r2 = r + len(prop_rows) + 2
    apply_cell(ws, r2, 1, "KEY RETURNS", font=FONT_HEADER, fill=FILL_HEADER, align=ALIGN_CENTER, border=BORDER_ALL)
    for c in range(2, 6):
        apply_cell(ws, r2, c, "", fill=FILL_HEADER, border=BORDER_ALL)
    ws.merge_cells(f"A{r2}:E{r2}")

    # Reference the Returns sheet for live formula metrics
    ret = "'6. Returns'"
    opx = "'4. OpEx'"
    metrics_left = [
        ("Going-In Cap Rate",     f"={opx}!B14",                              FMT_PCT_1),
        ("Year 1 Cash-on-Cash",   f"={ret}!B{R_NCF}/{a(R_EQUITY)}",           FMT_PCT_1),
        ("DSCR (Year 1)",         f"={ret}!B{R_DSCR}",                        "0.00x"),
        ("NOI (Year 1)",          f"={opx}!B13",                              FMT_DOLLAR),
        ("Annual Debt Service",   f"={a(R_IO_DS)}",                           FMT_DOLLAR),
    ]
    metrics_right = [
        ("5-Year IRR",            f"=IFERROR(IRR(A{R_IRR5}:{get_column_letter(6)}{R_IRR5}),\"N/A\")", FMT_PCT_1),
        ("10-Year IRR",           f"=IFERROR(IRR(A{R_IRR10}:{get_column_letter(11)}{R_IRR10}),\"N/A\")", FMT_PCT_1),
        ("5-Year Equity Multiple",f"=IFERROR(SUM(B{R_IRR5}:{get_column_letter(6)}{R_IRR5})/ABS(A{R_IRR5}),\"N/A\")", FMT_MULT),
        ("10-Year Equity Multiple",f"=IFERROR(SUM(B{R_IRR10}:{get_column_letter(11)}{R_IRR10})/ABS(A{R_IRR10}),\"N/A\")", FMT_MULT),
        ("Exit Cap Rate",         f"={ret}!B{R_CAP_R}+{a(R_EXIT_SPR)}",       FMT_PCT_1),
    ]

    # IRR formulas reference the Returns sheet
    irr_ret = f"'{ws.parent['6. Returns'].title}'" if '6. Returns' in (ws.parent.sheetnames if ws.parent else []) else ret

    for i, (label, val, fmt) in enumerate(metrics_left):
        row = r2 + 1 + i
        fill = FILL_GRAY if i % 2 == 0 else None
        apply_cell(ws, row, 1, label, font=FONT_BODY, fill=fill, border=BORDER_ALL, align=ALIGN_LEFT)
        apply_cell(ws, row, 2, val,   font=FONT_TOTAL, fill=fill, border=BORDER_ALL, align=ALIGN_RIGHT, fmt=fmt)

    for i, (label, val, fmt) in enumerate(metrics_right):
        row = r2 + 1 + i
        fill = FILL_GRAY if i % 2 == 0 else None
        irr_fill = fill
        if "IRR" in label:
            irr_fill = None  # will be set by conditional formatting hint
        apply_cell(ws, row, 4, label, font=FONT_BODY, fill=irr_fill, border=BORDER_ALL, align=ALIGN_LEFT)
        apply_cell(ws, row, 5, val,   font=FONT_TOTAL, fill=irr_fill, border=BORDER_ALL, align=ALIGN_RIGHT, fmt=fmt)

    note_row = r2 + max(len(metrics_left), len(metrics_right)) + 2
    apply_cell(ws, note_row, 1,
               "Targets: Cap Rate ≥ 6%  |  DSCR ≥ 1.25x  |  CoC ≥ 7%  |  5yr IRR ≥ 12%",
               font=FONT_SMALL, align=ALIGN_LEFT)
    ws.merge_cells(f"A{note_row}:E{note_row}")


# ══════════════════════════════════════════════════════════════════════════
# Sheet 2 — Assumptions
# ══════════════════════════════════════════════════════════════════════════
def build_assumptions(ws, prop: Property, assumptions: UWAssumptions):
    ws.sheet_view.showGridLines = False
    _set_col_widths(ws, {"A": 34, "B": 22})

    apply_cell(ws, 1, 1, "UNDERWRITING ASSUMPTIONS", font=FONT_TITLE, align=ALIGN_LEFT)
    apply_cell(ws, 2, 1, "Yellow = editable inputs.  Change any value — all other sheets update automatically.",
               font=FONT_SMALL, align=ALIGN_LEFT)
    ws.merge_cells("A1:B1")
    ws.merge_cells("A2:B2")

    # Resolve market rent
    rent_val = assumptions.market_rent_per_unit
    if not rent_val and prop.monthly_rent_total and prop.units:
        rent_val = prop.monthly_rent_total / prop.units
    if not rent_val:
        rent_val = (prop.purchase_price / prop.units * 0.07) / 12

    sections = [
        ("PROPERTY", [
            (R_PP,    "Purchase Price",           prop.purchase_price,              FMT_DOLLAR,     False),
            (R_UNITS, "Units",                    prop.units,                        FMT_NUM,        False),
            (None,    "City / State",             f"{prop.city}, {prop.state}",     None,           False),
        ]),
        ("FINANCING", [
            (R_LTV,        "LTV",                         assumptions.ltv,                    FMT_PCT,    True),
            (R_RATE,       "Interest Rate",               assumptions.interest_rate,          FMT_PCT,    True),
            (R_IO_YRS,     "IO Period (Years)",           assumptions.io_years,               FMT_NUM,    True),
            (R_HOLD_YRS,   "Hold Period (Years)",         assumptions.hold_years,             FMT_NUM,    True),
            (R_CLOSE_COST, "Closing Cost %",              assumptions.closing_cost_pct,       FMT_PCT,    True),
            (R_TRANS_COST, "Transaction Cost %",          assumptions.transaction_cost_pct,   FMT_PCT,    True),
        ]),
        ("INCOME", [
            (R_RENT,     "Market Rent / Unit / Month",  rent_val,                           FMT_DOLLAR, True),
            (R_VAC,      "Vacancy Rate",                assumptions.vacancy_rate,            FMT_PCT,    True),
            (R_OTHER,    "Other Income / Unit / Month", assumptions.other_income_per_unit_monthly, FMT_DOLLAR_DEC, True),
            (R_RENT_GRW, "Rent Growth (Annual)",        assumptions.rent_growth_annual,      FMT_PCT,    True),
        ]),
        ("OPERATING EXPENSES", [
            (R_TAX,     "Tax Rate (% of Value/Year)",  assumptions.tax_rate_of_value,       FMT_PCT,    True),
            (R_INS,     "Insurance / Unit / Year",     assumptions.insurance_per_unit,      FMT_DOLLAR, True),
            (R_UTIL,    "Utilities / Unit / Month",    assumptions.utilities_per_unit_monthly, FMT_DOLLAR, True),
            (R_MAINT,   "Maintenance / Unit / Year",   assumptions.maintenance_per_unit,    FMT_DOLLAR, True),
            (R_MGMT,    "Property Mgmt (% of EGI)",    assumptions.mgmt_pct_of_egi,         FMT_PCT,    True),
            (R_ADMIN,   "Admin / Unit / Year",         assumptions.admin_per_unit,          FMT_DOLLAR, True),
            (R_CAPEX,   "CapEx Reserve / Unit / Year", assumptions.capex_reserve_per_unit,  FMT_DOLLAR, True),
            (R_EXP_GRW, "Expense Growth (Annual)",     assumptions.expense_growth_annual,   FMT_PCT,    True),
        ]),
        ("EXIT", [
            (R_EXIT_SPR, "Exit Cap Spread (vs. Going-In)", assumptions.exit_cap_spread, FMT_PCT, True),
        ]),
    ]

    # Write sections with exact row tracking
    # We pre-assign rows to match the R_* constants defined above
    row_map = {
        R_PP: prop.purchase_price, R_UNITS: prop.units,
        R_LTV: assumptions.ltv, R_RATE: assumptions.interest_rate,
        R_IO_YRS: assumptions.io_years, R_HOLD_YRS: assumptions.hold_years,
        R_CLOSE_COST: assumptions.closing_cost_pct, R_TRANS_COST: assumptions.transaction_cost_pct,
        R_RENT: rent_val, R_VAC: assumptions.vacancy_rate,
        R_OTHER: assumptions.other_income_per_unit_monthly, R_RENT_GRW: assumptions.rent_growth_annual,
        R_TAX: assumptions.tax_rate_of_value, R_INS: assumptions.insurance_per_unit,
        R_UTIL: assumptions.utilities_per_unit_monthly, R_MAINT: assumptions.maintenance_per_unit,
        R_MGMT: assumptions.mgmt_pct_of_egi, R_ADMIN: assumptions.admin_per_unit,
        R_CAPEX: assumptions.capex_reserve_per_unit, R_EXP_GRW: assumptions.expense_growth_annual,
        R_EXIT_SPR: assumptions.exit_cap_spread,
    }

    for section_name, rows in sections:
        # Find the header row for this section
        first_row_num = next((r for r, *_ in rows if r is not None), None)
        if first_row_num is None:
            continue
        hdr_row = first_row_num - 1
        style_header_row(ws, hdr_row, 1, 2)
        apply_cell(ws, hdr_row, 1, section_name, font=FONT_HEADER, fill=FILL_HEADER,
                   align=ALIGN_LEFT, border=BORDER_ALL)

        for i, (row_num, label, val, fmt, is_input) in enumerate(rows):
            target_row = row_num if row_num else (hdr_row + 1 + i)
            fill = FILL_INPUT if is_input else (FILL_GRAY if i % 2 == 0 else None)
            apply_cell(ws, target_row, 1, label, font=FONT_BODY, fill=fill, border=BORDER_ALL, align=ALIGN_LEFT)
            apply_cell(ws, target_row, 2, val,   font=FONT_BODY, fill=fill, border=BORDER_ALL, align=ALIGN_RIGHT, fmt=fmt)

    # Derived section
    hdr_row = R_LOAN - 1
    style_header_row(ws, hdr_row, 1, 2)
    apply_cell(ws, hdr_row, 1, "DERIVED (auto-calculated)", font=FONT_HEADER,
               fill=FILL_HEADER, align=ALIGN_LEFT, border=BORDER_ALL)

    derived = [
        (R_LOAN,   "Loan Amount",              f"=B{R_PP}*B{R_LTV}",                          FMT_DOLLAR),
        (R_EQUITY, "Equity Invested",          f"=B{R_PP}*(1-B{R_LTV})*(1+B{R_CLOSE_COST})",  FMT_DOLLAR),
        (R_IO_DS,  "Annual IO Debt Service",   f"=B{R_LOAN}*B{R_RATE}",                        FMT_DOLLAR),
        (R_MTH_DS, "Monthly IO Payment",       f"=B{R_IO_DS}/12",                              FMT_DOLLAR),
    ]
    for i, (row_num, label, formula, fmt) in enumerate(derived):
        fill = FILL_GRAY if i % 2 == 0 else None
        apply_cell(ws, row_num, 1, label,   font=FONT_BODY,  fill=fill, border=BORDER_ALL, align=ALIGN_LEFT)
        apply_cell(ws, row_num, 2, formula, font=FONT_TOTAL, fill=fill, border=BORDER_ALL, align=ALIGN_RIGHT, fmt=fmt)


# ══════════════════════════════════════════════════════════════════════════
# Sheet 3 — Income
# ══════════════════════════════════════════════════════════════════════════
def build_income(ws, prop: Property, assumptions: UWAssumptions, results: UWResults):
    ws.sheet_view.showGridLines = False
    _set_col_widths(ws, {"A": 34, "B": 18, "C": 16, "D": 16, "E": 14})

    apply_cell(ws, 1, 1, "INCOME & REVENUE ANALYSIS — YEAR 1", font=FONT_TITLE, align=ALIGN_LEFT)
    ws.merge_cells("A1:E1")
    apply_cell(ws, 2, 1, "All values formula-driven from Assumptions tab.",
               font=FONT_SMALL, align=ALIGN_LEFT)
    ws.merge_cells("A2:E2")

    r = 4
    for i, h in enumerate(["Line Item", "Annual ($)", "Per Unit ($)", "Per Month ($)", "% of EGI"]):
        apply_cell(ws, r, i + 1, h, font=FONT_HEADER, fill=FILL_HEADER, align=ALIGN_CENTER, border=BORDER_ALL)

    # Row assignments (B column = annual value)
    INC_GPR   = 5
    INC_VAC   = 6
    INC_EGI   = 7
    INC_OTHER = 8
    INC_EFF   = 9   # Total Effective EGI (referenced by OpEx mgmt formula)

    income_rows = [
        (INC_GPR,   "Gross Potential Rent (GPR)",       f"={a(R_RENT)}*{a(R_UNITS)}*12",        None),
        (INC_VAC,   "Vacancy & Credit Loss",            f"=-B{INC_GPR}*{a(R_VAC)}",             None),
        (INC_EGI,   "Effective Gross Income (EGI)",     f"=B{INC_GPR}+B{INC_VAC}",              "subtotal"),
        (INC_OTHER, "Other Income (Parking/Laundry)",   f"={a(R_OTHER)}*{a(R_UNITS)}*12",       None),
        (INC_EFF,   "Total Effective EGI",              f"=B{INC_EGI}+B{INC_OTHER}",            "total"),
    ]

    for row_num, label, formula, row_type in income_rows:
        fill = FILL_TOTAL if row_type == "total" else (FILL_SUBHEADER if row_type == "subtotal" else (FILL_GRAY if row_num % 2 == 0 else None))
        font = FONT_TOTAL if row_type in ("total", "subtotal") else FONT_BODY
        apply_cell(ws, row_num, 1, label,   font=font, fill=fill, border=BORDER_ALL, align=ALIGN_LEFT)
        apply_cell(ws, row_num, 2, formula, font=font, fill=fill, border=BORDER_ALL, align=ALIGN_RIGHT, fmt=FMT_DOLLAR)
        apply_cell(ws, row_num, 3, f"=B{row_num}/{a(R_UNITS)}", font=font, fill=fill, border=BORDER_ALL, align=ALIGN_RIGHT, fmt=FMT_DOLLAR)
        apply_cell(ws, row_num, 4, f"=B{row_num}/12",           font=font, fill=fill, border=BORDER_ALL, align=ALIGN_RIGHT, fmt=FMT_DOLLAR)
        pct = "1" if row_type == "total" else f"=B{row_num}/B{INC_EFF}"
        apply_cell(ws, row_num, 5, pct, font=font, fill=fill, border=BORDER_ALL, align=ALIGN_RIGHT, fmt=FMT_PCT_1)


# ══════════════════════════════════════════════════════════════════════════
# Sheet 4 — OpEx
# ══════════════════════════════════════════════════════════════════════════
def build_opex(ws, prop: Property, assumptions: UWAssumptions, results: UWResults):
    ws.sheet_view.showGridLines = False
    _set_col_widths(ws, {"A": 34, "B": 18, "C": 16, "D": 16, "E": 14})

    apply_cell(ws, 1, 1, "OPERATING EXPENSES — YEAR 1", font=FONT_TITLE, align=ALIGN_LEFT)
    ws.merge_cells("A1:E1")

    r = 3
    for i, h in enumerate(["Expense Line", "Annual ($)", "Per Unit ($)", "Per Month ($)", "% of EGI"]):
        apply_cell(ws, r, i + 1, h, font=FONT_HEADER, fill=FILL_HEADER, align=ALIGN_CENTER, border=BORDER_ALL)

    inc = "'3. Income'"
    EFF_EGI_REF = f"{inc}!B9"   # Total Effective EGI from Income sheet

    # Fixed row numbers for OpEx sheet
    OPEX_TAX   = 5
    OPEX_INS   = 6
    OPEX_UTIL  = 7
    OPEX_MAINT = 8
    OPEX_MGMT  = 9
    OPEX_ADMIN = 10
    OPEX_CAPEX = 11
    OPEX_TOTAL = 12
    OPEX_NOI   = 13
    OPEX_CAP   = 14

    opex_rows = [
        (OPEX_TAX,   "Property Taxes",             f"={a(R_PP)}*{a(R_TAX)}"),
        (OPEX_INS,   "Insurance",                  f"={a(R_INS)}*{a(R_UNITS)}"),
        (OPEX_UTIL,  "Utilities (Common Area)",    f"={a(R_UTIL)}*{a(R_UNITS)}*12"),
        (OPEX_MAINT, "Maintenance & Repairs",      f"={a(R_MAINT)}*{a(R_UNITS)}"),
        (OPEX_MGMT,  "Property Management",        f"={a(R_MGMT)}*{EFF_EGI_REF}"),
        (OPEX_ADMIN, "Admin / Legal / Accounting", f"={a(R_ADMIN)}*{a(R_UNITS)}"),
        (OPEX_CAPEX, "CapEx Reserve",              f"={a(R_CAPEX)}*{a(R_UNITS)}"),
    ]

    for row_num, label, formula in opex_rows:
        fill = FILL_GRAY if row_num % 2 == 0 else None
        apply_cell(ws, row_num, 1, label,   font=FONT_BODY, fill=fill, border=BORDER_ALL, align=ALIGN_LEFT)
        apply_cell(ws, row_num, 2, formula, font=FONT_BODY, fill=fill, border=BORDER_ALL, align=ALIGN_RIGHT, fmt=FMT_DOLLAR)
        apply_cell(ws, row_num, 3, f"=B{row_num}/{a(R_UNITS)}", font=FONT_BODY, fill=fill, border=BORDER_ALL, align=ALIGN_RIGHT, fmt=FMT_DOLLAR)
        apply_cell(ws, row_num, 4, f"=B{row_num}/12",           font=FONT_BODY, fill=fill, border=BORDER_ALL, align=ALIGN_RIGHT, fmt=FMT_DOLLAR)
        apply_cell(ws, row_num, 5, f"=B{row_num}/{EFF_EGI_REF}", font=FONT_BODY, fill=fill, border=BORDER_ALL, align=ALIGN_RIGHT, fmt=FMT_PCT_1)

    # Total OpEx
    style_total_row(ws, OPEX_TOTAL, 1, 5)
    apply_cell(ws, OPEX_TOTAL, 1, "Total Operating Expenses", font=FONT_TOTAL, fill=FILL_TOTAL, border=BORDER_ALL, align=ALIGN_LEFT)
    apply_cell(ws, OPEX_TOTAL, 2, f"=SUM(B{OPEX_TAX}:B{OPEX_CAPEX})", font=FONT_TOTAL, fill=FILL_TOTAL, border=BORDER_ALL, align=ALIGN_RIGHT, fmt=FMT_DOLLAR)
    apply_cell(ws, OPEX_TOTAL, 3, f"=B{OPEX_TOTAL}/{a(R_UNITS)}", font=FONT_TOTAL, fill=FILL_TOTAL, border=BORDER_ALL, align=ALIGN_RIGHT, fmt=FMT_DOLLAR)
    apply_cell(ws, OPEX_TOTAL, 4, f"=B{OPEX_TOTAL}/12",           font=FONT_TOTAL, fill=FILL_TOTAL, border=BORDER_ALL, align=ALIGN_RIGHT, fmt=FMT_DOLLAR)
    apply_cell(ws, OPEX_TOTAL, 5, f"=B{OPEX_TOTAL}/{EFF_EGI_REF}", font=FONT_TOTAL, fill=FILL_TOTAL, border=BORDER_ALL, align=ALIGN_RIGHT, fmt=FMT_PCT_1)

    # NOI
    style_header_row(ws, OPEX_NOI, 1, 5)
    apply_cell(ws, OPEX_NOI, 1, "Net Operating Income (NOI)", font=FONT_HEADER, fill=FILL_HEADER, border=BORDER_ALL, align=ALIGN_LEFT)
    apply_cell(ws, OPEX_NOI, 2, f"={EFF_EGI_REF}-B{OPEX_TOTAL}", font=FONT_HEADER, fill=FILL_HEADER, border=BORDER_ALL, align=ALIGN_RIGHT, fmt=FMT_DOLLAR)
    apply_cell(ws, OPEX_NOI, 3, f"=B{OPEX_NOI}/{a(R_UNITS)}", font=FONT_HEADER, fill=FILL_HEADER, border=BORDER_ALL, align=ALIGN_RIGHT, fmt=FMT_DOLLAR)
    apply_cell(ws, OPEX_NOI, 4, f"=B{OPEX_NOI}/12",           font=FONT_HEADER, fill=FILL_HEADER, border=BORDER_ALL, align=ALIGN_RIGHT, fmt=FMT_DOLLAR)
    apply_cell(ws, OPEX_NOI, 5, f"=B{OPEX_NOI}/{EFF_EGI_REF}", font=FONT_HEADER, fill=FILL_HEADER, border=BORDER_ALL, align=ALIGN_RIGHT, fmt=FMT_PCT_1)

    # Cap Rate
    apply_cell(ws, OPEX_CAP, 1, "Going-In Cap Rate", font=FONT_SUBHEADER, align=ALIGN_LEFT)
    apply_cell(ws, OPEX_CAP, 2, f"=B{OPEX_NOI}/{a(R_PP)}", font=FONT_METRIC, align=ALIGN_RIGHT, fmt=FMT_PCT_1)


# ══════════════════════════════════════════════════════════════════════════
# Sheet 5 — Debt Schedule
# ══════════════════════════════════════════════════════════════════════════
def build_debt_schedule(ws, prop: Property, assumptions: UWAssumptions, results: UWResults):
    ws.sheet_view.showGridLines = False
    _set_col_widths(ws, {"A": 8, "B": 16, "C": 16, "D": 16, "E": 16, "F": 16, "G": 12, "H": 16})

    apply_cell(ws, 1, 1, "DEBT SCHEDULE — 7/1 IO ARM", font=FONT_TITLE, align=ALIGN_LEFT)
    ws.merge_cells("A1:H1")

    # Loan summary box — all formula references
    loan_info = [
        ("Loan Amount",            f"={a(R_LOAN)}",   FMT_DOLLAR),
        ("LTV",                    f"={a(R_LTV)}",    FMT_PCT_1),
        ("Interest Rate",          f"={a(R_RATE)}",   FMT_PCT),
        ("Structure",              "7/1 Interest-Only ARM", None),
        ("IO Period (Years)",      f"={a(R_IO_YRS)}", FMT_NUM),
        ("Annual IO Payment",      f"={a(R_IO_DS)}",  FMT_DOLLAR),
        ("Monthly IO Payment",     f"={a(R_MTH_DS)}", FMT_DOLLAR),
        ("Amortizing Payment/mo",  f"=-PMT({a(R_RATE)}/12,360,-{a(R_LOAN)})", FMT_DOLLAR),
    ]
    r = 3
    for i, (label, val, fmt) in enumerate(loan_info):
        fill = FILL_GRAY if i % 2 == 0 else None
        apply_cell(ws, r, 1, label, font=FONT_BODY, fill=fill, border=BORDER_ALL, align=ALIGN_LEFT)
        ws.merge_cells(f"A{r}:A{r}")  # label spans A
        apply_cell(ws, r, 2, val,   font=FONT_BODY, fill=fill, border=BORDER_ALL, align=ALIGN_RIGHT, fmt=fmt)
        r += 1

    r += 1
    headers = ["Year", "Period", "Interest", "Principal", "Debt Service", "Loan Balance", "DSCR", "Net Cash Flow"]
    for i, h in enumerate(headers):
        apply_cell(ws, r, i + 1, h, font=FONT_HEADER, fill=FILL_HEADER, align=ALIGN_CENTER, border=BORDER_ALL)

    noi_ref = "'4. OpEx'!B13"   # Year 1 NOI for DSCR

    opx = "'4. OpEx'"
    ret = "'6. Returns'"

    for yr in range(1, assumptions.hold_years + 1):
        r += 1
        col_yr = get_column_letter(yr + 1)  # Returns sheet col for this year

        # Pull NOI from Returns sheet for each year
        noi = f"'{ret[1:-1]}'!{col_yr}{R_NOI}" if yr > 1 else f"{opx}!B13"
        # For the debt schedule we pull from the Returns sheet year columns
        noi_cell = f"'6. Returns'!{col_yr}{R_NOI}"
        ds_cell  = f"'6. Returns'!{col_yr}{R_DS}"
        ncf_cell = f"'6. Returns'!{col_yr}{R_NCF}"
        lbal_cell = f"'6. Returns'!{col_yr}{R_LNBAL}"

        is_io = yr <= assumptions.io_years
        from openpyxl.styles import PatternFill
        row_fill = PatternFill("solid", fgColor="EBF3FB") if is_io else None

        apply_cell(ws, r, 1, yr,       font=FONT_BODY, fill=row_fill, border=BORDER_ALL, align=ALIGN_CENTER)
        apply_cell(ws, r, 2, f'=IF({col_yr}{R_YR_ROW}<={a(R_IO_YRS)},"Interest Only","Amortizing")',
                   font=FONT_BODY, fill=row_fill, border=BORDER_ALL, align=ALIGN_CENTER)
        # Interest = loan*rate during IO; else DS - principal
        interest = (f"={a(R_LOAN)}*{a(R_RATE)}" if is_io
                    else f"={ds_cell}-(-PMT({a(R_RATE)}/12,360,-{a(R_LOAN)})-{a(R_LOAN)}*{a(R_RATE)})")
        principal = "=0" if is_io else f"=-PMT({a(R_RATE)}/12,360,-{a(R_LOAN)})-{a(R_LOAN)}*{a(R_RATE)}"
        apply_cell(ws, r, 3, interest,   font=FONT_BODY, fill=row_fill, border=BORDER_ALL, align=ALIGN_RIGHT, fmt=FMT_DOLLAR)
        apply_cell(ws, r, 4, principal,  font=FONT_BODY, fill=row_fill, border=BORDER_ALL, align=ALIGN_RIGHT, fmt=FMT_DOLLAR)
        apply_cell(ws, r, 5, f"={ds_cell}",   font=FONT_BODY, fill=row_fill, border=BORDER_ALL, align=ALIGN_RIGHT, fmt=FMT_DOLLAR)
        apply_cell(ws, r, 6, f"={lbal_cell}", font=FONT_BODY, fill=row_fill, border=BORDER_ALL, align=ALIGN_RIGHT, fmt=FMT_DOLLAR)

        dscr_formula = f"={noi_cell}/{ds_cell}"
        dscr_fill = FILL_GREEN if (results.yearly_metrics[yr-1]["noi"] / results.yearly_metrics[yr-1]["debt_service"]) >= 1.25 else FILL_RED
        apply_cell(ws, r, 7, dscr_formula, font=FONT_BODY, fill=dscr_fill, border=BORDER_ALL, align=ALIGN_RIGHT, fmt="0.00x")
        apply_cell(ws, r, 8, f"={ncf_cell}", font=FONT_BODY, fill=row_fill, border=BORDER_ALL, align=ALIGN_RIGHT, fmt=FMT_DOLLAR)


# ══════════════════════════════════════════════════════════════════════════
# Sheet 6 — Returns (10-year waterfall — all formulas)
# ══════════════════════════════════════════════════════════════════════════
def build_returns(ws, prop: Property, assumptions: UWAssumptions, results: UWResults):
    ws.sheet_view.showGridLines = False

    hold = assumptions.hold_years
    n_data_cols = hold
    last_data_col = get_column_letter(n_data_cols + 1)  # +1 for label col A

    widths = {"A": 32}
    for i in range(1, n_data_cols + 1):
        widths[get_column_letter(i + 1)] = 14
    _set_col_widths(ws, widths)

    apply_cell(ws, 1, 1, f"{hold}-YEAR CASH FLOW & RETURNS MODEL", font=FONT_TITLE, align=ALIGN_LEFT)
    ws.merge_cells(f"A1:{last_data_col}1")
    apply_cell(ws, 2, 1, "All values are formula-driven. Change assumptions in Sheet 2 — this sheet updates automatically.",
               font=FONT_SMALL, align=ALIGN_LEFT)
    ws.merge_cells(f"A2:{last_data_col}2")

    # Year header row (row 3)
    style_header_row(ws, R_YR_ROW, 1, n_data_cols + 1)
    apply_cell(ws, R_YR_ROW, 1, "Year", font=FONT_HEADER, fill=FILL_HEADER, align=ALIGN_LEFT, border=BORDER_ALL)
    for yr in range(1, n_data_cols + 1):
        apply_cell(ws, R_YR_ROW, yr + 1, yr, font=FONT_HEADER, fill=FILL_HEADER, align=ALIGN_CENTER, border=BORDER_ALL)

    ws.freeze_panes = "B4"

    def sec_hdr(row, label):
        style_header_row(ws, row, 1, n_data_cols + 1)
        apply_cell(ws, row, 1, label, font=FONT_HEADER, fill=FILL_HEADER, align=ALIGN_LEFT, border=BORDER_ALL)
        for c in range(2, n_data_cols + 2):
            apply_cell(ws, row, c, "", fill=FILL_HEADER, border=BORDER_ALL)

    def data_row(row, label, formulas_by_col: dict, fmt, row_type="normal"):
        fill_map = {"total": FILL_TOTAL, "subtotal": FILL_SUBHEADER, "normal": None}
        font_map = {"total": FONT_TOTAL, "subtotal": FONT_SUBHEADER, "normal": FONT_BODY}
        fill = fill_map.get(row_type)
        font = font_map.get(row_type, FONT_BODY)
        apply_cell(ws, row, 1, label, font=font, fill=fill or (FILL_GRAY if row % 2 == 0 else None),
                   border=BORDER_ALL, align=ALIGN_LEFT)
        for yr in range(1, n_data_cols + 1):
            col = get_column_letter(yr + 1)
            f = formulas_by_col.get(yr, "")
            cell_fill = fill or (FILL_GRAY if row % 2 == 0 else None)
            apply_cell(ws, row, yr + 1, f, font=font, fill=cell_fill, border=BORDER_ALL,
                       align=ALIGN_RIGHT, fmt=fmt)

    # ── REVENUE ──────────────────────────────────────────────────────────
    sec_hdr(5, "REVENUE")

    # GPR: Yr1 from Assumptions; YrN = prev*(1+growth)
    gpr_f = {}
    for yr in range(1, n_data_cols + 1):
        col = get_column_letter(yr + 1)
        prev = get_column_letter(yr)
        gpr_f[yr] = (f"={a(R_RENT)}*{a(R_UNITS)}*12" if yr == 1
                     else f"={prev}{R_GPR}*(1+{a(R_RENT_GRW)})")
    data_row(R_GPR, "Gross Potential Rent", gpr_f, FMT_DOLLAR)

    vac_f = {yr: f"=-{get_column_letter(yr+1)}{R_GPR}*{a(R_VAC)}" for yr in range(1, n_data_cols + 1)}
    data_row(R_VAC_R, "Vacancy & Credit Loss", vac_f, FMT_DOLLAR)

    egi_f = {yr: f"={get_column_letter(yr+1)}{R_GPR}+{get_column_letter(yr+1)}{R_VAC_R}" for yr in range(1, n_data_cols + 1)}
    data_row(R_EGI, "Effective Gross Income (EGI)", egi_f, FMT_DOLLAR, "subtotal")

    other_f = {}
    for yr in range(1, n_data_cols + 1):
        col = get_column_letter(yr + 1)
        prev = get_column_letter(yr)
        other_f[yr] = (f"={a(R_OTHER)}*{a(R_UNITS)}*12" if yr == 1
                       else f"={prev}{R_OTHER_R}*(1+{a(R_RENT_GRW)})")
    data_row(R_OTHER_R, "Other Income", other_f, FMT_DOLLAR)

    rev_f = {yr: f"={get_column_letter(yr+1)}{R_EGI}+{get_column_letter(yr+1)}{R_OTHER_R}" for yr in range(1, n_data_cols + 1)}
    data_row(R_REV, "Total Revenue", rev_f, FMT_DOLLAR, "total")

    # ── OPERATING EXPENSES ───────────────────────────────────────────────
    sec_hdr(12, "OPERATING EXPENSES")

    def exp_row(row, label, yr1_formula, growth_ref):
        f = {}
        for yr in range(1, n_data_cols + 1):
            col = get_column_letter(yr + 1)
            prev = get_column_letter(yr)
            f[yr] = yr1_formula if yr == 1 else f"={prev}{row}*(1+{growth_ref})"
        data_row(row, label, f, FMT_DOLLAR)

    exp_row(R_TAX_R,   "Property Taxes",        f"={a(R_PP)}*{a(R_TAX)}",         a(R_EXP_GRW))
    exp_row(R_INS_R,   "Insurance",             f"={a(R_INS)}*{a(R_UNITS)}",       a(R_EXP_GRW))
    exp_row(R_UTIL_R,  "Utilities",             f"={a(R_UTIL)}*{a(R_UNITS)}*12",   a(R_EXP_GRW))
    exp_row(R_MAINT_R, "Maintenance",           f"={a(R_MAINT)}*{a(R_UNITS)}",     a(R_EXP_GRW))

    # Mgmt = % of Total Revenue each year
    mgmt_f = {yr: f"={a(R_MGMT)}*{get_column_letter(yr+1)}{R_REV}" for yr in range(1, n_data_cols + 1)}
    data_row(R_MGMT_R, "Property Management", mgmt_f, FMT_DOLLAR)

    exp_row(R_ADMIN_R, "Admin / Legal",         f"={a(R_ADMIN)}*{a(R_UNITS)}",     a(R_EXP_GRW))
    exp_row(R_CAPEX_R, "CapEx Reserve",         f"={a(R_CAPEX)}*{a(R_UNITS)}",     a(R_EXP_GRW))

    opex_f = {yr: f"=SUM({get_column_letter(yr+1)}{R_TAX_R}:{get_column_letter(yr+1)}{R_CAPEX_R})"
              for yr in range(1, n_data_cols + 1)}
    data_row(R_OPEX, "Total OpEx", opex_f, FMT_DOLLAR, "total")

    # ── NOI ──────────────────────────────────────────────────────────────
    sec_hdr(21, "NET OPERATING INCOME")

    noi_f = {yr: f"={get_column_letter(yr+1)}{R_REV}-{get_column_letter(yr+1)}{R_OPEX}" for yr in range(1, n_data_cols + 1)}
    data_row(R_NOI, "Net Operating Income (NOI)", noi_f, FMT_DOLLAR, "total")

    cap_f = {yr: f"={get_column_letter(yr+1)}{R_NOI}/{a(R_PP)}" for yr in range(1, n_data_cols + 1)}
    data_row(R_CAP_R, "Cap Rate (on purchase price)", cap_f, FMT_PCT_1)

    # ── DEBT SERVICE ─────────────────────────────────────────────────────
    sec_hdr(25, "DEBT SERVICE")

    ds_f = {yr: f"=IF({get_column_letter(yr+1)}{R_YR_ROW}<={a(R_IO_YRS)},{a(R_LOAN)}*{a(R_RATE)},-PMT({a(R_RATE)}/12,360,-{a(R_LOAN)})*12)"
            for yr in range(1, n_data_cols + 1)}
    data_row(R_DS, "Annual Debt Service", ds_f, FMT_DOLLAR)

    period_f = {yr: f'=IF({get_column_letter(yr+1)}{R_YR_ROW}<={a(R_IO_YRS)},"Interest Only","Amortizing")'
                for yr in range(1, n_data_cols + 1)}
    data_row(R_PERIOD, "Period", period_f, None)

    # ── CASH FLOW ────────────────────────────────────────────────────────
    sec_hdr(28, "CASH FLOW")

    ncf_f = {yr: f"={get_column_letter(yr+1)}{R_NOI}-{get_column_letter(yr+1)}{R_DS}" for yr in range(1, n_data_cols + 1)}
    data_row(R_NCF, "Net Cash Flow (NCF)", ncf_f, FMT_DOLLAR, "total")

    dscr_f = {yr: f"={get_column_letter(yr+1)}{R_NOI}/{get_column_letter(yr+1)}{R_DS}" for yr in range(1, n_data_cols + 1)}
    data_row(R_DSCR, "DSCR", dscr_f, "0.00x")

    # ── LOAN BALANCE ─────────────────────────────────────────────────────
    sec_hdr(32, "LOAN BALANCE & EXIT")

    lbal_f = {}
    for yr in range(1, n_data_cols + 1):
        col = get_column_letter(yr + 1)
        lbal_f[yr] = (
            f"=IF({col}{R_YR_ROW}<={a(R_IO_YRS)},"
            f"{a(R_LOAN)},"
            f"-PV({a(R_RATE)}/12,"
            f"360-({col}{R_YR_ROW}-{a(R_IO_YRS)})*12,"
            f"PMT({a(R_RATE)}/12,360,-{a(R_LOAN)})))"
        )
    data_row(R_LNBAL, "Loan Balance (End of Year)", lbal_f, FMT_DOLLAR)

    # Going-in cap (fixed, always Year 1 NOI / PP)
    going_in_cap = f"=B{R_NOI}/{a(R_PP)}"

    # Exit proceeds — 5yr (exit at year 5) and 10yr (exit at hold_years)
    def exit_formula(col, yr, exit_yr_expr):
        noi_col = f"{col}{R_NOI}"
        lbal_col = f"{col}{R_LNBAL}"
        yr_cell = f"{col}{R_YR_ROW}"
        exit_price = f"({noi_col}/(B{R_NOI}/{a(R_PP)}+{a(R_EXIT_SPR)}))"
        net = f"{exit_price}*(1-{a(R_TRANS_COST)})-{lbal_col}"
        return f"=IF({yr_cell}={exit_yr_expr},{net},0)"

    exit5_f  = {yr: exit_formula(get_column_letter(yr+1), yr, "5")          for yr in range(1, n_data_cols + 1)}
    exit10_f = {yr: exit_formula(get_column_letter(yr+1), yr, a(R_HOLD_YRS)) for yr in range(1, n_data_cols + 1)}
    data_row(R_EXIT5,  "Net Exit Proceeds (5-Year Hold)",         exit5_f,  FMT_DOLLAR)
    data_row(R_EXIT10, f"Net Exit Proceeds ({hold}-Year Hold)",   exit10_f, FMT_DOLLAR)

    # ── IRR CASH FLOW ROWS ───────────────────────────────────────────────
    # Row structure: col A = Year 0 equity outflow; cols B onward = annual CFs
    # IRR5 row: years 0-5 (A through F)
    # IRR10 row: years 0-hold (A through last_data_col+1)
    sec_hdr(37, "RETURN CALCULATIONS")

    apply_cell(ws, R_IRR5,  1, "Cash Flows — 5yr Hold",          font=FONT_BODY, fill=FILL_GRAY, border=BORDER_ALL, align=ALIGN_LEFT)
    apply_cell(ws, R_IRR10, 1, f"Cash Flows — {hold}yr Hold",    font=FONT_BODY, fill=FILL_GRAY, border=BORDER_ALL, align=ALIGN_LEFT)

    # Col A (column index 1) = Year 0 equity outflow
    apply_cell(ws, R_IRR5,  1, "CF — 5yr Hold (Yr0→Yr5)",  font=FONT_SMALL, fill=FILL_GRAY, border=BORDER_ALL, align=ALIGN_LEFT)
    apply_cell(ws, R_IRR10, 1, f"CF — {hold}yr Hold (Yr0→Yr{hold})", font=FONT_SMALL, fill=FILL_GRAY, border=BORDER_ALL, align=ALIGN_LEFT)

    # Populate IRR cash flow rows
    # NOTE: these rows use the LABEL column (col 1) for Year-0 equity
    #       and data columns (col 2+) for annual cash flows
    yr0_eq = f"=-{a(R_EQUITY)}"
    apply_cell(ws, R_IRR5,  1, f"CF 5yr [Yr0={a(R_EQUITY)}]", font=FONT_SMALL, fill=FILL_GRAY, border=BORDER_ALL)
    apply_cell(ws, R_IRR10, 1, f"CF {hold}yr [Yr0={a(R_EQUITY)}]", font=FONT_SMALL, fill=FILL_GRAY, border=BORDER_ALL)

    # Use a dedicated helper row approach: put Year-0 in a named cell, years 1-N in data cols
    # We'll place the IRR CF array starting in column A (index 1) for Year 0
    # and columns B+ for Year 1+
    # Since col A is the label col, we overwrite the label with the Year-0 value
    apply_cell(ws, R_IRR5,  1, yr0_eq, font=FONT_SMALL, fill=FILL_GRAY, border=BORDER_ALL, align=ALIGN_RIGHT, fmt=FMT_DOLLAR)
    apply_cell(ws, R_IRR10, 1, yr0_eq, font=FONT_SMALL, fill=FILL_GRAY, border=BORDER_ALL, align=ALIGN_RIGHT, fmt=FMT_DOLLAR)

    for yr in range(1, n_data_cols + 1):
        col = get_column_letter(yr + 1)
        ncf_cell   = f"{col}{R_NCF}"
        exit5_cell = f"{col}{R_EXIT5}"
        exit10_cell= f"{col}{R_EXIT10}"

        # 5yr row: include exit at year 5, zero after
        if yr <= 5:
            irr5_val = f"={ncf_cell}+{exit5_cell}"
        else:
            irr5_val = "=0"
        apply_cell(ws, R_IRR5, yr + 1, irr5_val, font=FONT_SMALL, fill=FILL_GRAY, border=BORDER_ALL, align=ALIGN_RIGHT, fmt=FMT_DOLLAR)

        # 10yr row: include exit at hold_years
        irr10_val = f"={ncf_cell}+{exit10_cell}"
        apply_cell(ws, R_IRR10, yr + 1, irr10_val, font=FONT_SMALL, fill=FILL_GRAY, border=BORDER_ALL, align=ALIGN_RIGHT, fmt=FMT_DOLLAR)

    # Summary return metrics
    irr5_range  = f"A{R_IRR5}:{get_column_letter(6)}{R_IRR5}"    # Yr0 through Yr5
    irr10_range = f"A{R_IRR10}:{get_column_letter(n_data_cols+1)}{R_IRR10}"  # Yr0 through YrN

    ret_rows = [
        ("5-Year IRR",              f"=IFERROR(IRR({irr5_range}),\"N/A\")",                        FMT_PCT_1),
        ("10-Year IRR",             f"=IFERROR(IRR({irr10_range}),\"N/A\")",                       FMT_PCT_1),
        ("5-Year Equity Multiple",  f"=IFERROR(SUM(B{R_IRR5}:{get_column_letter(6)}{R_IRR5})/ABS(A{R_IRR5}),\"N/A\")", FMT_MULT),
        (f"{hold}-Year Eq. Multiple", f"=IFERROR(SUM(B{R_IRR10}:{get_column_letter(n_data_cols+1)}{R_IRR10})/ABS(A{R_IRR10}),\"N/A\")", FMT_MULT),
        ("Year 1 Cash-on-Cash",     f"=B{R_NCF}/{a(R_EQUITY)}",                                   FMT_PCT_1),
        ("Year 1 DSCR",             f"=B{R_DSCR}",                                                 "0.00x"),
        ("Year 1 Cap Rate",         f"=B{R_CAP_R}",                                                FMT_PCT_1),
        ("Equity Invested",         f"={a(R_EQUITY)}",                                             FMT_DOLLAR),
        ("Exit Price (Yr 10)",      f"=IFERROR({get_column_letter(n_data_cols+1)}{R_NOI}/(B{R_NOI}/{a(R_PP)}+{a(R_EXIT_SPR)}),\"N/A\")", FMT_DOLLAR),
    ]

    r_sum = R_IRR10 + 2
    style_header_row(ws, r_sum, 1, 3)
    apply_cell(ws, r_sum, 1, "RETURN SUMMARY", font=FONT_HEADER, fill=FILL_HEADER, border=BORDER_ALL, align=ALIGN_LEFT)
    apply_cell(ws, r_sum, 2, "Value",          font=FONT_HEADER, fill=FILL_HEADER, border=BORDER_ALL, align=ALIGN_CENTER)
    apply_cell(ws, r_sum, 3, "Target",         font=FONT_HEADER, fill=FILL_HEADER, border=BORDER_ALL, align=ALIGN_CENTER)

    targets = {"IRR": "≥ 12%", "Cash-on-Cash": "≥ 7%", "DSCR": "≥ 1.25x",
               "Cap Rate": "≥ 6%", "Multiple": "≥ 1.5x"}

    for i, (label, formula, fmt) in enumerate(ret_rows):
        row = r_sum + 1 + i
        fill = FILL_GRAY if i % 2 == 0 else None
        target = next((v for k, v in targets.items() if k in label), "—")
        apply_cell(ws, row, 1, label,   font=FONT_BODY,  fill=fill, border=BORDER_ALL, align=ALIGN_LEFT)
        apply_cell(ws, row, 2, formula, font=FONT_TOTAL, fill=fill, border=BORDER_ALL, align=ALIGN_RIGHT, fmt=fmt)
        apply_cell(ws, row, 3, target,  font=FONT_SMALL, fill=fill, border=BORDER_ALL, align=ALIGN_CENTER)


# ══════════════════════════════════════════════════════════════════════════
# Sheet 7 — Sensitivity
# ══════════════════════════════════════════════════════════════════════════
def build_sensitivity(ws, prop: Property, assumptions: UWAssumptions, results: UWResults):
    ws.sheet_view.showGridLines = False
    _set_col_widths(ws, {"A": 22, "B": 12, "C": 12, "D": 12, "E": 12, "F": 12, "G": 12})

    apply_cell(ws, 1, 1, "SENSITIVITY ANALYSIS", font=FONT_TITLE, align=ALIGN_LEFT)
    ws.merge_cells("A1:G1")
    apply_cell(ws, 2, 1,
               "Note: Sensitivity tables re-run Python calculations and show results. "
               "Change base assumptions in Sheet 2 and regenerate the Excel file to refresh.",
               font=FONT_SMALL, align=ALIGN_LEFT)
    ws.merge_cells("A2:G2")

    from underwriting.engine import underwrite
    from underwriting.assumptions import assumptions_from_dict

    def _quick(overrides):
        a_ = assumptions_from_dict({**assumptions.model_dump(), **overrides})
        return underwrite(prop, a_)

    # Grid 1: CoC Y1 vs Vacancy × Rent
    r = 4
    apply_cell(ws, r, 1, "Year 1 Cash-on-Cash — Vacancy Rate vs. Rent Level",
               font=FONT_SUBHEADER, align=ALIGN_LEFT)
    ws.merge_cells(f"A{r}:G{r}")
    r += 1

    vacancies   = [0.03, 0.05, 0.08, 0.10, 0.15]
    rent_deltas = [-0.10, -0.05, 0.00, 0.05, 0.10]
    base_rent   = (assumptions.market_rent_per_unit or
                   (prop.monthly_rent_total / prop.units if prop.monthly_rent_total else None))

    apply_cell(ws, r, 1, "Vacancy →", font=FONT_SUBHEADER, fill=FILL_SUBHEADER, border=BORDER_ALL, align=ALIGN_CENTER)
    for j, v in enumerate(vacancies):
        apply_cell(ws, r, j + 2, f"{v:.0%}", font=FONT_SUBHEADER, fill=FILL_SUBHEADER, border=BORDER_ALL, align=ALIGN_CENTER)
    r += 1

    for rd in rent_deltas:
        apply_cell(ws, r, 1, f"Rent {rd:+.0%}", font=FONT_BODY, fill=FILL_GRAY, border=BORDER_ALL, align=ALIGN_CENTER)
        for j, v in enumerate(vacancies):
            ov = {"vacancy_rate": v}
            if base_rent:
                ov["market_rent_per_unit"] = base_rent * (1 + rd)
            try:
                res = _quick(ov)
                coc = res.coc_y1
                fill = FILL_GREEN if coc >= 0.07 else FILL_RED
                apply_cell(ws, r, j + 2, coc, font=FONT_BODY, fill=fill, border=BORDER_ALL, align=ALIGN_CENTER, fmt=FMT_PCT_1)
            except Exception:
                apply_cell(ws, r, j + 2, "ERR", font=FONT_BODY, border=BORDER_ALL, align=ALIGN_CENTER)
        r += 1

    # Grid 2: DSCR vs Purchase Price × NOI
    r += 2
    apply_cell(ws, r, 1, "DSCR — Purchase Price Δ vs. NOI Δ",
               font=FONT_SUBHEADER, align=ALIGN_LEFT)
    ws.merge_cells(f"A{r}:G{r}")
    r += 1

    price_deltas = [-0.10, -0.05, 0.00, 0.05, 0.10]
    noi_deltas   = [-0.10, -0.05, 0.00, 0.05, 0.10]

    apply_cell(ws, r, 1, "NOI Δ →", font=FONT_SUBHEADER, fill=FILL_SUBHEADER, border=BORDER_ALL, align=ALIGN_CENTER)
    for j, nd in enumerate(noi_deltas):
        apply_cell(ws, r, j + 2, f"NOI {nd:+.0%}", font=FONT_SUBHEADER, fill=FILL_SUBHEADER, border=BORDER_ALL, align=ALIGN_CENTER)
    r += 1

    for pd_ in price_deltas:
        apply_cell(ws, r, 1, f"Price {pd_:+.0%}", font=FONT_BODY, fill=FILL_GRAY, border=BORDER_ALL, align=ALIGN_CENTER)
        for j, nd in enumerate(noi_deltas):
            new_price = prop.purchase_price * (1 + pd_)
            new_noi   = results.noi * (1 + nd)
            new_loan  = new_price * assumptions.ltv
            ds        = new_loan * assumptions.interest_rate
            dscr      = new_noi / ds if ds else 0
            fill = FILL_GREEN if dscr >= 1.25 else FILL_RED
            apply_cell(ws, r, j + 2, dscr, font=FONT_BODY, fill=fill, border=BORDER_ALL, align=ALIGN_CENTER, fmt="0.00x")
        r += 1

    # Grid 3: 5yr IRR vs Entry Cap × Exit Cap
    r += 2
    apply_cell(ws, r, 1, "5-Year IRR — Implied Entry Cap vs. Exit Cap Spread",
               font=FONT_SUBHEADER, align=ALIGN_LEFT)
    ws.merge_cells(f"A{r}:G{r}")
    r += 1

    going_in = results.going_in_cap_rate
    entry_caps   = [going_in - 0.01, going_in - 0.005, going_in, going_in + 0.005, going_in + 0.01]
    exit_spreads = [-0.005, 0.0, 0.0025, 0.005, 0.01]

    apply_cell(ws, r, 1, "Exit Spread →", font=FONT_SUBHEADER, fill=FILL_SUBHEADER, border=BORDER_ALL, align=ALIGN_CENTER)
    for j, es in enumerate(exit_spreads):
        apply_cell(ws, r, j + 2, f"{es:+.2%}", font=FONT_SUBHEADER, fill=FILL_SUBHEADER, border=BORDER_ALL, align=ALIGN_CENTER)
    r += 1

    for ec in entry_caps:
        apply_cell(ws, r, 1, f"Entry {ec:.2%}", font=FONT_BODY, fill=FILL_GRAY, border=BORDER_ALL, align=ALIGN_CENTER)
        for j, es in enumerate(exit_spreads):
            implied_pp = results.noi / ec if ec > 0 else prop.purchase_price
            test_prop = prop.model_copy(update={"purchase_price": implied_pp})
            try:
                res = _quick.__func__({"exit_cap_spread": es}) if False else _quick({"exit_cap_spread": es})
                # Re-underwrite with implied price for entry cap
                from underwriting.assumptions import assumptions_from_dict as afd
                a2 = afd({**assumptions.model_dump(), "exit_cap_spread": es})
                from underwriting.engine import underwrite as uw2
                res = uw2(test_prop, a2)
                irr = res.irr_5yr
                fill = FILL_GREEN if irr and irr >= 0.12 else FILL_RED
                apply_cell(ws, r, j + 2, irr, font=FONT_BODY, fill=fill, border=BORDER_ALL, align=ALIGN_CENTER, fmt=FMT_PCT_1)
            except Exception:
                apply_cell(ws, r, j + 2, "ERR", font=FONT_BODY, border=BORDER_ALL, align=ALIGN_CENTER)
        r += 1

    r += 2
    apply_cell(ws, r, 1, "■ Green = meets target  ■ Red = below target  |  CoC ≥ 7%  |  IRR ≥ 12%  |  DSCR ≥ 1.25x",
               font=FONT_SMALL, align=ALIGN_LEFT)
    ws.merge_cells(f"A{r}:G{r}")
