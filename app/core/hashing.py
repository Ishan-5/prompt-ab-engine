"""
Deterministic bucketing for variant assignment, using weighted rendezvous
hashing (HRW).

WHY NOT cumulative weight ranges: an earlier version of this used
`hash(session) -> point in [0,1)` mapped onto contiguous cumulative-weight
ranges per variant. That approach is BROKEN for the property we actually
need: removing a variant reshuffles boundaries for ALL remaining variants,
not just the removed one's sessions (verified failing in
tests/test_hashing.py::test_removing_variant_does_not_reshuffle_everyone).

Rendezvous hashing fixes this: each session gets an INDEPENDENT score
against every variant, and we take the max. A session's relative ranking
between any two variants A and B never depends on whether variant C exists.
So removing C can only reassign sessions whose top choice WAS C -- everyone
else's assignment is untouched. This is the actual definition of consistent
bucketing, not an approximation of it.
"""

import hashlib


def hash_to_unit_interval(key: str) -> float:
    """
    Map an arbitrary string deterministically to a float in (0, 1).

    Uses SHA-256, not Python's built-in hash(), because hash() is randomized
    per-process (PYTHONHASHSEED) -- it would give a different value on every
    server restart, silently breaking consistent bucketing.

    Returns a value strictly greater than 0 (never exactly 0), because the
    rendezvous score formula divides by a log/power of this value and 0
    would break it for low-weight variants.
    """
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    int_value = int(digest[:15], 16)
    max_value = 16 ** 15
    value = int_value / max_value
    return value if value > 0 else 1e-12


def assign_variant(session_id: str, experiment_id: int, active_variants: list[dict]) -> dict:
    """
    Deterministically assign a variant to a session using weighted
    rendezvous hashing.

    active_variants: list of dicts like
        [{"id": 1, "name": "control", "traffic_weight": 1.0},
         {"id": 2, "name": "variant_b", "traffic_weight": 1.0}]

    Returns the assigned variant dict.
    """
    if not active_variants:
        raise ValueError(
            f"No active variants for experiment {experiment_id}. "
            "Cannot assign -- experiment may need to be stopped."
        )

    best_variant = None
    best_score = -1.0

    for variant in active_variants:
        weight = variant["traffic_weight"]
        if weight <= 0:
            continue  # zero/negative weight variants never win

        key = f"{session_id}:{experiment_id}:{variant['id']}"
        u = hash_to_unit_interval(key)

        # Weighted rendezvous hashing score. Higher weight -> u^(1/w) pushed
        # closer to 1 on average -> more likely to win the max.
        score = u ** (1.0 / weight)

        if score > best_score:
            best_score = score
            best_variant = variant

    if best_variant is None:
        raise ValueError(f"All variants have zero/negative weight for experiment {experiment_id}.")

    return best_variant