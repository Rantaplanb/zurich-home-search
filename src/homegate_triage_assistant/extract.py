from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path
from datetime import date
from html import unescape
from typing import Any

import httpx
from bs4 import BeautifulSoup
from dateutil import parser as date_parser
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from .config import Config
from .schemas import ExtractedListing, ListingRecord


SECTION_HEADERS = {
    "location",
    "travel time",
    "surrounding information",
    "costs",
    "main information",
    "features and furnishings",
    "documents (0)",
    "description",
    "contact",
}


def parse_homegate_listing_html(
    url: str,
    homegate_id: str,
    html: str,
    office_address: str,
    transport_base_url: str,
    enable_transport: bool = True,
) -> ExtractedListing:
    soup = BeautifulSoup(html, "html.parser")
    lines = _normalized_lines(soup)
    full_text = "\n".join(lines)

    listing = ExtractedListing(
        homegate_id=homegate_id,
        url=url,
        title=_title_from_soup(soup),
        address=_line_after(lines, "Location"),
        rent_chf=_parse_currency(_line_after(lines, "Rent")),
        rooms=_parse_float(_line_after(lines, "Rooms")),
        living_space_sqm=_parse_square_meters(_line_after(lines, "Living space")),
        available_from=_parse_date_value(_line_after(lines, "Available from:")),
        listing_type=_line_after(lines, "Type:"),
        last_refurbishment_year=_parse_int(_line_after(lines, "Last refurbishment:")),
        year_built=_parse_int(_line_after(lines, "Year built:")),
        public_transport_walk_minutes=_minutes_for(lines, "Public Transport"),
        public_transport_name=_name_for(lines, "Public Transport"),
        supermarket_walk_minutes=_minutes_for(lines, "Supermarket"),
        supermarket_name=_name_for(lines, "Supermarket"),
        description=_section_body(lines, "Description", "Contact"),
        raw_text=full_text,
        extraction_status="success",
        facts={},
    )

    listing.extra_costs_chf = _parse_extra_costs(full_text)
    listing.total_cost_chf = _sum_costs(listing.rent_chf, listing.extra_costs_chf)

    postal_code, city = _parse_postal_city(listing.address)
    listing.postal_code = postal_code
    listing.city = city
    listing.is_roommate_listing = _infer_roommate_listing(listing.title, listing.description, listing.listing_type)

    if enable_transport and listing.address:
        listing.office_commute_minutes = fetch_commute_minutes(
            from_address=listing.address,
            to_address=office_address,
            base_url=transport_base_url,
        )

    listing.facts = {
        "parsed_from_html": True,
        "transport_enabled": enable_transport,
        "has_description": bool(listing.description),
    }
    return listing


