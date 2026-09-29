# Project: SMS Transaction Parser

Fine-tune a small open model with LoRA to parse Indian bank/UPI SMS into JSON,
and compare it with regex and a large API model.

## Read first
- docs/architecture.md: system design, schema, repo structure
- docs/plan.md: phases and done-criteria

## Decisions already made (do not change without asking)
- Primary model: [Qwen 1.5B Instruct]; comparison model: [Qwen 0.5B]
- Training: QLoRA with Unsloth, run in Google Colab (not locally)
- Python 3.11, Pydantic for the schema, pytest for tests
- Large-model baseline: [Anthropic API], key read from .env

## Rules
- Never read, create, or modify files in data/raw/ or data/real/
- Never hardcode API keys; use python-dotenv
- Work on one phase at a time; don't build ahead
- Before writing code, show me a short plan and wait for approval
- Every new module gets unit tests in tests/
- Keep code simple and commented: I am learning ML, so explain non-obvious parts
- Don't install new packages without asking; add approved ones to requirements.txt

## Current phase
[Week 1 — P1 Schema]