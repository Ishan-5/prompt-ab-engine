"""
Rule-based success checks.

These are cheap, deterministic checks that don't require an LLM call.
Deliberately simple for now (length + non-empty) -- task-specific checks
(e.g. "is this valid JSON", "did generated code pass tests") get added
per task_type as the project grows. Do not oversell these as "quality"
checks; they check for OBVIOUS failure, not good output.
"""


def check_basic_output_validity(output_text: str, min_length: int = 10, max_length: int = 2000) -> dict:
    """
    Returns dict of individual check results + overall pass/fail.
    Stored in Outcome.rule_based_details as JSON, so keep keys stable.
    """
    if output_text is None:
        return {
            "non_empty": False,
            "length_ok": False,
            "overall_pass": False,
        }

    stripped = output_text.strip()
    non_empty = len(stripped) > 0
    length_ok = min_length <= len(stripped) <= max_length

    return {
        "non_empty": non_empty,
        "length_ok": length_ok,
        "overall_pass": non_empty and length_ok,
    }