"""
Groq LLM call wrapper.

Kept as a thin, isolated wrapper (not scattered inline in route handlers)
so it's the single place that knows about Groq's API shape. If you ever
swap providers, this is the only file that changes.
"""

import os
import time
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# Groq pricing changes over time and varies by model -- hardcoding a rate
# here is a known simplification. Check https://groq.com/pricing for current
# rates and update this if the model changes. This is stated explicitly so
# it's not mistaken for a live pricing lookup.
MODEL_NAME = "llama-3.1-8b-instant"
PRICE_PER_1M_INPUT_TOKENS = 0.05
PRICE_PER_1M_OUTPUT_TOKENS = 0.08


def call_llm(prompt: str) -> dict:
    """
    Sends a prompt to Groq, returns output text + measured latency + token
    usage + estimated cost.

    Returns dict with keys: output_text, latency_ms, input_tokens,
    output_tokens, cost_usd.

    Raises the underlying exception on failure -- caller decides how to
    handle it (we do NOT swallow errors here, since a silently-failed LLM
    call producing empty output would corrupt the outcome data).
    """
    start = time.perf_counter()

    response = _client.chat.completions.create(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=500,
    )

    latency_ms = (time.perf_counter() - start) * 1000

    output_text = response.choices[0].message.content
    input_tokens = response.usage.prompt_tokens
    output_tokens = response.usage.completion_tokens

    cost_usd = (
        (input_tokens / 1_000_000) * PRICE_PER_1M_INPUT_TOKENS +
        (output_tokens / 1_000_000) * PRICE_PER_1M_OUTPUT_TOKENS
    )

    return {
        "output_text": output_text,
        "latency_ms": latency_ms,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_usd": cost_usd,
    }