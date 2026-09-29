"""Replace personal details in bank SMS with consistent fake values.

What gets masked (see the rules in Masker.mask_text):
  - account / card numbers:  XX1234, A/c no. 50100123451234, card ending 1234
  - phone numbers:           9876543210, +91 98765 43210-style (10 digits after +91)
  - reference numbers:       UPI Ref 426512345678, UTR KKBKN52026..., Txn ID ...
  - any other 9-18 digit run (catch-all; toll-free 1800/1860 numbers excepted)
  - personal UPI IDs:        9876543210@ybl, rahul.k@okaxis (merchant VPAs are kept)
  - person names:            after Mr/Ms/Dear/to/from/by, and in UPI/P2A/.../NAME/ strings

What is deliberately NOT masked, because it is what we label:
  amounts, balances, dates, merchant names and VPAs, bank names.

Consistency: the same real value always gets the same fake within one run, so
"XX1234" in two messages stays one account. Account numbers are faked by their
last 4 digits, so a full number and its XX-masked form share the same fake last4.

Limitation: names are found by rules, so unusual formats slip through.
ALWAYS read the masked output before labelling or sharing it.

Usage:
    python -m src.collect.mask data/raw/filtered.jsonl -o data/real/masked.jsonl
"""

import argparse
import random
import re
from collections import Counter

from src.collect.filter_senders import SENDER_BANKS
from src.collect.jsonl_io import read_jsonl, write_jsonl

DIGITS = "0123456789"

FAKE_FIRST = [
    "Aarav", "Vivaan", "Aditya", "Arjun", "Rohan", "Karan", "Ishaan", "Kabir", "Nikhil", "Siddharth",
    "Ananya", "Diya", "Kavya", "Meera", "Priya", "Riya", "Sneha", "Tanvi", "Pooja", "Neha",
]  # fmt: skip
FAKE_LAST = [
    "Sharma", "Verma", "Iyer", "Nair", "Reddy", "Patel", "Mehta", "Gupta", "Joshi", "Rao",
    "Kulkarni", "Desai", "Menon", "Bose", "Das", "Singh", "Kapoor", "Pillai", "Chopra", "Shah",
]  # fmt: skip

# A UPI ID whose local part contains one of these is treated as a merchant and kept.
MERCHANT_KEYWORDS = [
    "swiggy", "zomato", "amazon", "amzn", "flipkart", "myntra", "paytmqr", "bharatpe", "razorpay",
    "payu", "cashfree", "billdesk", "irctc", "uber", "ola", "rapido", "zepto", "blinkit",
    "bigbasket", "jio", "airtel", "bsnl", "netflix", "spotify", "google", "phonepe", "merchant",
    "store", "shop", "mart", "recharge", "billpay", "bank", "insurance", "electricity",
]  # fmt: skip
MERCHANT_VPA_CODE_RE = re.compile(r"^q\d{6,}$", re.IGNORECASE)  # PhonePe merchant QR codes

# Capitalised words after "to"/"from" that are not person names.
NOT_NAME_WORDS = {w.upper() for w in SENDER_BANKS.values()} | {
    "VPA", "A", "AC", "ACCT", "ACCOUNT", "YOUR", "YOU", "RS", "INR", "UPI", "NEFT", "IMPS", "RTGS",
    "ATM", "POS", "CARD", "BANK", "WALLET", "BENEFICIARY", "MOBILE", "LINKED", "SAVINGS", "SB",
    "CUSTOMER", "USER", "SIR", "MADAM", "CARDHOLDER", "MEMBER", "VALUED", "CLIENT", "SBI", "NA",
    "CASH", "SELF", "MERCHANT", "INFO", "AMAZON", "PAY", "GOOGLE", "PAYTM", "PHONEPE",
    # Titles: "to MR RAHUL" is handled by the title rule, so "MR" itself is no name.
    "MR", "MRS", "MS", "MISS", "DEAR", "SHRI", "SMT", "SRI",
}  # fmt: skip
# Words that mark a company, not a person ("ACME TECHNOLOGIES PVT LTD").
COMPANY_WORDS = {
    "PVT", "LTD", "LIMITED", "PRIVATE", "LLP", "INC", "CORP", "TECHNOLOGIES", "SERVICES",
    "SOLUTIONS", "ENTERPRISES", "INDIA", "STORE", "STORES", "MART", "TRADERS", "HOSPITAL",
}  # fmt: skip
# A name stops at these words ("RAHUL KUMAR ON 28-09" -> name is "RAHUL KUMAR").
NAME_STOP_WORDS = {
    "ON", "VIA", "FOR", "AT", "REF", "UPI", "AVL", "BAL", "IF", "NOT", "THE", "AND", "IS", "HAS",
    "WAS", "WITH", "IN", "OF", "FROM", "TO", "BY", "DATED", "DT", "INFO", "NEFT", "IMPS",
    "REFNO", "UTR", "TXN", "RRN", "TRANSACTION", "IST", "CR", "DR", "A/C", "AC", "ACCT",
}  # fmt: skip

