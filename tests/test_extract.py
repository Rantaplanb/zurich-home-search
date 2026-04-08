from __future__ import annotations

from pathlib import Path

from homegate_triage_assistant.extract import parse_homegate_listing_html


def test_parse_homegate_listing_html_extracts_expected_fields() -> None:
    html = Path("tests/fixtures/homegate_listing.html").read_text()
    extracted = parse_homegate_listing_html(
        url="https://www.homegate.ch/rent/4003058517",
        homegate_id="4003058517",
        html=html,
        office_address="Beethovenstrasse 48, Zurich",
        transport_base_url="https://transport.opendata.ch/v1/connections",
        enable_transport=False,
    )
    assert extracted.title is not None
    assert extracted.total_cost_chf == 1790
    assert extracted.living_space_sqm == 60
    assert extracted.city == "Zurich"
    assert extracted.available_from.isoformat() == "2026-06-01"
    assert extracted.public_transport_walk_minutes == 2
    assert extracted.supermarket_walk_minutes == 10
    assert extracted.is_roommate_listing is False
    assert extracted.extraction_status == "success"


def test_parse_homegate_listing_html_detects_roommate_listing() -> None:
    html = """
    <html><body>
      <h1>WG room in Zurich Oerlikon</h1>
      <div>Location</div><div>Somewhere 10, 8050 Zurich</div>
      <div>Rent</div><div>CHF 1200.-</div>
      <div>Description</div><div>Bright WG room in a shared apartment.</div>
      <div>Contact</div>
    </body></html>
    """
    extracted = parse_homegate_listing_html(
        url="https://www.homegate.ch/rent/123",
        homegate_id="123",
        html=html,
        office_address="Beethovenstrasse 48, Zurich",
        transport_base_url="https://transport.opendata.ch/v1/connections",
        enable_transport=False,
    )
    assert extracted.is_roommate_listing is True