class HomegateExtractor:
    def __init__(self, config: Config) -> None:
        self.config = config

    def extract(self, listing: ListingRecord, html_override: str | None = None) -> ExtractedListing:
        if html_override is not None:
            return parse_homegate_listing_html(
                url=listing.url,
                homegate_id=listing.homegate_id,
                html=html_override,
                office_address=self.config.search.office_address,
                transport_base_url=self.config.transport.base_url,
                enable_transport=self.config.transport.enabled,
            )

        try:
            html = self._fetch_html(listing.url)
        except Exception as exc:
            return ExtractedListing(
                homegate_id=listing.homegate_id,
                url=listing.url,
                title=listing.title,
                address=listing.address,
                city=listing.city,
                total_cost_chf=listing.total_cost_chf,
                raw_text=listing.source_email_excerpt,
                extraction_status="blocked",
                extraction_error=str(exc),
                facts={"fallback": "email_only"},
            )

        try:
            parsed = parse_homegate_listing_html(
                url=listing.url,
                homegate_id=listing.homegate_id,
                html=html,
                office_address=self.config.search.office_address,
                transport_base_url=self.config.transport.base_url,
                enable_transport=self.config.transport.enabled,
            )
            return parsed
        except Exception as exc:
            return ExtractedListing(
                homegate_id=listing.homegate_id,
                url=listing.url,
                title=listing.title,
                address=listing.address,
                city=listing.city,
                total_cost_chf=listing.total_cost_chf,
                raw_text=listing.source_email_excerpt,
                extraction_status="partial",
                extraction_error=f"HTML parsing failed: {exc}",
                facts={"fallback": "email_only"},
            )

    def _fetch_html(self, url: str) -> str:
        user_data_dir = self._prepare_profile_copy()
        with sync_playwright() as playwright:
            context = playwright.chromium.launch_persistent_context(
                user_data_dir=str(user_data_dir),
                channel=self.config.homegate.chrome_channel,
                headless=self.config.homegate.headless,
            )
            try:
                page = context.new_page()
                page.goto(url, wait_until="domcontentloaded", timeout=self.config.homegate.timeout_seconds * 1000)
                page.wait_for_timeout(1500)
                body_text = page.locator("body").inner_text(timeout=3000)
                lowered = body_text.lower()
                if "verify you are human" in lowered or "performing security verification" in lowered:
                    raise RuntimeError("Homegate blocked the browser session with Cloudflare verification.")
                return page.content()
            except PlaywrightTimeoutError as exc:
                raise RuntimeError("Homegate page load timed out.") from exc
            finally:
                context.close()

    def _prepare_profile_copy(self) -> Path:
        source = self.config.homegate.chrome_user_data_dir
        target = self.config.homegate.chrome_profile_copy_dir
        if target.exists():
            shutil.rmtree(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        command = [
            "rsync",
            "-a",
            "--delete",
            "--exclude=Singleton*",
            "--exclude=Crashpad",
            "--exclude=ShaderCache",
            "--exclude=GrShaderCache",
            "--exclude=GraphiteDawnCache",
            "--exclude=Code Cache",
            "--exclude=component_crx_cache",
            "--exclude=Safe Browsing",
            "--exclude=BrowserMetrics",
            "--exclude=optimization_guide_model_store",
            "--exclude=*.lock",
            "--exclude=.DS_Store",
            f"{source}/",
            str(target),
        ]
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        if result.returncode not in {0, 23, 24}:
            stderr = result.stderr.strip() or result.stdout.strip()
            raise RuntimeError(f"Failed to copy Chrome profile: {stderr}")
        return target


def fetch_commute_minutes(from_address: str, to_address: str, base_url: str) -> int | None:
    try:
        response = httpx.get(
            base_url,
            params={"from": from_address, "to": to_address, "limit": 1},
            timeout=15.0,
        )
        response.raise_for_status()
        payload: dict[str, Any] = response.json()
        duration = payload.get("connections", [{}])[0].get("duration")
        return _duration_to_minutes(duration)
    except Exception:
        return None


def _normalized_lines(soup: BeautifulSoup) -> list[str]:
    lines = [unescape(line.strip()) for line in soup.get_text("\n").splitlines()]
    return [line for line in lines if line]


def _title_from_soup(soup: BeautifulSoup) -> str | None:
    heading = soup.find("h1")
    if heading is None:
        return None
    title = heading.get_text(" ", strip=True).strip('"')
    return title or None


def _line_after(lines: list[str], label: str) -> str | None:
    lowered = label.lower().rstrip(":")
    for index, line in enumerate(lines):
        if line.lower().rstrip(":") == lowered:
            for next_line in lines[index + 1 :]:
                if next_line.lower() in SECTION_HEADERS:
                    break
                if next_line and next_line.lower().rstrip(":") != lowered:
                    return next_line
    return None


def _section_body(lines: list[str], start: str, end: str) -> str | None:
    try:
        start_index = next(i for i, value in enumerate(lines) if value.lower() == start.lower())
    except StopIteration:
        return None
    try:
        end_index = next(
            i for i, value in enumerate(lines[start_index + 1 :], start=start_index + 1)
            if value.lower() == end.lower()
        )
    except StopIteration:
        end_index = len(lines)
    body_lines = [line for line in lines[start_index + 1 : end_index] if line.lower() not in SECTION_HEADERS]
    return "\n".join(body_lines).strip() or None


def _parse_currency(value: str | None) -> float | None:
    if not value:
        return None
    match = re.search(r"CHF\s*([\d'.,]+)", value)
    if not match:
        return None
    normalized = match.group(1).replace("'", "").replace(",", "").replace(".–", "").replace(".-", "")
    normalized = normalized.replace("’", "")
    try:
        return float(normalized)
    except ValueError:
        return None


def _parse_float(value: str | None) -> float | None:
    if not value:
        return None
    match = re.search(r"(\d+(?:[.,]\d+)?)", value)
    if not match:
        return None
    return float(match.group(1).replace(",", "."))


def _parse_square_meters(value: str | None) -> float | None:
    return _parse_float(value)


def _parse_int(value: str | None) -> int | None:
    parsed = _parse_float(value)
    return int(parsed) if parsed is not None else None


def _parse_date_value(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date_parser.parse(value, dayfirst=True, fuzzy=True).date()
    except (ValueError, TypeError):
        return None


def _parse_postal_city(address: str | None) -> tuple[str | None, str | None]:
    if not address:
        return None, None
    match = re.search(r"(\d{4})\s+(.+)$", address)
    if not match:
        return None, None
    return match.group(1), match.group(2)


def _minutes_for(lines: list[str], label: str) -> int | None:
    value = _line_after(lines, label)
    if not value:
        return None
    match = re.search(r"(\d+)\s*min", value)
    return int(match.group(1)) if match else None


def _name_for(lines: list[str], label: str) -> str | None:
    value = _line_after(lines, label)
    if not value:
        return None
    match = re.search(r"\d+\s*min\.?\s*(.+)", value)
    if match:
        return match.group(1).strip()
    return value


def _parse_extra_costs(full_text: str) -> float | None:
    patterns = [
        r"Extra costs:\s*CHF\s*([\d'.,]+)",
        r"Charges:\s*CHF\s*([\d'.,]+)",
        r"Additional costs:\s*CHF\s*([\d'.,]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, full_text, re.IGNORECASE)
        if match:
            normalized = match.group(1).replace("'", "").replace(",", "")
            return float(normalized)
    return None


def _sum_costs(rent_chf: float | None, extra_costs_chf: float | None) -> float | None:
    if rent_chf is None:
        return None
    return round(rent_chf + (extra_costs_chf or 0.0), 2)


def _infer_roommate_listing(title: str | None, description: str | None, listing_type: str | None) -> bool | None:
    combined = " ".join(filter(None, [title, description, listing_type])).lower()
    if not combined:
        return None
    if "keine wg" in combined or "no wg" in combined or "apartment" in combined:
        if "wg" not in (title or "").lower():
            return False
    roommate_patterns = [
        r"\bwg\b",
        r"flatshare",
        r"flat share",
        r"coliving",
        r"co-living",
        r"\broom in\b",
        r"shared apartment",
    ]
    if any(re.search(pattern, combined) for pattern in roommate_patterns):
        return True
    if listing_type and listing_type.lower() == "apartment":
        return False
    return None


def _duration_to_minutes(duration: str | None) -> int | None:
    if not duration:
        return None
    match = re.match(r"(?:(\d+)d)?(\d+):(\d+):(\d+)", duration)
    if not match:
        return None
    days = int(match.group(1) or 0)
    hours = int(match.group(2))
    minutes = int(match.group(3))
    return days * 24 * 60 + hours * 60 + minutes
