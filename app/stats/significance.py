"""
Core statistical tests.

Success rate (categorical: succeeded / failed) -> chi-squared test of
independence. This is correct for comparing two proportions.

Latency / cost (continuous, right-skewed) -> Mann-Whitney U test, NOT a
t-test. A t-test assumes approximately normal distributions; LLM latency
and cost are typically right-skewed (a few slow/expensive calls dominate),
so the normality assumption is usually violated. Mann-Whitney U is a
non-parametric test that doesn't require that assumption -- it tests
whether one distribution tends to produce larger values than the other,
which is what we actually want to know.
"""

from scipy import stats
import numpy as np


def compare_success_rates(success_a: int, total_a: int, success_b: int, total_b: int) -> dict:
    if total_a == 0 or total_b == 0:
        raise ValueError("Both variants need at least 1 sample to compare")

    fail_a = total_a - success_a
    fail_b = total_b - success_b

    rate_a = success_a / total_a
    rate_b = success_b / total_b

    # Degenerate case: chi-squared requires variation in both success AND
    # failure columns. If both variants have (near-)0% or (near-)100%
    # failure rate, there's no variance to test -- this isn't a computation
    # error, it means the rule-based check has essentially no discriminating
    # power on this data (everything passes or everything fails). Report
    # this explicitly instead of crashing or silently returning a bogus
    # p-value.
    if (fail_a == 0 and fail_b == 0) or (success_a == 0 and success_b == 0):
        return {
            "rate_a": rate_a,
            "rate_b": rate_b,
            "ci_a": _wilson_score_interval(success_a, total_a),
            "ci_b": _wilson_score_interval(success_b, total_b),
            "chi2_statistic": None,
            "p_value": None,
            "absolute_lift": rate_b - rate_a,
            "degenerate": True,
            "degenerate_reason": (
                "Both variants have identical success/failure composition "
                "(no variance) -- chi-squared is undefined. Rule-based check "
                "likely has near-zero discriminating power on this data; "
                "consider LLM-judge scoring instead."
            ),
        }

    contingency_table = [[success_a, fail_a], [success_b, fail_b]]
    chi2, p_value, dof, expected = stats.chi2_contingency(contingency_table, correction=False)

    return {
        "rate_a": rate_a,
        "rate_b": rate_b,
        "ci_a": _wilson_score_interval(success_a, total_a),
        "ci_b": _wilson_score_interval(success_b, total_b),
        "chi2_statistic": chi2,
        "p_value": p_value,
        "absolute_lift": rate_b - rate_a,
        "degenerate": False,
    }

def _wilson_score_interval(successes: int, total: int, confidence: float = 0.95) -> tuple[float, float]:
    """
    Wilson score confidence interval for a proportion. More accurate than
    the naive (p +/- z*sqrt(p(1-p)/n)) normal approximation, especially
    when the success rate is close to 0 or 1 or the sample is small --
    the naive interval can produce nonsensical bounds outside [0,1] in
    those cases; Wilson score cannot.
    """
    if total == 0:
        return (0.0, 0.0)

    z = stats.norm.ppf(1 - (1 - confidence) / 2)
    p = successes / total
    n = total

    denominator = 1 + z**2 / n
    center = (p + z**2 / (2 * n)) / denominator
    margin = (z * ((p * (1 - p) / n + z**2 / (4 * n**2)) ** 0.5)) / denominator

    lower = max(0.0, center - margin)
    upper = min(1.0, center + margin)
    return (lower, upper)




def compare_continuous_metric(values_a: list[float], values_b: list[float]) -> dict:
    """
    Mann-Whitney U test comparing a continuous metric (latency_ms, cost_usd)
    between two variants. Non-parametric -- does not assume normal
    distributions.

    Reports MEDIAN, not mean, alongside the test -- median is the
    appropriate summary statistic for right-skewed data (mean gets pulled
    up by outlier-slow requests and misrepresents the "typical" case).
    """
    if len(values_a) == 0 or len(values_b) == 0:
        raise ValueError("Both variants need at least 1 sample to compare")

    statistic, p_value = stats.mannwhitneyu(values_a, values_b, alternative="two-sided")

    return {
        "median_a": float(np.median(values_a)),
        "median_b": float(np.median(values_b)),
        "u_statistic": float(statistic),
        "p_value": float(p_value),
    }