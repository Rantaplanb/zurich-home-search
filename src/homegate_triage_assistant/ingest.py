from __future__ import annotations

import email
import imaplib
import re
from datetime import datetime
from email.header import decode_header, make_header
from email.message import Message
from email.policy import default
from typing import Iterable

from .config import Config
from .schemas import ParsedAlert


HOMEGATE_URL_RE = re.compile(r"https://(?:www\.)?homegate\.ch/rent/\d+")


def extract_homegate_id(url: str) -> str | None:
    match = re.search(r"/rent/(\d+)", url)
    return match.group(1) if match else None


def extract_homegate_urls(text: str) -> list[str]:
    return sorted(set(HOMEGATE_URL_RE.findall(text)))


def _decode_header_value(value: str | None) -> str:
    if not value:
        return ""
    return str(make_header(decode_header(value)))


def _extract_bodies(message: Message) -> tuple[str, str | None]:
    text_body: list[str] = []
    html_body: list[str] = []
    if message.is_multipart():
        for part in message.walk():
            content_type = part.get_content_type()
            if content_type == "text/plain":
                text_body.append(part.get_content())
            elif content_type == "text/html":
                html_body.append(part.get_content())
    else:
        content = message.get_content()
        if message.get_content_type() == "text/html":
            html_body.append(content)
        else:
            text_body.append(content)
    return "\n".join(text_body).strip(), "\n".join(html_body).strip() or None


def _extract_received_at(message: Message) -> datetime | None:
    date_header = message.get("Date")
    if not date_header:
        return None
    parsed = email.utils.parsedate_to_datetime(date_header)
    return parsed


def _listing_excerpt(raw_text: str, url: str) -> str | None:
    index = raw_text.find(url)
    if index == -1:
        return None
    start = max(0, index - 120)
    end = min(len(raw_text), index + len(url) + 120)
    snippet = " ".join(raw_text[start:end].split())
    return snippet or None


def parse_homegate_email(raw_message: bytes, config: Config) -> ParsedAlert | None:
    message = email.message_from_bytes(raw_message, policy=default)
    sender = _decode_header_value(message.get("From"))
    subject = _decode_header_value(message.get("Subject"))
    if config.homegate.alert_sender_contains.lower() not in sender.lower():
        return None
    if config.homegate.alert_subject_contains.lower() not in subject.lower():
        return None

    raw_text, raw_html = _extract_bodies(message)
    body_blob = "\n".join(filter(None, [raw_text, raw_html or ""]))
    listing_urls = extract_homegate_urls(body_blob)
    if not listing_urls:
        return None

    message_id = _decode_header_value(message.get("Message-ID")) or f"missing-{hash(body_blob)}"
    return ParsedAlert(
        message_id=message_id,
        sender=sender,
        subject=subject,
        received_at=_extract_received_at(message),
        raw_text=raw_text or body_blob,
        raw_html=raw_html,
        listing_urls=listing_urls,
    )


class IMAPAlertFetcher:
    def __init__(self, config: Config) -> None:
        self.config = config

    def poll(self) -> list[ParsedAlert]:
        if not self.config.imap.is_configured:
            return []

        client: imaplib.IMAP4 | imaplib.IMAP4_SSL
        if self.config.imap.use_ssl:
            client = imaplib.IMAP4_SSL(self.config.imap.host, self.config.imap.port)
        else:
            client = imaplib.IMAP4(self.config.imap.host, self.config.imap.port)

        try:
            client.login(self.config.imap.username, self.config.imap.password)
            client.select(self.config.imap.mailbox)
            status, data = client.search(None, self.config.imap.search_query)
            if status != "OK":
                return []

            parsed_alerts: list[ParsedAlert] = []
            for message_num in _message_nums(data):
                fetch_status, parts = client.fetch(message_num, "(RFC822)")
                if fetch_status != "OK":
                    continue
                raw_message = _raw_message(parts)
                if not raw_message:
                    continue
                parsed = parse_homegate_email(raw_message, self.config)
                if parsed is not None:
                    parsed_alerts.append(parsed)
            return parsed_alerts
        finally:
            try:
                client.close()
            except Exception:
                pass
            client.logout()

    @staticmethod
    def build_listing_refs(alert: ParsedAlert) -> list[tuple[str, str, str | None]]:
        refs: list[tuple[str, str, str | None]] = []
        for url in alert.listing_urls:
            homegate_id = extract_homegate_id(url)
            if homegate_id is None:
                continue
            refs.append((homegate_id, url, _listing_excerpt(alert.raw_text, url)))
        return refs


def _message_nums(data: Iterable[bytes]) -> list[bytes]:
    nums: list[bytes] = []
    for chunk in data:
        nums.extend(chunk.split())
    return nums


def _raw_message(parts: list[tuple[bytes, bytes] | bytes]) -> bytes | None:
    for part in parts:
        if isinstance(part, tuple):
            return part[1]
    return None
