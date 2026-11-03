"""AI Support Desk: classify support tickets with an LLM into structured JSON."""

import json
import os
import sys
from collections import Counter
from pathlib import Path

import groq
from dotenv import load_dotenv
from groq import Groq

load_dotenv()  # reads GROQ_API_KEY from .env (which is git-ignored)

MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
BASE_DIR = Path(__file__).parent
TICKETS_FILE = BASE_DIR / "sample_tickets.json"
RESULTS_FILE = BASE_DIR / "results.json"
SUMMARY_FILE = BASE_DIR / "summary.txt"

CATEGORIES = ["billing", "technical", "account", "general", "feature_request"]
URGENCIES = ["low", "medium", "high", "critical"]
MAX_ATTEMPTS = 2  # one retry if the model returns malformed JSON

SYSTEM_PROMPT = f"""You are a support-ticket triage assistant.
Read the customer ticket and respond with ONLY a single JSON object. No prose,
no explanation, no markdown code fences.

The JSON object must have exactly these keys:
{{
  "category": one of {CATEGORIES},
  "urgency": one of {URGENCIES},
  "suggested_action": a single concise sentence (max 25 words) telling the support agent what to do next
}}

Urgency guide:
- critical: outage or data/security issue affecting many users or heavy financial loss
- high: a customer is blocked, or money/billing is wrong and the customer is upset
- medium: a problem exists but there is a workaround or a deadline is not imminent
- low: general questions, feedback, feature ideas

If the ticket is vague, pick the best-fit category and make the suggested action
a request for more information."""


def load_tickets(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def strip_fences(text: str) -> str:
    """Remove ```json fences or extra text around the JSON object, if present."""
    text = text.strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("No JSON object found in response")
    return text[start : end + 1]


def validate(data: dict) -> dict:
    """Check required keys and allowed values; normalise casing."""
    missing = {"category", "urgency", "suggested_action"} - data.keys()
    if missing:
        raise ValueError(f"Missing keys: {sorted(missing)}")

    category = str(data["category"]).strip().lower()
    urgency = str(data["urgency"]).strip().lower()
    action = str(data["suggested_action"]).strip()

    if category not in CATEGORIES:
        raise ValueError(f"Invalid category: {category!r}")
    if urgency not in URGENCIES:
        raise ValueError(f"Invalid urgency: {urgency!r}")
    if not action:
        raise ValueError("Empty suggested_action")

    return {"category": category, "urgency": urgency, "suggested_action": action}


def classify_ticket(client: Groq, ticket: dict) -> dict:
    """Send one ticket to the LLM and return a validated classification."""
    user_message = (
        f"Subject: {ticket.get('subject') or '(no subject)'}\n"
        f"Body: {ticket.get('body', '')}"
    )

    last_error = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        response = client.chat.completions.create(
            model=MODEL,
            max_tokens=300,
            temperature=0,
            response_format={"type": "json_object"},  # forces valid JSON
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
        )
        raw = response.choices[0].message.content or ""
        try:
            return validate(json.loads(strip_fences(raw)))
        except (ValueError, json.JSONDecodeError) as exc:
            last_error = f"Malformed response (attempt {attempt}): {exc} | raw={raw[:200]!r}"
    raise ValueError(last_error)


def process_tickets(client: Groq, tickets: list[dict]) -> list[dict]:
    results = []
    for ticket in tickets:
        record = {"id": ticket["id"], "subject": ticket.get("subject", "")}
        try:
            record.update(classify_ticket(client, ticket))
            record["status"] = "ok"
        except groq.APIError as exc:  # network, auth, rate limit, server errors
            record.update(status="error", error=f"API error: {exc}")
        except Exception as exc:  # parsing/validation or anything unexpected
            record.update(status="error", error=str(exc))
        results.append(record)
        print(f"[{record['status'].upper():5}] {record['id']}: "
              f"{record.get('category', '-')} / {record.get('urgency', '-')}")
    return results


def build_summary(results: list[dict]) -> str:
    ok = [r for r in results if r["status"] == "ok"]
    failed = len(results) - len(ok)
    by_category = Counter(r["category"] for r in ok)
    by_urgency = Counter(r["urgency"] for r in ok)

    lines = [
        "=" * 40,
        "SUPPORT DESK SUMMARY",
        "=" * 40,
        f"Total tickets: {len(results)}   Processed: {len(ok)}   Failed: {failed}",
        "",
        "By category:",
    ]
    lines += [f"  {c:<16} {by_category.get(c, 0)}" for c in CATEGORIES]
    lines += ["", "By urgency:"]
    lines += [f"  {u:<16} {by_urgency.get(u, 0)}" for u in URGENCIES]

    critical = [r for r in ok if r["urgency"] == "critical"]
    if critical:
        lines += ["", "Needs immediate attention:"]
        lines += [f"  {r['id']}: {r['suggested_action']}" for r in critical]
    return "\n".join(lines)


def main() -> None:
    if not os.getenv("GROQ_API_KEY"):
        sys.exit("GROQ_API_KEY not set. Copy .env.example to .env and add your key.")

    client = Groq()  # picks up the key from the environment

    try:
        tickets = load_tickets(TICKETS_FILE)
    except (OSError, json.JSONDecodeError) as exc:
        sys.exit(f"Could not load tickets: {exc}")

    results = process_tickets(client, tickets)

    RESULTS_FILE.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    summary = build_summary(results)
    SUMMARY_FILE.write_text(summary, encoding="utf-8")
    print("\n" + summary)


if __name__ == "__main__":
    main()
