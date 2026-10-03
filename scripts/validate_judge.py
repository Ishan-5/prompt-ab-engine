"""
Human validation of the LLM judge.

Pulls a random sample of completed assignments, shows you the original
query + model output, asks YOU to score it 1-5 using the same rubric the
judge uses, and stores your score in judge_scores with source='human'.

This produces the data needed to compute judge/human agreement -- the
thing that actually tells us whether the judge's scores mean anything.
"""

import sys, os, random
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db.session import SessionLocal
from app.db.models import Assignment, JudgeScore
from app.judge.llm_judge import RUBRIC_VERSION

RUBRIC_TEXT = """
1 = Summary is irrelevant, empty, or nonsensical given the original text
2 = Summary is on-topic but misses most key information or is confusing
3 = Summary captures some key points but omits important information or includes irrelevant details
4 = Summary captures the main points accurately and concisely, minor omissions acceptable
5 = Summary is accurate, concise, and captures all essential information
"""


def run(sample_size: int = 25):
    db = SessionLocal()

    # Only sample assignments that HAVE a judge score already, so we can
    # directly compare human vs judge on the exact same output.
    candidates = (
        db.query(Assignment)
        .join(JudgeScore, JudgeScore.assignment_id == Assignment.id)
        .filter(JudgeScore.source == "llm_judge")
        .filter(Assignment.model_output.isnot(None))
        .all()
    )

    if len(candidates) < sample_size:
        print(f"Only {len(candidates)} judge-scored assignments available, "
              f"using all of them instead of {sample_size}.")
        sample_size = len(candidates)

    sample = random.sample(candidates, sample_size)

    print(f"\nScoring {sample_size} outputs. Rubric:\n{RUBRIC_TEXT}\n")
    print("Type a score 1-5 and press Enter. Type 'skip' to skip.\n")

    scored = 0
    for i, assignment in enumerate(sample):
        judge_score = (
            db.query(JudgeScore)
            .filter(JudgeScore.assignment_id == assignment.id, JudgeScore.source == "llm_judge")
            .first()
        )

        print(f"\n--- [{i+1}/{sample_size}] assignment_id={assignment.id} ---")
        print(f"ORIGINAL QUERY:\n{assignment.input_query}\n")
        print(f"MODEL OUTPUT:\n{assignment.model_output}\n")

        while True:
            raw = input("Your score (1-5, or 'skip'): ").strip()
            if raw.lower() == "skip":
                break
            if raw in {"1", "2", "3", "4", "5"}:
                human_score_raw = int(raw)
                normalized = (human_score_raw - 1) / 4

                existing = (
                    db.query(JudgeScore)
                    .filter(JudgeScore.assignment_id == assignment.id, JudgeScore.source == "human")
                    .first()
                )
                if existing:
                    print("  (already have a human score for this one, skipping insert)")
                    break

                human_row = JudgeScore(
                    assignment_id=assignment.id,
                    source="human",
                    score=normalized,
                    rubric_version=RUBRIC_VERSION,
                    raw_judge_response=None,
                )
                db.add(human_row)
                db.commit()
                scored += 1

                # Don't show the judge's score until after you commit yours --
                # seeing it first would bias your rating toward agreement.
                print(f"  Judge scored this: {judge_score.score * 4 + 1:.0f}/5")
                break
            print("  Invalid input, enter 1-5 or 'skip'.")

    print(f"\nDone. Scored {scored} outputs.")
    db.close()


if __name__ == "__main__":
    run(sample_size=25)