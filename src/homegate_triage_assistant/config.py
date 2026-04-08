from __future__ import annotations

import os
import tomllib
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


DEFAULT_WEIGHTS = {
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
}


DEFAULT_CONFIG: dict[str, Any] = {
    "app": {
        "database_path": "data/homegate_triage.db",
        "poll_interval_seconds": 60,
        "host": "127.0.0.1",
        "port": 8000,
    },
    "search": {
        "location": "Zurich",
        "office_address": "Beethovenstrasse 48, Zurich",
        "max_total_cost_chf": 1800,
        "desired_move_in_min_weeks": 2,
        "desired_move_in_max_weeks": 8,
        "acceptable_move_in_max_weeks": 12,
    },
    "homegate": {
        "alert_sender_contains": "homegate",
        "alert_subject_contains": "alert",
        "chrome_channel": "chrome",
        "chrome_user_data_dir": "~/Library/Application Support/Google/Chrome",
        "chrome_profile_copy_dir": "data/chrome-profile-copy",
        "headless": False,
        "timeout_seconds": 25,
    },
    "imap": {
        "host": "",
        "port": 993,
        "username": "",
        "password": "",
        "mailbox": "INBOX",
        "search_query": "UNSEEN",
        "use_ssl": True,
    },
    "gmail": {
        "client_id": "",
        "token_path": "data/gmail_tokens.json",
        "query": "from:homegate newer_than:14d",
        "max_results": 20,
        "auth_port": 8765,
        "open_browser": True,
    },
    "openai": {
        "model": "gpt-5.4",
        "api_key": "",
        "max_output_tokens": 700,
    },
    "notifications": {
        "enabled": True,
        "channel": "desktop",
    },
    "transport": {
        "base_url": "https://transport.opendata.ch/v1/connections",
        "enabled": True,
    },
    "weights": deepcopy(DEFAULT_WEIGHTS),
}


def _deep_merge(base: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


@dataclass(slots=True)
class AppSettings:
    database_path: Path
    poll_interval_seconds: int
    host: str
    port: int


@dataclass(slots=True)
class SearchSettings:
    location: str
    office_address: str
    max_total_cost_chf: int
    desired_move_in_min_weeks: int
    desired_move_in_max_weeks: int
    acceptable_move_in_max_weeks: int


@dataclass(slots=True)
class HomegateSettings:
    alert_sender_contains: str
    alert_subject_contains: str
    chrome_channel: str
    chrome_user_data_dir: Path
    chrome_profile_copy_dir: Path
    headless: bool
    timeout_seconds: int


@dataclass(slots=True)
class ImapSettings:
    host: str
    port: int
    username: str
    password: str
    mailbox: str
    search_query: str
    use_ssl: bool

    @property
    def is_configured(self) -> bool:
        return bool(self.host and self.username and self.password)


@dataclass(slots=True)
class GmailSettings:
    client_id: str
    token_path: Path
    query: str
    max_results: int
    auth_port: int
    open_browser: bool

    @property
    def is_configured(self) -> bool:
        return bool(self.client_id)


@dataclass(slots=True)
class OpenAISettings:
    api_key: str
    model: str
    max_output_tokens: int

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)


@dataclass(slots=True)
class NotificationSettings:
    enabled: bool
    channel: str


@dataclass(slots=True)
class TransportSettings:
    base_url: str
    enabled: bool


@dataclass(slots=True)
class Config:
    project_root: Path
    app: AppSettings
    search: SearchSettings
    homegate: HomegateSettings
    imap: ImapSettings
    gmail: GmailSettings
    openai: OpenAISettings
    notifications: NotificationSettings
    transport: TransportSettings
    weights: dict[str, float]

    @property
    def config_path(self) -> Path:
        return self.project_root / "config.toml"


