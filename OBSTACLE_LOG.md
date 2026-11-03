# Obstacle Log

> Replace/extend these with the problems YOU actually hit. These are common ones to compare against.

| # | Obstacle | How I solved it |
|---|----------|-----------------|
| 1 | The model sometimes wrapped JSON in ```json fences or added a sentence before it, so `json.loads` failed. | Tightened the system prompt ("ONLY a single JSON object") and added `strip_fences()` that extracts text between the first `{` and last `}`. |
| 2 | Valid JSON but wrong values (e.g. `"urgency": "URGENT"`, or a made-up category). | Added `validate()` that lowercases values and checks them against allowed lists; invalid output triggers one retry. |
| 3 | One failed API call would crash the whole run. | Wrapped each ticket in try/except (`anthropic.APIError` plus a generic fallback) and stored an `error` record so the batch continues. |
| 4 | Worried about leaking the API key to GitHub. | Used `python-dotenv`, added `.env` to `.gitignore`, and committed only `.env.example`. Verified with `git status` before pushing. |
| 5 | Inconsistent labels between runs for the same ticket. | Set `temperature=0` and defined an urgency guide in the prompt. |
| 6 | Edge case: empty subject / vague ticket (T-1008). | Prompt tells the model to ask for more info in `suggested_action` when unclear. |
