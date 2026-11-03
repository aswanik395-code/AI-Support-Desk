# AI Support Desk

Classifies support tickets with an LLM (Groq SDK) into structured JSON:
`category`, `urgency`, `suggested_action`, then prints a summary.

## Setup
```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # then put your real key in .env
python support_desk.py
```

## Files
- `support_desk.py`: main script
- `sample_tickets.json`: 8 sample tickets
- `results.json`, `summary.txt`: generated output
- `OBSTACLE_LOG.md`: problems and fixes

The API key lives in `.env` (git-ignored). Never commit it.
