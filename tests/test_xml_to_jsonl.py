"""Tests for src/collect/xml_to_jsonl.py, using a small made-up export."""

from src.collect.jsonl_io import read_jsonl
from src.collect.xml_to_jsonl import epoch_ms_to_iso, find_xml_files, main, parse_sms_xml

FAKE_EXPORT = """<?xml version='1.0' encoding='UTF-8' standalone='yes' ?>
<smses count="4">
  <sms protocol="0" address="VM-HDFCBK" date="1759046400000" type="1"
       body="Rs.450.00 debited from A/c XX1234 &amp; more&#10;-HDFC Bank" contact_name="(Unknown)" />
  <sms protocol="0" address="+919999999999" date="1759046500000" type="2"
       body="a message I sent" contact_name="Someone" />
  <sms protocol="0" address="AD-SBIINB" date="1759046600000" type="1" body="   " />
  <sms protocol="0" address="JD-ICICIB-S" date="not-a-number" type="1" body="₹120 paid" />
</smses>
"""


def write_export(tmp_path, name="export.xml"):
    path = tmp_path / name
    path.write_text(FAKE_EXPORT, encoding="utf-8")
    return path


def test_epoch_ms_to_iso_uses_ist():
    assert epoch_ms_to_iso("1759046400000") == "2025-09-28T13:30:00+05:30"


def test_epoch_ms_to_iso_handles_bad_values():
    assert epoch_ms_to_iso(None) is None
    assert epoch_ms_to_iso("abc") is None


def test_keeps_only_received_non_empty_sms(tmp_path):
    records = parse_sms_xml(write_export(tmp_path))
    # Sent message (type 2) and blank body are dropped.
    assert [r["sender"] for r in records] == ["VM-HDFCBK", "JD-ICICIB-S"]


def test_record_fields_and_xml_unescaping(tmp_path):
    first, second = parse_sms_xml(write_export(tmp_path))
    assert first["body"] == "Rs.450.00 debited from A/c XX1234 & more\n-HDFC Bank"
    assert first["date"] == "2025-09-28T13:30:00+05:30"
    assert first["source_file"] == "export.xml"
    assert set(first) == {"sender", "date", "body", "source_file"}  # no contact_name
    assert second["date"] is None
    assert second["body"] == "₹120 paid"


def test_find_xml_files_expands_folders(tmp_path):
    write_export(tmp_path, "b.xml")
    write_export(tmp_path, "a.xml")
    (tmp_path / "notes.txt").write_text("ignore me")
    assert [p.name for p in find_xml_files([str(tmp_path)])] == ["a.xml", "b.xml"]


def test_main_combines_files(tmp_path):
    write_export(tmp_path, "me.xml")
    write_export(tmp_path, "friend.xml")
    out = tmp_path / "out" / "all.jsonl"
    main([str(tmp_path), "-o", str(out)])
    records = read_jsonl(out)
    assert len(records) == 4
    assert {r["source_file"] for r in records} == {"me.xml", "friend.xml"}
