"""Unit tests for the underwriting engine."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from models.property import Property
from models.underwriting import UWAssumptions
from underwriting.engine import underwrite
from underwriting.cashflow import build_yearly_metrics, compute_irr


@pytest.fixture
def sample_property():
    return Property(
        address="123 Test St",
        city="Phoenix",
        state="AZ",
        units=4,
        purchase_price=900_000,
        monthly_rent_total=4_800,  # $1,200/unit
        year_built=1985,
        sqft=4_000,
        listing_url="https://example.com",
        source="test",
    )


@pytest.fixture
def sample_assumptions():
    return UWAssumptions(
        ltv=0.75,
        interest_rate=0.0575,
        io_years=7,
        hold_years=10,
        vacancy_rate=0.05,
        other_income_per_unit_monthly=75.0,
        rent_growth_annual=0.03,
        tax_rate_of_value=0.0125,
        insurance_per_unit=1200.0,
        utilities_per_unit_monthly=75.0,
        maintenance_per_unit=850.0,
        mgmt_pct_of_egi=0.09,
        admin_per_unit=300.0,
        capex_reserve_per_unit=275.0,
        expense_growth_annual=0.03,
        exit_cap_spread=0.0025,
    )


class TestUnderwritingEngine:
    def test_basic_underwrite_runs(self, sample_property, sample_assumptions):
        results = underwrite(sample_property, sample_assumptions)
        assert results is not None

    def test_gpr_calculation(self, sample_property, sample_assumptions):
        results = underwrite(sample_property, sample_assumptions)
        expected_gpr = 4_800 * 12  # $57,600
        assert abs(results.gpr - expected_gpr) < 1.0

    def test_vacancy_loss(self, sample_property, sample_assumptions):
        results = underwrite(sample_property, sample_assumptions)
        expected_loss = results.gpr * 0.05
        assert abs(results.vacancy_loss - expected_loss) < 1.0

    def test_noi_positive(self, sample_property, sample_assumptions):
        results = underwrite(sample_property, sample_assumptions)
        assert results.noi > 0

    def test_cap_rate_range(self, sample_property, sample_assumptions):
        results = underwrite(sample_property, sample_assumptions)
        assert 0.02 <= results.going_in_cap_rate <= 0.20

    def test_loan_amount(self, sample_property, sample_assumptions):
        results = underwrite(sample_property, sample_assumptions)
        expected_loan = 900_000 * 0.75  # $675,000
        assert abs(results.loan_amount - expected_loan) < 1.0

    def test_io_debt_service(self, sample_property, sample_assumptions):
        results = underwrite(sample_property, sample_assumptions)
        expected_ds = 675_000 * 0.0575  # $38,812.50
        assert abs(results.annual_ds_io - expected_ds) < 1.0

    def test_dscr_calculation(self, sample_property, sample_assumptions):
        results = underwrite(sample_property, sample_assumptions)
        expected_dscr = results.noi / results.annual_ds_io
        assert abs(results.dscr_y1 - expected_dscr) < 0.001

    def test_irr_5yr_reasonable(self, sample_property, sample_assumptions):
        results = underwrite(sample_property, sample_assumptions)
        if results.irr_5yr is not None:
            assert -0.50 <= results.irr_5yr <= 1.0

    def test_irr_10yr_reasonable(self, sample_property, sample_assumptions):
        results = underwrite(sample_property, sample_assumptions)
        if results.irr_10yr is not None:
            assert -0.50 <= results.irr_10yr <= 1.0

    def test_equity_multiple_positive(self, sample_property, sample_assumptions):
        results = underwrite(sample_property, sample_assumptions)
        assert results.equity_multiple_5yr > 0
        assert results.equity_multiple_10yr > 0

    def test_hold_years_match(self, sample_property, sample_assumptions):
        results = underwrite(sample_property, sample_assumptions)
        assert len(results.yearly_metrics) == sample_assumptions.hold_years

    def test_io_period_in_schedule(self, sample_property, sample_assumptions):
        results = underwrite(sample_property, sample_assumptions)
        for ym in results.yearly_metrics[:7]:
            assert ym["is_io"] is True
        if len(results.yearly_metrics) > 7:
            assert results.yearly_metrics[7]["is_io"] is False

    def test_cash_flows_length(self, sample_property, sample_assumptions):
        results = underwrite(sample_property, sample_assumptions)
        # cash_flows[0] = equity outflow, [1..10] = annual flows
        assert len(results.cash_flows) == sample_assumptions.hold_years + 1

    def test_cash_flow_year0_negative(self, sample_property, sample_assumptions):
        results = underwrite(sample_property, sample_assumptions)
        assert results.cash_flows[0] < 0

    def test_price_per_unit(self, sample_property, sample_assumptions):
        results = underwrite(sample_property, sample_assumptions)
        assert abs(results.price_per_unit - 225_000) < 1.0

    def test_opex_components_sum(self, sample_property, sample_assumptions):
        results = underwrite(sample_property, sample_assumptions)
        component_sum = (results.taxes + results.insurance + results.utilities +
                         results.maintenance + results.mgmt + results.admin + results.capex)
        assert abs(component_sum - results.total_opex) < 0.01


class TestIRR:
    def test_irr_simple(self):
        # -1000 invested, +1200 returned after 1 year → 20% IRR
        cash_flows = [-1000.0, 1200.0]
        irr = compute_irr(cash_flows)
        assert irr is not None
        assert abs(irr - 0.20) < 0.001

    def test_irr_multi_year(self):
        # -1000, +100/year for 9 years, +1100 in year 10 → ~10% IRR
        cash_flows = [-1000.0] + [100.0] * 9 + [1100.0]
        irr = compute_irr(cash_flows)
        assert irr is not None
        assert abs(irr - 0.10) < 0.001

    def test_irr_negative_investment(self):
        # All losses → IRR should be None or very negative
        cash_flows = [-1000.0, -100.0, -100.0]
        irr = compute_irr(cash_flows)
        # Either None or negative
        assert irr is None or irr < 0
