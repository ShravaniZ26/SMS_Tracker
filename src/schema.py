"""Output schema: the JSON object every parser must return for one SMS.

Every approach (regex, small model, fine-tuned model, API model) is scored
against this one Pydantic model, so "valid output" means the same thing for all.

Design choices worth knowing:
- All 11 keys must be present. A field that is not in the SMS is written as
  null, not left out. This keeps training targets identical in shape, and makes
  a model that silently drops keys count as invalid.
- strict=True turns off Pydantic's type coercion. Without it, "450" (a string)
  would quietly become 450.0 and 1234 (a number) would become "1234", hiding
  exactly the kind of sloppy model output we want to catch.
- Unknown keys are rejected (extra="forbid") for the same reason.
"""

from datetime import date as _date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

TxnType = Literal["debit", "credit"]
Mode = Literal["UPI", "IMPS", "NEFT", "CARD", "ATM", "NETBANKING", "OTHER"]

# Field order matches the architecture doc; handy for CSV columns and metrics.
FIELDS = [
    "is_transaction",
    "type",
    "amount",
    "account_last4",
    "merchant",
    "vpa",
    "mode",
    "date",
    "ref_no",
    "balance",
    "bank",
]


class Transaction(BaseModel):
    """Parsed form of one bank / UPI SMS."""

    model_config = ConfigDict(strict=True, extra="forbid")

    # False for OTP, promo, failed or pending payments.
    is_transaction: bool
    # Refunds and cashback count as "credit".
    type: TxnType | None
    # Rupees as a plain number: no commas, no "Rs." symbol. Must be positive.
    amount: float | None = Field(gt=0)
    # Last 4 digits only; never the full account or card number.
    account_last4: str | None = Field(pattern=r"^\d{4}$")
    # Normalised brand name ("Swiggy"), not the raw VPA.
    merchant: str | None = Field(min_length=1)
    # UPI ID, e.g. "swiggy@icici". Handle part has no dots, unlike an email.
    vpa: str | None = Field(pattern=r"^[A-Za-z0-9._\-]+@[A-Za-z][A-Za-z0-9]*$")
    mode: Mode | None
    # Always YYYY-MM-DD (checked below).
    date: str | None
    # UPI / IMPS / NEFT reference; may contain letters (e.g. NEFT UTRs).
    ref_no: str | None = Field(pattern=r"^[A-Za-z0-9]+$")
    # Available account balance after the transaction (may be negative).
    balance: float | None
    # Short bank or wallet name, e.g. "HDFC", "SBI", "Paytm".
    bank: str | None = Field(min_length=1)

    @field_validator("date")
    @classmethod
    def date_is_iso(cls, value: str | None) -> str | None:
        """Reject anything that is not a real calendar date in YYYY-MM-DD form."""
        if value is None:
            return value
        if len(value) != 10:  # fromisoformat also accepts "20260928"; we don't
            raise ValueError("date must be YYYY-MM-DD")
        _date.fromisoformat(value)  # raises ValueError for e.g. 2026-02-30
        return value

    @model_validator(mode="after")
    def check_transaction_rules(self) -> "Transaction":
        """Cross-field rules that a single field can't check on its own."""
        others = [getattr(self, name) for name in FIELDS if name != "is_transaction"]
        if not self.is_transaction:
            # A non-transaction (OTP, promo, failed payment) carries no fields.
            # One fixed rule makes hand-labelling unambiguous.
            if any(value is not None for value in others):
                raise ValueError("non-transaction SMS must have every other field null")
        elif self.type is None or self.amount is None:
            raise ValueError("a transaction needs at least type and amount")
        return self
