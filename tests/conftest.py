from __future__ import annotations

from pathlib import Path

import pytest

from homegate_triage_assistant.config import (
    AppSettings,
    Config,
    GmailSettings,
    HomegateSettings,
    ImapSettings,
    NotificationSettings,
    OpenAISettings,
    SearchSettings,
    TransportSettings,
)


@pytest.fixture
def test_config(tmp_path: Path) -> Config:
    return Config(
        project_root=tmp_path,
        app=AppSettings(
            database_path=tmp_path / "triage.db",
            poll_interval_seconds=60,
            host="127.0.0.1",
            port=8000,
        ),
        search=SearchSettings(
            location="Zurich",
            office_address="Beethovenstrasse 48, Zurich",
            max_total_cost_chf=1800,
            desired_move_in_min_weeks=2,
            desired_move_in_max_weeks=8,
            acceptable_move_in_max_weeks=12,
        ),
        homegate=HomegateSettings(
            alert_sender_contains="homegate",
            alert_subject_contains="alert",
            chrome_channel="chrome",
            chrome_user_data_dir=tmp_path / "chrome-profile",
            chrome_profile_copy_dir=tmp_path / "chrome-profile-copy",
            headless=True,
            timeout_seconds=10,
        ),
        imap=ImapSettings(
            host="",
            port=993,
            username="",
            password="",
            mailbox="INBOX",
            search_query="UNSEEN",
            use_ssl=True,
        ),
        gmail=GmailSettings(
            client_id="",
            token_path=tmp_path / "gmail_tokens.json",
            query="from:homegate newer_than:14d",
            max_results=20,
            auth_port=8765,
            open_browser=False,
        ),
        openai=OpenAISettings(api_key="", model="gpt-5.4", max_output_tokens=700),
        notifications=NotificationSettings(enabled=True, channel="desktop"),
        transport=TransportSettings(base_url="https://transport.opendata.ch/v1/connections", enabled=False),
        weights={
            "total_cost_per_month": 20.0,
            "proximity_to_office_beethovenstrasse_48": 16.0,
            "vfm": 14.0,
            "size": 12.0,
            "alone_or_with_roommates": 10.0,
            "proximity_to_public_transport": 8.0,
            "move_in_date_fit": 7.0,
            "kitchen_quality": 5.0,
            "condition": 4.0,
            "proximity_to_big_supermarket": 4.0,
        },
    )
