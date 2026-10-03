"""
Peeking correction for repeated significance checks.

PROBLEM: if you check p-value continuously and stop the moment p < 0.05,
your real false-positive rate is much higher than 5% -- this is the
"optional stopping" / peeking problem, the single most common statistical
error in ad-hoc A/B testing.

WHAT WE DO: a conservative Bonferroni correction based on how many times
results have been checked (num_looks). Divide alpha by the number of looks
so far, so the effective significance bar gets stricter each time someone
checks early.

WHAT THIS IS NOT: true sequential testing (e.g. O'Brien-Fleming alpha
spending, always-valid p-values / e-values) is more statistically
efficient -- it doesn't waste as much power as Bonferroni does. We chose
Bonferroni deliberately for simplicity and auditability over
maximum statistical power. This is a stated tradeoff, not an oversight.
"""


def corrected_alpha(base_alpha: float, num_looks: int) -> float:
    """
    Returns the alpha threshold to actually use for THIS look, given how
    many times the experiment has been checked so far (including this one).
    """
    if num_looks < 1:
        raise ValueError("num_looks must be >= 1")
    return base_alpha / num_looks