"""
Sample size / power analysis for the success-rate significance test.

Why this exists: without deciding sample size UP FRONT based on the effect
size you actually care about, "statistical significance" becomes decorative
-- you just stare at a p-value until it crosses 0.05, which is the peeking
problem. This function answers the question BEFORE data collection: "given
a baseline success rate and the smallest improvement worth caring about,
how many samples per variant do I need?"
"""

import math
from scipy import stats


def required_sample_size(
    baseline_rate: float,
    minimum_detectable_effect: float,
    alpha: float = 0.05,
    power: float = 0.8,
) -> int:
    """
    Sample size per variant for a two-proportion z-test.

    baseline_rate: expected success rate of control, e.g. 0.6
    minimum_detectable_effect: smallest absolute difference worth detecting,
        e.g. 0.05 means "I care about detecting a 5 percentage point lift"
    alpha: significance level (false positive rate), default 5%
    power: probability of detecting the effect if it's real, default 80%
        (this is the standard default in experiment design -- lower power
        means you'll frequently miss real effects)

    Returns: required sample size PER VARIANT (not total).
    """
    if not (0 < baseline_rate < 1):
        raise ValueError("baseline_rate must be between 0 and 1")
    if minimum_detectable_effect <= 0:
        raise ValueError("minimum_detectable_effect must be positive")

    p1 = baseline_rate
    p2 = baseline_rate + minimum_detectable_effect
    p2 = min(p2, 0.999)  # guard against overshooting 1.0

    z_alpha = stats.norm.ppf(1 - alpha / 2)   # two-tailed
    z_beta = stats.norm.ppf(power)

    p_bar = (p1 + p2) / 2
    q_bar = 1 - p_bar

    numerator = (
        z_alpha * math.sqrt(2 * p_bar * q_bar) +
        z_beta * math.sqrt(p1 * (1 - p1) + p2 * (1 - p2))
    ) ** 2
    denominator = (p2 - p1) ** 2

    n = numerator / denominator
    return math.ceil(n)