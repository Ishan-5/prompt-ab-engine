"""
HTTP routes for experiment management.
"""
from app.core import completion as completion_logic
from app.core.schemas import CompleteRequest, CompleteResponse
from app.core.schemas import AssignRequest, AssignResponse
from app.core import assignment as assignment_logic
from app.core import results as results_logic
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.schemas import ExperimentCreate, ExperimentOut
from app.core import experiments as experiment_logic

router = APIRouter(prefix="/experiments", tags=["experiments"])


@router.post("/", response_model=ExperimentOut, status_code=201)
def create_experiment_route(payload: ExperimentCreate, db: Session = Depends(get_db)):
    try:
        experiment = experiment_logic.create_experiment(db, payload)
        return experiment
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/", response_model=list[ExperimentOut])
def list_experiments_route(db: Session = Depends(get_db)):
    return experiment_logic.list_experiments(db)


@router.get("/{experiment_id}", response_model=ExperimentOut)
def get_experiment_route(experiment_id: int, db: Session = Depends(get_db)):
    experiment = experiment_logic.get_experiment(db, experiment_id)
    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")
    return experiment
@router.post("/assign", response_model=AssignResponse)
def assign_variant_route(payload: AssignRequest, db: Session = Depends(get_db)):
    try:
        assignment = assignment_logic.assign_and_log(
            db,
            experiment_id=payload.experiment_id,
            session_id=payload.session_id,
            input_query=payload.input_query,
        )
        return AssignResponse(
            assignment_id=assignment.id,
            variant_id=assignment.variant_id,
            variant_name=assignment.variant.name,
            rendered_prompt=assignment.rendered_prompt,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
@router.post("/complete", response_model=CompleteResponse)
def complete_assignment_route(payload: CompleteRequest, db: Session = Depends(get_db)):
    try:
        outcome = completion_logic.complete_assignment(db, payload.assignment_id)
        return CompleteResponse(
            assignment_id=outcome.assignment_id,
            output_text=outcome.assignment.model_output,
            latency_ms=outcome.latency_ms,
            input_tokens=outcome.input_tokens,
            output_tokens=outcome.output_tokens,
            cost_usd=outcome.cost_usd,
            rule_based_success=outcome.rule_based_success,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    


@router.get("/{experiment_id}/results")
def get_results_route(experiment_id: int, db: Session = Depends(get_db)):
    try:
        return results_logic.compute_results(db, experiment_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))