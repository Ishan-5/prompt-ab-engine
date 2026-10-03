"""
Database models for the Prompt A/B Testing Engine.

Table relationships:
    experiments (1) --> (many) variants
    variants    (1) --> (many) assignments
    assignments (1) --> (1)    outcomes
    assignments (1) --> (many) judge_scores   [many because a judge can be re-run,
                                                and human labels also live here]
"""

from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime,
    ForeignKey, Text, JSON, Enum as SAEnum
)
from sqlalchemy.orm import relationship, declarative_base
import enum

Base = declarative_base()


def utcnow():
    return datetime.now(timezone.utc)


class ExperimentStatus(str, enum.Enum):
    running = "running"
    stopped = "stopped"
    concluded = "concluded"


class VariantStatus(str, enum.Enum):
    active = "active"
    killed = "killed"        # auto-killed by guardrail, or manually disabled
    winner = "winner"        # set once an experiment concludes


class Experiment(Base):
    __tablename__ = "experiments"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, unique=True)
    description = Column(Text, nullable=True)
    task_type = Column(String, nullable=False)
    num_looks = Column(Integer, default=0, nullable=False)
    # incremented every time results are checked before conclusion --
    # used to compute the peeking-correction on alpha (see app/stats/sequential.py)
    # e.g. "summarization", "classification" -- used to pick which rule-based
    # checks and judge rubric apply

    status = Column(SAEnum(ExperimentStatus), default=ExperimentStatus.running, nullable=False)

    # Pre-registered experiment design values (fixes the peeking problem --
    # these are set BEFORE data collection, not decided after looking at results)
    minimum_detectable_effect = Column(Float, nullable=True)
    baseline_success_rate = Column(Float, nullable=True)
    required_sample_size_per_variant = Column(Integer, nullable=True)
    significance_alpha = Column(Float, default=0.05, nullable=False)

    created_at = Column(DateTime, default=utcnow, nullable=False)
    concluded_at = Column(DateTime, nullable=True)
    winning_variant_id = Column(Integer, ForeignKey("variants.id"), nullable=True)

    variants = relationship(
        "Variant", back_populates="experiment",
        foreign_keys="Variant.experiment_id"
    )


class Variant(Base):
    __tablename__ = "variants"

    id = Column(Integer, primary_key=True)
    experiment_id = Column(Integer, ForeignKey("experiments.id"), nullable=False)

    name = Column(String, nullable=False)          # e.g. "control", "variant_b"
    prompt_template = Column(Text, nullable=False)
    traffic_weight = Column(Float, default=1.0, nullable=False)
    # relative weight for bucketing, e.g. A=1.0, B=1.0 -> 50/50

    status = Column(SAEnum(VariantStatus), default=VariantStatus.active, nullable=False)
    killed_reason = Column(Text, nullable=True)     # why guardrail killed it, if applicable

    created_at = Column(DateTime, default=utcnow, nullable=False)

    experiment = relationship(
        "Experiment", back_populates="variants",
        foreign_keys=[experiment_id]
    )
    assignments = relationship("Assignment", back_populates="variant")


class Assignment(Base):
    __tablename__ = "assignments"

    id = Column(Integer, primary_key=True)
    experiment_id = Column(Integer, ForeignKey("experiments.id"), nullable=False)
    variant_id = Column(Integer, ForeignKey("variants.id"), nullable=False)

    session_id = Column(String, nullable=False, index=True)
    # who got this variant -- used for consistent hashing verification

    input_query = Column(Text, nullable=False)
    rendered_prompt = Column(Text, nullable=False)   # actual prompt sent, post-templating
    model_output = Column(Text, nullable=True)

    created_at = Column(DateTime, default=utcnow, nullable=False, index=True)

    variant = relationship("Variant", back_populates="assignments")
    outcome = relationship("Outcome", back_populates="assignment", uselist=False)
    judge_scores = relationship("JudgeScore", back_populates="assignment")


class Outcome(Base):
    __tablename__ = "outcomes"

    id = Column(Integer, primary_key=True)
    assignment_id = Column(Integer, ForeignKey("assignments.id"), nullable=False, unique=True)

    rule_based_success = Column(Boolean, nullable=True)
    rule_based_details = Column(JSON, nullable=True)  # e.g. {"length_ok": true, "format_ok": false}

    user_rephrased = Column(Boolean, nullable=True)
    # true if a follow-up message in same session was judged a rephrase/retry

    latency_ms = Column(Float, nullable=True)
    input_tokens = Column(Integer, nullable=True)
    output_tokens = Column(Integer, nullable=True)
    cost_usd = Column(Float, nullable=True)

    created_at = Column(DateTime, default=utcnow, nullable=False)

    assignment = relationship("Assignment", back_populates="outcome")


class JudgeScore(Base):
    __tablename__ = "judge_scores"

    id = Column(Integer, primary_key=True)
    assignment_id = Column(Integer, ForeignKey("assignments.id"), nullable=False)

    source = Column(String, nullable=False)
    # 'llm_judge' or 'human' -- human rows are the validation set

    score = Column(Float, nullable=False)          # normalized 0-1, be consistent
    rubric_version = Column(String, nullable=False)  # so rubric changes don't silently mix
    raw_judge_response = Column(Text, nullable=True)  # for auditing judge reasoning

    created_at = Column(DateTime, default=utcnow, nullable=False)

    assignment = relationship("Assignment", back_populates="judge_scores")