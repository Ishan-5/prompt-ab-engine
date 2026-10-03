"""
Aggregates outcomes per variant and produces a verdict.

Verdict states:
  - "not_enough_data": sample size per variant hasn't hit the
    pre-registered required_sample_size_per_variant yet. We refuse to
    call significance here, full stop -- this is what actually prevents
    the peeking problem at the source, not just the alpha correction.
  - "no_significant_difference": enough data, but p-value (after peeking
    correction) doesn't clear the bar.
  - "variant_X_wins": enough data AND statistically significant AND
    that variant has the better rate.

Every call to this function that has enough data to run a real test
increments Experiment.num_looks -- this is what feeds the peeking
correction. Calls that bail out at "not_enough_data" do NOT increment
num_looks, since no actual statistical test was performed.
"""

from sqlalchemy.orm import Session
from app.db.models import Experiment, Variant, Assignment, Outcome
from app.stats.significance import compare_success_rates, compare_continuous_metric
from app.stats.sequential import corrected_alpha


def get_variant_outcomes(db: Session, variant_id: int) -> list[Outcome]:
    return (
        db.query(Outcome)
        .join(Assignment, Outcome.assignment_id == Assignment.id)
        .filter(Assignment.variant_id == variant_id)
        .all()
    )


def compute_results(db: Session, experiment_id: int) -> dict:
    experiment = db.query(Experiment).filter(Experiment.id == experiment_id).first()
    if not experiment:
        raise ValueError(f"Experiment {experiment_id} not found")

    variants = db.query(Variant).filter(Variant.experiment_id == experiment_id).all()
    if len(variants) != 2:
        raise ValueError(
            "compute_results currently supports exactly 2 variants. "
            "Multi-variant comparison needs multiple-comparison correction "
            "(Bonferroni/BH across pairs) -- not implemented yet, deliberately "
            "out of scope until 2-variant case is proven correct."
        )

    variant_data = {}
    for v in variants:
        outcomes = get_variant_outcomes(db, v.id)
        variant_data[v.id] = {
            "name": v.name,
            "n": len(outcomes),
            "success_count": sum(1 for o in outcomes if o.rule_based_success),
            "latencies": [o.latency_ms for o in outcomes if o.latency_ms is not None],
            "costs": [o.cost_usd for o in outcomes if o.cost_usd is not None],
        }

    variant_ids = list(variant_data.keys())
    a_id, b_id = variant_ids[0], variant_ids[1]
    n_a, n_b = variant_data[a_id]["n"], variant_data[b_id]["n"]

    required_n = experiment.required_sample_size_per_variant

    result = {
        "experiment_id": experiment_id,
        "experiment_name": experiment.name,
        "required_sample_size_per_variant": required_n,
        "current_n": {variant_data[a_id]["name"]: n_a, variant_data[b_id]["name"]: n_b},
        "num_looks": experiment.num_looks,
    }

    if n_a < required_n or n_b < required_n:
        result["verdict"] = "not_enough_data"
        result["progress"] = {
            variant_data[a_id]["name"]: f"{n_a}/{required_n}",
            variant_data[b_id]["name"]: f"{n_b}/{required_n}",
        }
        return result

    # Compute the test FIRST. Only count this as a "look" (and pay the
    # peeking-correction cost) once we know the computation actually
    # succeeded -- a crash/exception before this point must not silently
    # consume a look, or a transient failure permanently tightens the
    # significance bar for no reason.
    success_test = compare_success_rates(
        success_a=variant_data[a_id]["success_count"], total_a=n_a,
        success_b=variant_data[b_id]["success_count"], total_b=n_b,
    )

    experiment.num_looks += 1
    db.commit()

    effective_alpha = corrected_alpha(experiment.significance_alpha, experiment.num_looks)

    result["success_rate_test"] = success_test
    if success_test.get("degenerate"):
        result["verdict"] = "no_significant_difference"
        result["verdict_note"] = success_test["degenerate_reason"]
        return result
    result["effective_alpha_after_peeking_correction"] = effective_alpha
    result["base_alpha"] = experiment.significance_alpha

    if variant_data[a_id]["latencies"] and variant_data[b_id]["latencies"]:
        result["latency_test"] = compare_continuous_metric(
            variant_data[a_id]["latencies"], variant_data[b_id]["latencies"]
        )
    if variant_data[a_id]["costs"] and variant_data[b_id]["costs"]:
        result["cost_test"] = compare_continuous_metric(
            variant_data[a_id]["costs"], variant_data[b_id]["costs"]
        )

    if success_test["p_value"] is not None and success_test["p_value"] < effective_alpha:
        winner_id = b_id if success_test["absolute_lift"] > 0 else a_id
        result["verdict"] = f"{variant_data[winner_id]['name']}_wins"
        result["winning_variant_id"] = winner_id
    else:
        result["verdict"] = "no_significant_difference"

    return result