def load_config(project_root: Path | None = None) -> Config:
    root = Path(project_root or Path.cwd()).resolve()
    load_dotenv(root / ".env", override=False)

    merged = deepcopy(DEFAULT_CONFIG)
    config_path = root / "config.toml"
    if config_path.exists():
        with config_path.open("rb") as handle:
            merged = _deep_merge(merged, tomllib.load(handle))

    env_overrides = {
        "imap": {
            "host": os.getenv("IMAP_HOST", ""),
            "port": int(os.getenv("IMAP_PORT", merged["imap"]["port"])),
            "username": os.getenv("IMAP_USERNAME", ""),
            "password": os.getenv("IMAP_PASSWORD", ""),
        },
        "gmail": {
            "client_id": os.getenv("GOOGLE_CLIENT_ID", ""),
        },
        "openai": {
            "api_key": os.getenv("OPENAI_API_KEY", ""),
            "model": os.getenv("OPENAI_MODEL", merged["openai"]["model"]),
        },
    }
    merged = _deep_merge(merged, env_overrides)

    weights = {key: float(value) for key, value in merged["weights"].items()}
    if not weights:
        raise ValueError("At least one weight must be configured.")
    if any(value <= 0 for value in weights.values()):
        raise ValueError("All configured weights must be positive.")

    return Config(
        project_root=root,
        app=AppSettings(
            database_path=(root / merged["app"]["database_path"]).resolve(),
            poll_interval_seconds=int(merged["app"]["poll_interval_seconds"]),
            host=str(merged["app"]["host"]),
            port=int(merged["app"]["port"]),
        ),
        search=SearchSettings(
            location=str(merged["search"]["location"]),
            office_address=str(merged["search"]["office_address"]),
            max_total_cost_chf=int(merged["search"]["max_total_cost_chf"]),
            desired_move_in_min_weeks=int(merged["search"]["desired_move_in_min_weeks"]),
            desired_move_in_max_weeks=int(merged["search"]["desired_move_in_max_weeks"]),
            acceptable_move_in_max_weeks=int(merged["search"]["acceptable_move_in_max_weeks"]),
        ),
        homegate=HomegateSettings(
            alert_sender_contains=str(merged["homegate"]["alert_sender_contains"]),
            alert_subject_contains=str(merged["homegate"]["alert_subject_contains"]),
            chrome_channel=str(merged["homegate"]["chrome_channel"]),
            chrome_user_data_dir=Path(str(merged["homegate"]["chrome_user_data_dir"])).expanduser(),
            chrome_profile_copy_dir=(root / str(merged["homegate"]["chrome_profile_copy_dir"])).resolve(),
            headless=bool(merged["homegate"]["headless"]),
            timeout_seconds=int(merged["homegate"]["timeout_seconds"]),
        ),
        imap=ImapSettings(
            host=str(merged["imap"]["host"]),
            port=int(merged["imap"]["port"]),
            username=str(merged["imap"]["username"]),
            password=str(merged["imap"]["password"]),
            mailbox=str(merged["imap"]["mailbox"]),
            search_query=str(merged["imap"]["search_query"]),
            use_ssl=bool(merged["imap"]["use_ssl"]),
        ),
        gmail=GmailSettings(
            client_id=str(merged["gmail"]["client_id"]),
            token_path=(root / str(merged["gmail"]["token_path"])).resolve(),
            query=str(merged["gmail"]["query"]),
            max_results=int(merged["gmail"]["max_results"]),
            auth_port=int(merged["gmail"]["auth_port"]),
            open_browser=bool(merged["gmail"]["open_browser"]),
        ),
        openai=OpenAISettings(
            api_key=str(merged["openai"]["api_key"]),
            model=str(merged["openai"]["model"]),
            max_output_tokens=int(merged["openai"]["max_output_tokens"]),
        ),
        notifications=NotificationSettings(
            enabled=bool(merged["notifications"]["enabled"]),
            channel=str(merged["notifications"]["channel"]),
        ),
        transport=TransportSettings(
            base_url=str(merged["transport"]["base_url"]),
            enabled=bool(merged["transport"]["enabled"]),
        ),
        weights=weights,
    )
