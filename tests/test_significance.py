import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.stats.significance import compare_success_rates, compare_continuous_metric
from app.stats.sequential import corrected_alpha


def test_clearly_different_success_rates_significant():
    # 30% vs 70% success rate, decent sample -- should be clearly significant
    result = compare_success_rates(success_a=30, total_a=100, success_b=70, total_b=100)
    assert result["p_value"] < 0.001
    assert result["absolute_lift"] > 0.35


def test_identical_success_rates_not_significant():
    result = compare_success_rates(success_a=50, total_a=100, success_b=51, total_b=100)
    assert result["p_value"] > 0.05


def test_continuous_metric_clear_difference():
    fast = [100, 110, 105, 95, 102] * 10
    slow = [500, 480, 510, 495, 505] * 10
    result = compare_continuous_metric(fast, slow)
    assert result["p_value"] < 0.001
    assert result["median_a"] < result["median_b"]


def test_corrected_alpha_gets_stricter_with_more_looks():
    a1 = corrected_alpha(0.05, 1)
    a5 = corrected_alpha(0.05, 5)
    assert a5 < a1
    assert a1 == 0.05


def test_corrected_alpha_rejects_zero_looks():
    import pytest
    with pytest.raises(ValueError):
        corrected_alpha(0.05, 0)

def test_degenerate_case_no_variance_does_not_crash():
    # both variants 100% success -- no failures at all
    result = compare_success_rates(success_a=214, total_a=214, success_b=207, total_b=207)
    assert result["degenerate"] is True
    assert result["p_value"] is None