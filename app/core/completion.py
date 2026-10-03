"""
Runs the LLM call for a given assignment, writes model_output back to the
Assignment row, and creates the corresponding Outcome + JudgeScore rows.
"""

from sqlalchemy.orm import Session
from app.db.models import Assignment, Outcome, JudgeScore
from app.core.llm import call_llm
from app.judge.rules import check_basic_output_validity
from app.judge.llm_judge import judge_summary


def complete_assignment(db: Session, assignment_id: int) -> Outcome:
    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment:
        raise ValueError(f"Assignment {assignment_id} not found")

    if assignment.outcome is not None:
        raise ValueError(f"Assignment {assignment_id} already has an outcome logged")

    result = call_llm(assignment.rendered_prompt)
    assignment.model_output = result["output_text"]

    rule_result = check_basic_output_validity(result["output_text"])

    outcome = Outcome(
        assignment_id=assignment.id,
        rule_based_success=rule_result["overall_pass"],
        rule_based_details=rule_result,
        latency_ms=result["latency_ms"],
        input_tokens=result["input_tokens"],
        output_tokens=result["output_tokens"],
        cost_usd=result["cost_usd"],
    )
    db.add(outcome)

    # Judge call is best-effort: if it fails (rate limit, malformed
    # response), we do NOT fail the whole completion -- the rule-based
    # outcome is still valid and saved. We log the judge failure rather
    # than silently swallowing it.
    try:
        judge_result = judge_summary(
            original_text=assignment.input_query,
            summary=result["output_text"],
        )
        judge_score = JudgeScore(
            assignment_id=assignment.id,
            source="llm_judge",
            score=judge_result["score"],
            rubric_version=judge_result["rubric_version"],
            raw_judge_response=judge_result["raw_judge_response"],
        )
        db.add(judge_score)
    except Exception as e:
        print(f"[WARN] Judge scoring failed for assignment {assignment_id}: {e}")

    db.commit()
    db.refresh(outcome)
    return outcome