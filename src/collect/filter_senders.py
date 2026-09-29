"""Keep SMS from bank / wallet senders, plus a small sample of negatives.

Indian commercial SMS come from DLT "headers" like VM-HDFCBK or AD-SBIINB-S:
  - 2-letter prefix: operator + circle (varies, so we ignore it)
  - 6-character sender ID: identifies the company (HDFCBK = HDFC Bank)
  - optional suffix: -S service, -T transactional, -P promotional, -G government
We strip the prefix/suffix and look the 6-character ID up in SENDER_BANKS.

Each kept message is tagged with a category:
  - candidate_txn: looks like a debit/credit (to be hand-labelled)
  - otp:           one-time passwords, even when they mention an amount
  - other:         promos, alerts, reminders, ...
All candidate_txn are kept. OTP/other are *negatives*: the model must learn to
say is_transaction=false for them, so we keep a random sample (by default
about 15% as many as the transactions).

Usage:
    python -m src.collect.filter_senders data/raw/all.jsonl -o data/raw/filtered.jsonl
"""

import argparse
import math
import random
import re
from collections import Counter

from src.collect.jsonl_io import read_jsonl, write_jsonl

# 6-character sender ID -> short bank/wallet name used in the schema's `bank` field.
# Not exhaustive: banks use several IDs. When the script reports "unmatched
# senders that look like transactions", add them here.
SENDER_BANKS = {
    "HDFCBK": "HDFC", "HDFCBN": "HDFC",
    "SBIINB": "SBI", "SBIUPI": "SBI", "SBICRD": "SBI", "ATMSBI": "SBI", "CBSSBI": "SBI",
    "SBMSMS": "SBI", "SBYONO": "SBI",
    "ICICIB": "ICICI", "ICICIT": "ICICI",
    "AXISBK": "Axis", "AXISMR": "Axis",
    "KOTAKB": "Kotak", "KOTAKM": "Kotak",
    "PAYTMB": "Paytm", "IPAYTM": "Paytm",
    "PNBSMS": "PNB",
    "BOBTXN": "BOB", "BOBSMS": "BOB",
    "CANBNK": "Canara",
    "UNIONB": "Union",
    "IDFCFB": "IDFC",
    "YESBNK": "Yes",
    "INDUSB": "IndusInd",
    "FEDBNK": "Federal",
    "IOBCHN": "IOB",
    "CENTBK": "Central",
    "AUBANK": "AU",
    "PHONPE": "PhonePe",
    "AMZNPY": "Amazon Pay",
}  # fmt: skip

# Optional 2-letter prefix, 6-char ID, optional 1-letter suffix.
HEADER_RE = re.compile(r"^(?:[A-Z]{2}-)?([A-Z0-9]{6})(?:-[A-Z])?$")

OTP_RE = re.compile(r"\b(otp|one[- ]time password|verification code)\b", re.IGNORECASE)
TXN_WORD_RE = re.compile(
    r"\b(debited|credited|debit|credit|spent|withdrawn|paid|received|sent|transferred|refund)",
    re.IGNORECASE,
)
# "Rs.450", "Rs 1,299", "INR 5000", "₹120"
AMOUNT_RE = re.compile(r"(\brs\.?|\binr|₹)\s*[\d,]*\d", re.IGNORECASE)


def normalise_sender(address: str) -> str:
    """'VM-HDFCBK-S' -> 'HDFCBK'. Anything else (e.g. a phone number) is returned upper-cased."""
    address = address.strip().upper()
    match = HEADER_RE.match(address)
    return match.group(1) if match else address


def categorise(body: str) -> str:
    """Rough rule-based category. It only decides what to keep; labels come later by hand."""
    # OTP first: "OTP for txn of Rs 2,499 at Myntra" is not a transaction.
    if OTP_RE.search(body):
        return "otp"
    if TXN_WORD_RE.search(body) and AMOUNT_RE.search(body):
        return "candidate_txn"
    return "other"


def filter_records(
    records: list[dict], negative_ratio: float = 0.15, seed: int = 0
) -> tuple[list[dict], Counter]:
    """Return (kept records, count of unmatched senders whose text looks like a transaction)."""
    candidates, negatives = [], []
    unmatched: Counter = Counter()

    for index, record in enumerate(records):
        sender_id = normalise_sender(record.get("sender", ""))
        bank = SENDER_BANKS.get(sender_id)
        category = categorise(record["body"])
        if bank is None:
            # Count likely-missed bank IDs. Only the ID is reported, never the text.
            if category == "candidate_txn" and HEADER_RE.match(sender_id):
                unmatched[sender_id] += 1
            continue
        kept = {**record, "sender_id": sender_id, "bank": bank, "category": category}
        (candidates if category == "candidate_txn" else negatives).append((index, kept))

    # Seeded RNG, so the same input always gives the same sample.
    n_negatives = min(len(negatives), math.ceil(negative_ratio * len(candidates)))
    sampled = random.Random(seed).sample(negatives, n_negatives)

    # Put everything back in the original (time) order.
    kept = [record for _, record in sorted(candidates + sampled, key=lambda pair: pair[0])]
    return kept, unmatched


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("input", help="JSONL from xml_to_jsonl.py")
    parser.add_argument("-o", "--output", required=True, help="output JSONL path")
    parser.add_argument(
        "--negative-ratio", type=float, default=0.15,
        help="negatives to keep, as a fraction of candidate transactions (default 0.15)",
    )  # fmt: skip
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args(argv)

    kept, unmatched = filter_records(read_jsonl(args.input), args.negative_ratio, args.seed)
    write_jsonl(kept, args.output)

    print(f"Wrote {len(kept)} records to {args.output}")
    print("By category:", dict(Counter(r["category"] for r in kept)))
    print("By bank:    ", dict(Counter(r["bank"] for r in kept)))
    if unmatched:
        print("Unmatched senders that look like transactions (add to SENDER_BANKS?):")
        for sender_id, n in unmatched.most_common():
            print(f"  {sender_id}: {n}")


if __name__ == "__main__":
    main()
