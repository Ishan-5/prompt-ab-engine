import os
import json
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# Switched to a larger model specifically for judging. Using a bigger judge
# than the model being evaluated is standard practice -- a same-or-smaller
# judge tends to have compressed, low-resolution scoring (confirmed
# empirically in our own validation: llama-3.1-8b-instant collapsed to a
# constant score regardless of rubric wording, across two rubric versions).
JUDGE_MODEL = "llama-3.3-70b-versatile"

RUBRIC_VERSION = "summarization_v3"

JUDGE_SYSTEM_PROMPT = """You are a strict evaluator comparing a summary against an original article.

Step 1: List every distinct fact in the original text (numbers, causes, consequences, named entities, outcomes).
Step 2: For each fact, check if the summary includes it, omits it, or distorts it.
Step 3: Count the omissions/distortions.
Step 4: Assign a score using ONLY this mapping:
  0 omissions/distortions AND no awkward phrasing -> 5
  0 omissions/distortions BUT some awkward phrasing or unnecessary length -> 4
  1 omission -> 3
  2+ omissions, or any distortion of a fact -> 2
  Summary is off-topic, empty, or nonsensical -> 1

Respond with ONLY a JSON object, nothing else:
{"omissions_found": ["<fact omitted or distorted, if any>"], "score": <integer 1-5>, "reasoning": "<one sentence>"}"""


def judge_summary(original_text: str, summary: str) -> dict:
    user_prompt = f"ORIGINAL TEXT:\n{original_text}\n\nSUMMARY:\n{summary}"

    response = _client.chat.completions.create(
        model=JUDGE_MODEL,
        messages=[
            {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        max_tokens=300,
        temperature=0,
    )

    raw_text = response.choices[0].message.content.strip()

    try:
        cleaned = raw_text.replace("```json", "").replace("```", "").strip()
        parsed = json.loads(cleaned)
        raw_score = int(parsed["score"])
        reasoning = parsed.get("reasoning", "")
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        raise ValueError(f"Judge returned unparseable response: {raw_text!r}") from e

    if not (1 <= raw_score <= 5):
        raise ValueError(f"Judge returned out-of-range score: {raw_score}")

    normalized_score = (raw_score - 1) / 4

    return {
        "score": normalized_score,
        "raw_score": raw_score,
        "reasoning": reasoning,
        "rubric_version": RUBRIC_VERSION,
        "raw_judge_response": raw_text,
    }