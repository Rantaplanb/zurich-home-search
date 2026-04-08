from __future__ import annotations

from pathlib import Path

from homegate_triage_assistant.ingest import IMAPAlertFetcher, extract_homegate_id, parse_homegate_email


def test_parse_homegate_email_extracts_listing_links(test_config) -> None:
    fixture = Path("tests/fixtures/homegate_alert.eml").read_bytes()
    parsed = parse_homegate_email(fixture, test_config)
    assert parsed is not None
    assert parsed.message_id == "<alert-1@example.com>"
    assert parsed.listing_urls == ["https://www.homegate.ch/rent/4003058517"]
    refs = IMAPAlertFetcher.build_listing_refs(parsed)
    assert refs[0][0] == "4003058517"
    assert "Wohnung" in (refs[0][2] or "")


def test_extract_homegate_id_handles_homegate_listing_urls() -> None:
    assert extract_homegate_id("https://www.homegate.ch/rent/4003058517") == "4003058517"
    assert extract_homegate_id("https://www.homegate.ch/rent/not-a-listing") is None