# Each fake value is first swapped for one "placeholder" character from Unicode's
# private-use area, and all placeholders are expanded at the very end. This stops
# a later rule from re-masking an earlier fake (e.g. the catch-all digit rule
# eating a fake account number). No regex below matches these characters.
PLACEHOLDER_BASE = 0xF0000
PLACEHOLDER_RE = re.compile("[\U000f0000-\U000ffffd]")

# --- Patterns, applied in this order ---------------------------------------
# UPI ID: local@handle. The lookahead rejects emails like support@hdfcbank.com.
VPA_RE = re.compile(
    r"(?<![\w.\-])([A-Za-z0-9._\-]+)@([A-Za-z][A-Za-z0-9]*)(?![A-Za-z0-9]|\.[A-Za-z])"
)
PHONE_LOCAL_RE = re.compile(r"^(91)?([6-9]\d{9})$")
# Already-masked account/card: XX1234, X5678, **9012, ..4321
MASKED_ACCOUNT_RE = re.compile(r"(?<![A-Za-z0-9])([Xx*]+|\.{2,})(\d{3,6})(?!\d)")
ENDING_RE = re.compile(r"\b(ending(?:\s+(?:with|in))?\s*[:\-]?\s*)(\d{4})(?!\d)", re.IGNORECASE)
FULL_ACCOUNT_RE = re.compile(
    r"\b(a/c|acct|account|ac)(\.?\s*(?:no\.?|number)?\s*[:.\-]?\s*)(\d{4,18})(?!\d)", re.IGNORECASE
)
# Reference after a cue word. The value must contain a digit, so words like
# "Refund" or "transactional" never match.
REF_RE = re.compile(
    r"\b((?:ref(?:erence)?|rrn|utr|txn|transaction)(?:\s*(?:no|number|id|#))?\.?\s*[:#.\-/]?\s*)"
    r"([A-Za-z0-9]*\d[A-Za-z0-9]*)",
    re.IGNORECASE,
)
# 10-digit Indian mobile, optionally with +91 / 91- / 0 in front.
PHONE_RE = re.compile(r"(?<![\dA-Za-z])(\+91[\s-]?|91[\s-]|0)?([6-9]\d{9})(?!\d)")
# Catch-all for long digit runs, except toll-free numbers (1800..., 1860...).
LONG_NUMBER_RE = re.compile(r"(?<!\d)(?!18[06]0)\d{9,18}(?!\d)")
TITLE_NAME_RE = re.compile(
    r"\b((?i:mr|mrs|ms|miss|dear|shri|smt|sri)\.?\s+)([A-Z][A-Za-z]*(?:\s+[A-Z][A-Za-z]*){0,3})"
)
CUE_NAME_RE = re.compile(r"\b((?i:to|from|by|frm)\s+)([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]*){0,3})")
# "UPI/P2A/<ref>/RAHUL KUMA/..." as seen in Axis/ICICI "Info:" lines.
UPI_INFO_NAME_RE = re.compile(
    r"(?i)(\bupi/(?:p2a|p2m|dr|cr)/[^/\s]+/)([A-Za-z][A-Za-z .]*[A-Za-z])(?=/)"
)


