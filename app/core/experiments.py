"""
Business logic for creating and reading experiments.

Kept separate from the API route file (app/api/experiments.py) so this
logic is independently testable without spinning up FastAPI / HTTP.
"""

from sqlalchemy.orm import Session
from app.db.models import Experiment, Variant, ExperimentStatus, VariantStatus
from app.core.schemas import ExperimentCreate
from app.stats.power import required_sample_size


def create_experiment(db: Session, payload: ExperimentCreate) -> Experiment:
    """
    Creates an experiment and its variants in one transaction.

    Computes and STORES required_sample_size_per_variant at creation time --
    this number is fixed once and read later by the significance-check logic
    to decide whether the experiment has enough data to draw a conclusion
    yet. It is never recomputed after the fact based on how results look.
    """
    sample_size = required_sample_size(
        baseline_rate=payload.baseline_success_rate,
        minimum_detectable_effect=payload.minimum_detectable_effect,
        alpha=payload.significance_alpha,
    )

    experiment = Experiment(
        name=payload.name,
        description=payload.description,
        task_type=payload.task_type,
        status=ExperimentStatus.running,
        baseline_success_rate=payload.baseline_success_rate,
        minimum_detectable_effect=payload.minimum_detectable_effect,
        required_sample_size_per_variant=sample_size,
        significance_alpha=payload.significance_alpha,
    )
    db.add(experiment)
    db.flush()  # assigns experiment.id without committing yet

    for v in payload.variants:
        variant = Variant(
            experiment_id=experiment.id,
            name=v.name,
            prompt_template=v.prompt_template,
            traffic_weight=v.traffic_weight,
            status=VariantStatus.active,
        )
        db.add(variant)

    db.commit()
    db.refresh(experiment)
    return experiment


def get_experiment(db: Session, experiment_id: int) -> Experiment | None:
    return db.query(Experiment).filter(Experiment.id == experiment_id).first()


def list_experiments(db: Session) -> list[Experiment]:
    return db.query(Experiment).order_by(Experiment.created_at.desc()).all()


def get_active_variants(db: Session, experiment_id: int) -> list[Variant]:
    """
    Returns only ACTIVE variants -- killed variants must never receive new
    traffic. This is what feeds into app.core.hashing.assign_variant().
    """
    return (
        db.query(Variant)
        .filter(Variant.experiment_id == experiment_id, Variant.status == VariantStatus.active)
        .all()
    )