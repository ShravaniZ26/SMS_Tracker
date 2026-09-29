"""Tests for src/schema.py: the hand-written examples pass, bad outputs fail."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.schema import FIELDS, Transaction

SAMPLES = Path(__file__).resolve().parents[1] / "data" / "samples" / "examples.jsonl"


def load_samples() -> list[dict]:
    with SAMPLES.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def good_label() -> dict:
    """A valid label to mutate in the negative tests below."""
    return dict(load_samples()[0]["label"])


def test_there_are_ten_examples():
    assert len(load_samples()) == 10


@pytest.mark.parametrize("record", load_samples(), ids=lambda r: r["template_id"])
def test_every_example_validates(record):
    Transaction.model_validate(record["label"])


def test_examples_also_validate_from_raw_json():
    # Model output arrives as a JSON string, so check that path too.
    for record in load_samples():
        Transaction.model_validate_json(json.dumps(record["label"]))


def test_examples_have_all_keys_in_order():
    for record in load_samples():
        assert list(record["label"]) == FIELDS


def test_examples_include_negatives():
    flags = [r["label"]["is_transaction"] for r in load_samples()]
    assert True in flags and False in flags


@pytest.mark.parametrize(
    "field, bad_value",
    [
        ("amount", "450.00"),  # string, not number (strict mode)
        ("amount", 0),  # must be positive
        ("account_last4", "XX1234"),  # digits only
        ("account_last4", "501001234"),  # never the full number
        ("account_last4", 1234),  # number loses leading zeros; must be a string
        ("type", "refund"),  # refunds are "credit"
        ("mode", "upi"),  # enum values are upper-case
        ("date", "28-09-26"),  # must be YYYY-MM-DD
        ("date", "2026-02-30"),  # not a real date
        ("date", "20260928"),  # compact ISO form is not allowed
        ("vpa", "support@hdfcbank.com"),  # an email, not a UPI ID
        ("is_transaction", "true"),  # string, not boolean
    ],
)
def test_bad_field_values_are_rejected(field, bad_value):
    label = good_label()
    label[field] = bad_value
    with pytest.raises(ValidationError):
        Transaction.model_validate(label)


def test_missing_key_is_rejected():
    label = good_label()
    del label["balance"]  # must be written as null, not dropped
    with pytest.raises(ValidationError):
        Transaction.model_validate(label)


def test_extra_key_is_rejected():
    label = good_label()
    label["currency"] = "INR"
    with pytest.raises(ValidationError):
        Transaction.model_validate(label)


def test_non_transaction_must_have_null_fields():
    label = {name: None for name in FIELDS}
    label["is_transaction"] = False
    Transaction.model_validate(label)  # all null: fine

    label["amount"] = 2499.0  # e.g. the amount inside an OTP message
    with pytest.raises(ValidationError):
        Transaction.model_validate(label)


def test_transaction_needs_type_and_amount():
    label = good_label()
    label["amount"] = None
    with pytest.raises(ValidationError):
        Transaction.model_validate(label)


def test_integer_amount_is_accepted():
    # JSON has one number type; 450 and 450.0 mean the same amount.
    label = good_label()
    label["amount"] = 450
    assert Transaction.model_validate(label).amount == 450.0
