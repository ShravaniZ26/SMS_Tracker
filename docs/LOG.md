# Weekly log

A few lines per week: what I tried, what broke, what I learned.

## Week 1 — Setup + P1 Schema

- Repo skeleton, `.gitignore`, pre-commit hook blocking `data/raw/` and `data/real/`.
- `src/schema.py`: Pydantic model with all 11 fields. Chose strict mode (no type coercion),
  all keys required (nulls explicit), and "non-transaction ⇒ all other fields null".
- 10 hand-written synthetic examples in `data/samples/examples.jsonl`; tests pass.

## Week 2 — P2 Real data

- Collection pipeline: `xml_to_jsonl.py` → `filter_senders.py` → `mask.py`.
- TODO: export SMS, collect from 3–5 people with consent, label 200, fill `docs/bank_formats.md`.
