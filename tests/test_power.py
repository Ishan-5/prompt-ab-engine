"""
Sanity checks for sample size calculation against known reference values.
These numbers are checkable against any standard A/B test sample size
calculator (e.g. Evan Miller's calculator) -- if these drift, the formula
is wrong.
"""

import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.stats.power import required_sample_size


def test_known_reference_case():
    # baseline 20%, detect a 5pp lift (20% -> 25%), alpha=0.05, power=0.8
    # Reference calculators give ~1090-1100 per variant for this input.
    n = required_sample_size(baseline_rate=0.20, minimum_detectable_effect=0.05)
    assert 1000 < n < 1200, f"Expected ~1090, got {n}"


def test_smaller_effect_needs_more_samples():
    n_small_effect = required_sample_size(baseline_rate=0.20, minimum_detectable_effect=0.02)
    n_large_effect = required_sample_size(baseline_rate=0.20, minimum_detectable_effect=0.10)
    assert n_small_effect > n_large_effect, (
        "Detecting a smaller effect must require MORE samples, not fewer"
    )


def test_invalid_inputs_raise():
    import pytest
    with pytest.raises(ValueError):
        required_sample_size(baseline_rate=1.5, minimum_detectable_effect=0.05)
    with pytest.raises(ValueError):
        required_sample_size(baseline_rate=0.5, minimum_detectable_effect=-0.1)