# SMS Transaction Parser

Fine-tune a small open model (Qwen 1.5B) with LoRA to turn Indian bank and UPI transaction SMS
into structured JSON, and compare it with regex rules and a large API model on accuracy, speed,
cost and privacy.

**Status:** work in progress (Week 2: collecting real test data).

## Results

Filled in as phases complete. All approaches are scored on the same 200 hand-labelled real SMS.

| Approach | Field acc. | Record acc. | Valid JSON | Latency p50 | Cost / 1k SMS |
|---|---|---|---|---|---|
| Regex rules | – | – | – | – | – |
| Qwen 1.5B few-shot | – | – | – | – | – |
| Qwen 1.5B + LoRA | – | – | – | – | – |
| Large API model few-shot | – | – | – | – | – |

## Output schema

Each SMS becomes one JSON object with **all 11 keys present**. A field that is not in the SMS
is `null`. The schema lives in [src/schema.py](src/schema.py). Any output that fails it counts as
wrong.

| Field | Type | Example | Rule |
|---|---|---|---|
| `is_transaction` | boolean | `true` | `false` for OTP, promo, failed or pending payment |
| `type` | `"debit"` / `"credit"` | `"debit"` | Refunds and cashback count as credit |
| `amount` | number | `450.0` | Rupees, no commas or symbol, > 0 |
| `account_last4` | string | `"1234"` | Exactly 4 digits, never the full number |
| `merchant` | string | `"Swiggy"` | Normalised brand name, not the raw VPA |
| `vpa` | string | `"swiggy@icici"` | UPI ID if present |
| `mode` | enum | `"UPI"` | `UPI`, `IMPS`, `NEFT`, `CARD`, `ATM`, `NETBANKING`, `OTHER` |
| `date` | string | `"2026-09-28"` | Always `YYYY-MM-DD` |
| `ref_no` | string | `"426512345678"` | UPI or transaction reference (letters and digits) |
| `balance` | number | `12340.5` | Available account balance after the transaction |
| `bank` | string | `"HDFC"` | Short bank or wallet name |

Extra labelling rules:

- If `is_transaction` is `false`, every other field is `null`.
- If `is_transaction` is `true`, `type` and `amount` must be set.
- A credit card's "available limit" is not a balance, so `balance` is `null`.
- Wallet payments (e.g. Paytm Wallet) use `mode: "OTHER"`.
- Types are strict: `"450"` is not a number and `1234` is not a string. Unknown keys are rejected.

Example:

```text
Rs.450.00 debited from A/c XX1234 on 28-09-26 to VPA swiggy@icici. UPI Ref 426512345678. Avl Bal Rs.12,340.50 -HDFC Bank
```

```json
{"is_transaction": true, "type": "debit", "amount": 450.0, "account_last4": "1234",
 "merchant": "Swiggy", "vpa": "swiggy@icici", "mode": "UPI", "date": "2026-09-28",
 "ref_no": "426512345678", "balance": 12340.5, "bank": "HDFC"}
```

There are 10 more hand-written (synthetic) examples in
[data/samples/examples.jsonl](data/samples/examples.jsonl).

## Setup

```bash
git clone https://github.com/ShravaniZ26/SMS_Tracker.git
cd SMS_Tracker
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pre-commit install
cp .env.example .env             # then fill in your keys
pytest
```

## Collecting real test data (Week 2)

Real SMS stay in the git-ignored `data/raw/` and `data/real/` folders and are never committed.

```bash
# 1. Put SMS Backup & Restore XML exports in data/raw/, then convert them to JSONL
python -m src.collect.xml_to_jsonl data/raw -o data/raw/all.jsonl
# 2. Keep bank/wallet senders, plus a sample of OTP/promo negatives
python -m src.collect.filter_senders data/raw/all.jsonl -o data/raw/filtered.jsonl
# 3. Replace account numbers, phones, refs and names with fake values
python -m src.collect.mask data/raw/filtered.jsonl -o data/real/masked.jsonl
```

Then hand-label 200 records from `data/real/masked.jsonl` into `data/real/test.jsonl`. Always
read the masked text before using it: masking is rule-based and can miss names.

## Privacy

- `data/raw/`, `data/real/`, `*.xml` and `.env` are git-ignored. A pre-commit hook also blocks
  any file under `data/raw/` or `data/real/`.
- Only masked SMS are ever sent to the API baseline.
- SMS from other people are used only with their consent.
