"""Convert SMS Backup & Restore (Android) XML exports into one JSONL file.

The export looks like:

    <smses count="2">
      <sms address="VM-HDFCBK" date="1759046400000" type="1" body="Rs.450.00 debited ..." />
      ...
    </smses>

`date` is milliseconds since 1970 (Unix epoch). `type` is 1 for received (inbox)
and 2 for sent. Only received messages are kept, since banks send to us.

Contact names, phone metadata, etc. are dropped on purpose: we keep only what
the later steps need.

Usage:
    python -m src.collect.xml_to_jsonl data/raw -o data/raw/all.jsonl
    python -m src.collect.xml_to_jsonl data/raw/me.xml data/raw/friend.xml -o data/raw/all.jsonl
"""

import argparse
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.collect.jsonl_io import write_jsonl

INBOX_TYPE = "1"
# All exports come from Indian phones, so use IST rather than the laptop's
# local timezone; this keeps output identical on any machine.
IST = timezone(timedelta(hours=5, minutes=30))


def epoch_ms_to_iso(value: str | None) -> str | None:
    """'1759046400000' -> '2025-09-28T13:30:00+05:30'; None if missing or garbled."""
    try:
        return datetime.fromtimestamp(int(value) / 1000, tz=IST).isoformat(timespec="seconds")
    except (TypeError, ValueError, OverflowError, OSError):
        return None


def parse_sms_xml(path: str | Path) -> list[dict]:
    """Return one record per received SMS in an export file."""
    path = Path(path)
    root = ET.parse(path).getroot()
    records = []
    # .iter() finds <sms> elements at any depth, so a slightly different
    # export layout still works. MMS entries (<mms>) are ignored.
    for sms in root.iter("sms"):
        body = (sms.get("body") or "").strip()
        if sms.get("type") != INBOX_TYPE or not body:
            continue
        records.append(
            {
                "sender": (sms.get("address") or "").strip(),
                "date": epoch_ms_to_iso(sms.get("date")),
                "body": body,
                "source_file": path.name,
            }
        )
    return records


def find_xml_files(inputs: list[str]) -> list[Path]:
    """Expand folders into the .xml files inside them (PowerShell doesn't expand *.xml)."""
    files: list[Path] = []
    for item in map(Path, inputs):
        files.extend(sorted(item.glob("*.xml")) if item.is_dir() else [item])
    return files


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("inputs", nargs="+", help="XML files, or folders containing them")
    parser.add_argument("-o", "--output", required=True, help="output JSONL path")
    args = parser.parse_args(argv)

    files = find_xml_files(args.inputs)
    if not files:
        parser.error("no .xml files found")

    records = []
    for file in files:
        found = parse_sms_xml(file)
        print(f"{file.name}: {len(found)} received SMS")
        records.extend(found)

    count = write_jsonl(records, args.output)
    print(f"Wrote {count} records to {args.output}")


if __name__ == "__main__":
    main()
