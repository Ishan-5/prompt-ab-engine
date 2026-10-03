"""
Pydantic schemas for API request/response validation.

Kept separate from the SQLAlchemy models (app/db/models.py) deliberately --
API contracts and DB schema are different concerns and will drift from each
other over time (e.g. API might expose computed fields the DB doesn't store).
Conflating them is a common shortcut that causes pain later.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime


class VariantCreate(BaseModel):
    name: str
    prompt_template: str
    traffic_weight: float = Field(default=1.0, gt=0)


class ExperimentCreate(BaseModel):
    name: str
    description: Optional[str] = None
    task_type: str
    variants: list[VariantCreate]

    # Pre-registration fields -- REQUIRED, not optional. This is deliberate:
    # you cannot create an experiment without stating up front what effect
    # size you care about detecting. This is the mechanism that actually
    # prevents the peeking problem, not a nice-to-have.
    baseline_success_rate: float = Field(gt=0, lt=1)
    minimum_detectable_effect: float = Field(gt=0)
    significance_alpha: float = Field(default=0.05, gt=0, lt=1)

    @field_validator("variants")
    @classmethod
    def must_have_at_least_two_variants(cls, v):
        if len(v) < 2:
            raise ValueError("An experiment needs at least 2 variants to compare")
        return v


class VariantOut(BaseModel):
    id: int
    name: str
    prompt_template: str
    traffic_weight: float
    status: str

    class Config:
        from_attributes = True


class ExperimentOut(BaseModel):
    id: int
    name: str
    description: Optional[str]
    task_type: str
    status: str
    baseline_success_rate: Optional[float]
    minimum_detectable_effect: Optional[float]
    required_sample_size_per_variant: Optional[int]
    significance_alpha: float
    created_at: datetime
    variants: list[VariantOut]

    class Config:
        from_attributes = True

class AssignRequest(BaseModel):
    experiment_id: int
    session_id: str
    input_query: str


class AssignResponse(BaseModel):
    assignment_id: int
    variant_id: int
    variant_name: str
    rendered_prompt: str

class CompleteRequest(BaseModel):
    assignment_id: int


class CompleteResponse(BaseModel):
    assignment_id: int
    output_text: str
    latency_ms: float
    input_tokens: int
    output_tokens: int
    cost_usd: float
    rule_based_success: bool