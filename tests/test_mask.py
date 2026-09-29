"""Tests for src/collect/mask.py.

The most important test is test_no_sensitive_value_survives: every "real"
value planted in the made-up SMS below must be gone after masking, while the
fields we label (amounts, dates, balances, merchants) must be untouched.
"""

import re

import pytest

from src.collect.jsonl_io import read_jsonl
from src.collect.mask import Masker, main

# (sms, sensitive values that must disappear, values that must survive)
CASES = [
    (
        (
            "Rs.450.00 debited from A/c XX1234 on 28-09-26 to VPA swiggy@icici. "
            "UPI Ref 426512345678. Avl Bal Rs.12,340.50 -HDFC Bank"
        ),
        ["1234", "426512345678"],
        ["Rs.450.00", "28-09-26", "swiggy@icici", "Rs.12,340.50", "HDFC Bank"],
    ),
    (
        "Rs 500 sent to MR RAHUL KUMAR on 28-09-26 via VPA 9876543210@ybl. Ref 426511112222",
        ["RAHUL", "KUMAR", "9876543210", "426511112222"],
        ["Rs 500", "28-09-26", "@ybl", "sent to MR "],
    ),
    (
        (
            "Acct 50100123454321 credited with Rs 1,000.00 by Priya Sharma. "
            "UPI Ref No 426533334444. Call +91 9123456780"
        ),
        ["50100123454321", "4321", "Priya", "Sharma", "426533334444", "9123456780"],
        ["Rs 1,000.00", "+91 "],
    ),
    (
        (
            "Info: UPI/P2A/426555556666/SNEHA DESAI/HDFC Bank. A/c XX4321 debited INR 4321.00. "
            "SMS BLOCK 4321 to 5676766"
        ),
        ["426555556666", "SNEHA", "DESAI", "XX4321", "BLOCK 4321"],
        ["INR 4321.00", "HDFC Bank", "5676766"],
    ),
    (
        "Paid Rs 99 to rahul.k@okaxis. Contact support@hdfcbank.com or 18002586161.",
        ["rahul.k"],
        ["Rs 99", "@okaxis", "support@hdfcbank.com", "18002586161"],
    ),
    (
        (
            "Rs 25,000.00 credited to A/c XX7890 via NEFT from ACME TECHNOLOGIES PVT LTD. "
            "UTR KKBKN52026092412345. Txn ID: 30512345678"
        ),
        ["7890", "52026092412345", "30512345678"],
        ["Rs 25,000.00", "ACME TECHNOLOGIES PVT LTD", "UTR KKBKN"],
    ),
    (
        (
            "Dear Customer, Rs.200 credited from Q123456789@ybl to your a/c ending 9999. "
            "Refund of Rs 349.00 from Flipkart"
        ),
        ["9999"],
        ["Dear Customer", "Q123456789@ybl", "Refund of Rs 349.00 from Flipkart"],
    ),
]


@pytest.mark.parametrize("sms, sensitive, kept", CASES)
def test_no_sensitive_value_survives(sms, sensitive, kept):
    masked = Masker().mask_text(sms)
    for value in sensitive:
        assert value not in masked, f"{value!r} leaked in: {masked}"
    for value in kept:
        assert value in masked, f"{value!r} should be kept in: {masked}"


def test_same_real_value_gets_same_fake():
    masker = Masker()
    a = masker.mask_text("Rs 10 debited from A/c XX1234 by RAHUL KUMAR")
    b = masker.mask_text("Card XX1234 used. Paid to RAHUL KUMAR")
    last4 = lambda text: re.search(r"XX(\d{4})", text).group(1)
    assert last4(a) == last4(b)
    assert a.split("by ")[1] in b  # same fake name


def test_full_and_masked_account_share_last4():
    masked = Masker().mask_text("A/c 50100123451234 debited. Info for A/c XX1234")
    full, short = re.findall(r"\d{4,}", masked)[:2]
    assert full[-4:] == short and len(full) == 14


def test_masking_keeps_shape():
    masked = Masker().mask_text("A/c XX1234 UPI Ref 426512345678")
    assert re.fullmatch(r"A/c XX\d{4} UPI Ref \d{12}", masked)


def test_is_repeatable_with_seed():
    sms = CASES[1][0]
    assert Masker(seed=3).mask_text(sms) == Masker(seed=3).mask_text(sms)


def test_text_without_personal_data_is_unchanged():
    promo = "Get a pre-approved Personal Loan up to Rs 5,00,000 at 10.5% p.a. -Axis Bank"
    assert Masker().mask_text(promo) == promo


def test_main_writes_safe_records(tmp_path):
    src = tmp_path / "filtered.jsonl"
    src.write_text(
        '{"sender": "VM-HDFCBK", "sender_id": "HDFCBK", "bank": "HDFC", '
        '"category": "candidate_txn", "date": "2026-09-28T10:00:00+05:30", '
        '"body": "Rs.5 debited from A/c XX1234", "source_file": "rahul_phone.xml"}\n',
        encoding="utf-8",
    )
    out = tmp_path / "real" / "masked.jsonl"
    main([str(src), "-o", str(out)])
    (record,) = read_jsonl(out)
    assert record["id"] == "real_0001"
    assert record["source"] == "source_01"  # file name (maybe a person's name) removed
    assert "1234" not in record["sms"]
    assert "body" not in record and "sender" not in record
