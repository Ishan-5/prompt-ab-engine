"""
Ties together variant selection (hashing) + prompt rendering + DB logging
into a single operation: assign a session to a variant for an experiment.
"""

from sqlalchemy.orm import Session
from app.db.models import Assignment, Experiment, ExperimentStatus
from app.core.hashing import assign_variant
from app.core import experiments as experiment_logic


def render_prompt(template: str, input_query: str) -> str:
    """
    Fills the variant's prompt template with the user's input.

    Uses a simple {text} placeholder convention. If the template doesn't
    contain {text}, we append the query -- this is a deliberate fallback
    rather than raising, so a malformed template doesn't crash a live
    request; but we should still log a warning path for this in a real
    system (noted, not built yet -- out of scope for this step).
    """
    if "{text}" in template:
        return template.format(text=input_query)
    return f"{template}\n\n{input_query}"


def assign_and_log(db: Session, experiment_id: int, session_id: str, input_query: str) -> Assignment:
    experiment = experiment_logic.get_experiment(db, experiment_id)
    if not experiment:
        raise ValueError(f"Experiment {experiment_id} not found")

    if experiment.status != ExperimentStatus.running:
        raise ValueError(
            f"Experiment {experiment_id} is not running (status={experiment.status.value}). "
            "Cannot assign new traffic to a stopped/concluded experiment."
        )

    active_variants = experiment_logic.get_active_variants(db, experiment_id)
    active_variant_dicts = [
        {"id": v.id, "name": v.name, "traffic_weight": v.traffic_weight}
        for v in active_variants
    ]

    chosen = assign_variant(session_id, experiment_id, active_variant_dicts)

    # Need the actual Variant object to get its prompt_template
    chosen_variant = next(v for v in active_variants if v.id == chosen["id"])
    rendered = render_prompt(chosen_variant.prompt_template, input_query)

    assignment = Assignment(
        experiment_id=experiment_id,
        variant_id=chosen_variant.id,
        session_id=session_id,
        input_query=input_query,
        rendered_prompt=rendered,
        model_output=None,  # filled in later, after the LLM call happens
    )
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    return assignment