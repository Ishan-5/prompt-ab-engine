"""
Replays a labeled query dataset through assign -> complete, repeatedly,
to generate realistic traffic volume for demo purposes.

This is explicitly SYNTHETIC replay, not live user traffic -- stated
outright, not implied otherwise. Real live traffic would come through the
same /assign and /complete endpoints organically; this script just drives
volume through the same code path for demonstration.

Usage: python3 scripts/replay_traffic.py --experiment-id 1 --count 400
"""

import argparse
import json
import time
import uuid
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import httpx

BASE_URL = "http://127.0.0.1:8000"
DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "queries.jsonl")


def load_queries() -> list[str]:
    queries = []
    with open(DATA_PATH, "r") as f:
        for line in f:
            line = line.strip()
            if line:
                queries.append(json.loads(line)["query"])
    if not queries:
        raise RuntimeError(f"No queries loaded from {DATA_PATH}")
    return queries


def replay(experiment_id: int, count: int, delay_seconds: float = 0.05):
    queries = load_queries()
    client = httpx.Client(timeout=30.0)

    successes = 0
    failures = 0

    for i in range(count):
        session_id = f"replay_{uuid.uuid4().hex[:12]}"
        query = queries[i % len(queries)]

        try:
            assign_resp = client.post(
                f"{BASE_URL}/experiments/assign",
                json={
                    "experiment_id": experiment_id,
                    "session_id": session_id,
                    "input_query": query,
                },
            )
            assign_resp.raise_for_status()
            assignment_id = assign_resp.json()["assignment_id"]

            complete_resp = client.post(
                f"{BASE_URL}/experiments/complete",
                json={"assignment_id": assignment_id},
            )
            complete_resp.raise_for_status()

            successes += 1
            if (i + 1) % 25 == 0:
                print(f"[{i+1}/{count}] completed. Last variant: "
                      f"{complete_resp.json().get('rule_based_success')}")

        except httpx.HTTPStatusError as e:
            failures += 1
            print(f"[{i+1}/{count}] FAILED: {e.response.status_code} {e.response.text}")
        except Exception as e:
            failures += 1
            print(f"[{i+1}/{count}] FAILED: {e}")

        time.sleep(delay_seconds)  # be polite to Groq's rate limits

    client.close()
    print(f"\nDone. {successes} succeeded, {failures} failed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--experiment-id", type=int, required=True)
    parser.add_argument("--count", type=int, required=True)
    parser.add_argument("--delay", type=float, default=0.05,
                         help="seconds to sleep between requests, to respect Groq rate limits")
    args = parser.parse_args()

    replay(experiment_id=args.experiment_id, count=args.count, delay_seconds=args.delay)