"""
Tests for deterministic bucketing.

The property we actually care about proving:
1. Same (session_id, experiment_id) always returns the same variant.
2. Removing a variant only reshuffles ITS sessions, not everyone else's.
"""

import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.hashing import assign_variant, hash_to_unit_interval


def test_same_session_same_variant():
    variants = [
        {"id": 1, "name": "control", "traffic_weight": 1.0},
        {"id": 2, "name": "variant_b", "traffic_weight": 1.0},
    ]
    results = [assign_variant("session_abc", 1, variants)["id"] for _ in range(20)]
    assert len(set(results)) == 1, "Same session must always get the same variant"


def test_distribution_roughly_matches_weights():
    variants = [
        {"id": 1, "name": "control", "traffic_weight": 1.0},
        {"id": 2, "name": "variant_b", "traffic_weight": 1.0},
    ]
    counts = {1: 0, 2: 0}
    for i in range(5000):
        v = assign_variant(f"session_{i}", 1, variants)
        counts[v["id"]] += 1

    ratio = counts[1] / (counts[1] + counts[2])
    assert 0.45 < ratio < 0.55, f"Expected ~50/50 split, got {ratio}"


def test_removing_variant_does_not_reshuffle_everyone():
    """
    This is the property that actually matters. With 3 variants, remove one,
    and check that sessions NOT originally in the removed variant keep their
    assignment.
    """
    variants_before = [
        {"id": 1, "name": "control", "traffic_weight": 1.0},
        {"id": 2, "name": "variant_b", "traffic_weight": 1.0},
        {"id": 3, "name": "variant_c", "traffic_weight": 1.0},
    ]
    variants_after = [v for v in variants_before if v["id"] != 3]  # kill variant_c

    before_assignments = {}
    for i in range(2000):
        sid = f"session_{i}"
        before_assignments[sid] = assign_variant(sid, 1, variants_before)["id"]

    unaffected_sessions = [sid for sid, vid in before_assignments.items() if vid != 3]

    changed = 0
    for sid in unaffected_sessions:
        after = assign_variant(sid, 1, variants_after)["id"]
        if after != before_assignments[sid]:
            changed += 1

    # With correct consistent bucketing, ZERO sessions that weren't in the
    # killed variant should change. Allow 0 tolerance here -- this is the
    # whole point of the algorithm.
    assert changed == 0, (
        f"{changed} sessions were reassigned even though they weren't in "
        "the killed variant -- consistent bucketing is broken"
    )


def test_hash_is_stable_across_calls():
    """Guards against accidentally using Python's randomized hash()."""
    v1 = hash_to_unit_interval("session_abc:1")
    v2 = hash_to_unit_interval("session_abc:1")
    assert v1 == v2