class Masker:
    """Holds the real->fake mapping so fakes stay consistent across a whole run."""

    def __init__(self, seed: int = 0):
        self._rng = random.Random(seed)  # seeded: same input -> same output
        self._fakes: dict[tuple[str, str], str] = {}
        self._sources: dict[str, str] = {}
        self.counts: Counter = Counter()  # how many values of each kind were masked

    # --- fake value makers ---------------------------------------------------
    def _fake(self, kind: str, original: str, make, count: bool = True) -> str:
        """Return the fake for (kind, original), creating one the first time."""
        key = (kind, original.upper())
        if key not in self._fakes:
            fake = make()
            while fake.upper() == original.upper():  # never "mask" to the same value
                fake = make()
            self._fakes[key] = fake
        if count:
            self.counts[kind] += 1
        return self._fakes[key]

    def _digits(self, n: int, first: str = DIGITS) -> str:
        return self._rng.choice(first) + "".join(self._rng.choice(DIGITS) for _ in range(n - 1))

    def fake_digits(self, kind: str, value: str) -> str:
        """Replace each digit with a random one; letters and length stay the same."""

        def make():
            return "".join(self._rng.choice(DIGITS) if c.isdigit() else c for c in value)

        return self._fake(kind, value, make)

    def fake_phone(self, digits: str) -> str:
        return self._fake("phone", digits, lambda: self._digits(10, first="6789"))

    def fake_account(self, digits: str) -> str:
        """Fake by last 4 digits so XX1234 and 5010...1234 both become ...<same 4>."""
        if len(digits) <= 4:
            return self._fake("account", digits, lambda: self._digits(len(digits)))
        prefix, last4 = digits[:-4], digits[-4:]
        # count=False: one account number should be counted once, not twice.
        fake_prefix = self._fake(
            "account_prefix", prefix, lambda: self._digits(len(prefix)), count=False
        )
        return fake_prefix + self._fake("account", last4, lambda: self._digits(4))

    def fake_name(self, name: str) -> str:
        real_words = {w.upper() for w in name.split()}
        # Only draw from fake names that share no word with the real one, so
        # "Priya Sharma" can never become "Priya Kapoor".
        firsts = [f for f in FAKE_FIRST if f.upper() not in real_words]
        lasts = [s for s in FAKE_LAST if s.upper() not in real_words]

        def make():
            parts = [self._rng.choice(firsts)]
            if len(real_words) > 1:
                parts.append(self._rng.choice(lasts))
            return " ".join(parts)

        fake = self._fake("name", " ".join(name.split()), make)
        return fake.upper() if name.isupper() else fake

    def fake_vpa_user(self, local: str) -> str:
        def make():
            first, last = self._rng.choice(FAKE_FIRST), self._rng.choice(FAKE_LAST)
            return f"{first}.{last}{self._rng.randint(10, 99)}".lower()

        return self._fake("vpa", local, make)

    def source_id(self, source_file: str) -> str:
        """File names may contain a friend's name, so replace them with source_01, ..."""
        if source_file not in self._sources:
            self._sources[source_file] = f"source_{len(self._sources) + 1:02d}"
        return self._sources[source_file]

    # --- masking -------------------------------------------------------------
    def mask_text(self, text: str) -> str:
        held: list[str] = []

        def hold(value: str) -> str:
            held.append(value)
            return chr(PLACEHOLDER_BASE + len(held) - 1)

        real_last4: dict[str, str] = {}  # real last4 -> fake, seen in this message

        def on_vpa(m: re.Match) -> str:
            local, handle = m.group(1), m.group(2)
            phone = PHONE_LOCAL_RE.match(local)
            if phone:
                return hold((phone.group(1) or "") + self.fake_phone(phone.group(2)) + "@" + handle)
            lower = local.lower()
            if any(k in lower for k in MERCHANT_KEYWORDS) or MERCHANT_VPA_CODE_RE.match(local):
                return hold(m.group(0))  # merchant: keep, but protect from later rules
            return hold(self.fake_vpa_user(local) + "@" + handle)

        def on_account(prefix: str, digits: str) -> str:
            fake = self.fake_account(digits)
            real_last4[digits[-4:]] = fake[-4:]
            return prefix + hold(fake)

        def on_name(m: re.Match) -> str:
            cue, name = m.group(1), m.group(2)
            tokens = list(re.finditer(r"\S+", name))
            # Cut the name at the first stop word and leave the rest untouched.
            for i, token in enumerate(tokens):
                if token.group().upper() in NAME_STOP_WORDS:
                    tokens = tokens[:i]
                    break
            words = [t.group() for t in tokens]
            upper = [w.upper() for w in words]
            if not words or upper[0] in NOT_NAME_WORDS or COMPANY_WORDS & set(upper):
                return m.group(0)
            if any(k in upper[0].lower() for k in MERCHANT_KEYWORDS):
                return m.group(0)
            end = tokens[-1].end()  # replace only the name; keep what follows as-is
            return cue + hold(self.fake_name(name[:end])) + name[end:]

        def on_upi_info_name(m: re.Match) -> str:
            name = m.group(2)
            if COMPANY_WORDS & set(name.upper().split()) or name.upper() in NOT_NAME_WORDS:
                return m.group(0)
            return m.group(1) + hold(self.fake_name(name))

        text = VPA_RE.sub(on_vpa, text)
        text = MASKED_ACCOUNT_RE.sub(lambda m: on_account(m.group(1), m.group(2)), text)
        text = ENDING_RE.sub(lambda m: on_account(m.group(1), m.group(2)), text)
        text = FULL_ACCOUNT_RE.sub(lambda m: on_account(m.group(1) + m.group(2), m.group(3)), text)
        # A last4 can reappear on its own, e.g. "SMS BLOCK 1234 to ...". The
        # lookarounds skip amounts such as "1,234.00" or "1234.50".
        for real, fake in real_last4.items():
            pattern = rf"(?<![\d.,]){real}(?!\d|[.,]\d)"
            text = re.sub(pattern, lambda m, f=fake: hold(f), text)

        def on_ref(m: re.Match) -> str:
            if len(m.group(2)) < 6:  # too short to be a reference; leave it
                return m.group(0)
            return m.group(1) + hold(self.fake_digits("ref", m.group(2)))

        text = REF_RE.sub(on_ref, text)
        text = PHONE_RE.sub(lambda m: (m.group(1) or "") + hold(self.fake_phone(m.group(2))), text)
        text = LONG_NUMBER_RE.sub(lambda m: hold(self.fake_digits("number", m.group(0))), text)
        text = UPI_INFO_NAME_RE.sub(on_upi_info_name, text)
        text = TITLE_NAME_RE.sub(on_name, text)
        text = CUE_NAME_RE.sub(on_name, text)

        # Expand placeholders into their fake values.
        return PLACEHOLDER_RE.sub(lambda m: held[ord(m.group(0)) - PLACEHOLDER_BASE], text)

    def mask_record(self, record: dict, index: int) -> dict:
        """Build the record that goes to data/real/: masked text plus safe metadata only."""
        return {
            "id": f"real_{index:04d}",
            "sms": self.mask_text(record["body"]),
            "bank": record.get("bank"),
            "sender_id": record.get("sender_id"),
            "category": record.get("category"),
            "date": record.get("date"),
            "source": self.source_id(record.get("source_file", "")),
        }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("input", help="JSONL from filter_senders.py")
    parser.add_argument("-o", "--output", required=True, help="output JSONL path (in data/real/)")
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args(argv)

    masker = Masker(seed=args.seed)
    records = read_jsonl(args.input)
    masked = [masker.mask_record(r, i) for i, r in enumerate(records, start=1)]
    write_jsonl(masked, args.output)

    print(f"Wrote {len(masked)} masked records to {args.output}")
    print("Values masked:", dict(+masker.counts))  # unary + drops zero/negative counts
    print("Now read through the output: rule-based masking can miss unusual names.")


if __name__ == "__main__":
    main()
