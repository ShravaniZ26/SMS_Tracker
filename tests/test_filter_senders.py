"""Tests for src/collect/filter_senders.py, using made-up SMS."""

import pytest

from src.collect.filter_senders import categorise, filter_records, normalise_sender


@pytest.mark.parametrize(
    "address, expected",
    [
        ("VM-HDFCBK", "HDFCBK"),
        ("AD-SBIINB-S", "SBIINB"),
        ("jd-icicib-t", "ICICIB"),
        ("AXISBK", "AXISBK"),
        ("+919999999999", "+919999999999"),  # a person: returned unchanged
    ],
)
def test_normalise_sender(address, expected):
    assert normalise_sender(address) == expected


@pytest.mark.parametrize(
    "body, expected",
    [
        ("Rs.450.00 debited from A/c XX1234", "candidate_txn"),
        ("INR 5,000 credited to your account", "candidate_txn"),
        ("₹120 paid to Uber", "candidate_txn"),
        ("123456 is your OTP for txn of INR 2,499.00 at MYNTRA", "otp"),  # OTP wins
        ("Get a Personal Loan up to Rs 5,00,000!", "other"),  # amount, no txn word
        ("Your card has been credited with reward points", "other"),  # txn word, no amount
    ],
)
def test_categorise(body, expected):
    assert categorise(body) == expected


def rec(sender, body):
    return {"sender": sender, "date": None, "body": body, "source_file": "x.xml"}


def make_records():
    txns = [rec("VM-HDFCBK", f"Rs.{i}.00 debited from A/c XX1234") for i in range(1, 21)]
    otps = [rec("AD-SBIINB", f"{i:06d} is your OTP") for i in range(10)]
    promos = [rec("VM-AXISBK", "Apply for a loan today") for _ in range(10)]
    people = [rec("+919999999999", "Rs 500 sent, check it")]
    unknown = [rec("VM-NEWBNK", "Rs.10 debited from your account")]
    return txns + otps + promos + people + unknown


def test_keeps_all_transactions_and_sampled_negatives():
    kept, _ = filter_records(make_records(), negative_ratio=0.15)
    categories = [r["category"] for r in kept]
    assert categories.count("candidate_txn") == 20
    assert len(kept) - 20 == 3  # ceil(0.15 * 20)


def test_drops_people_and_unknown_senders_and_reports_unknown_banks():
    kept, unmatched = filter_records(make_records())
    assert {r["sender_id"] for r in kept} <= {"HDFCBK", "SBIINB", "AXISBK"}
    assert unmatched == {"NEWBNK": 1}  # likely bank not yet in SENDER_BANKS


def test_adds_bank_and_keeps_original_order():
    kept, _ = filter_records(make_records(), negative_ratio=1.0)
    assert kept[0]["bank"] == "HDFC"
    bodies = [r["body"] for r in make_records()]
    positions = [bodies.index(r["body"]) for r in kept]
    assert positions == sorted(positions)


def test_sampling_is_repeatable():
    first, _ = filter_records(make_records(), seed=7)
    second, _ = filter_records(make_records(), seed=7)
    assert first == second


def test_zero_ratio_keeps_no_negatives():
    kept, _ = filter_records(make_records(), negative_ratio=0)
    assert all(r["category"] == "candidate_txn" for r in kept)
