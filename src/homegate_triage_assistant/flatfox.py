from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


API_ROOT = "https://flatfox.ch/api/v1"
SITE_ROOT = "https://flatfox.ch"
USER_AGENT = "zurich-home-search flatfox-fetcher/1.0"


@dataclass(frozen=True)
class BBox:
    west: float
    south: float
    east: float
    north: float

    @property
    def width(self) -> float:
        return self.east - self.west

    @property
    def height(self) -> float:
        return self.north - self.south

    def as_query_items(self) -> list[tuple[str, str]]:
        return [
            ("west", f"{self.west:.6f}"),
            ("south", f"{self.south:.6f}"),
            ("east", f"{self.east:.6f}"),
            ("north", f"{self.north:.6f}"),
        ]

    def split(self) -> list["BBox"]:
        mid_lon = (self.west + self.east) / 2
        mid_lat = (self.south + self.north) / 2
        return [
            BBox(self.west, self.south, mid_lon, mid_lat),
            BBox(mid_lon, self.south, self.east, mid_lat),
            BBox(self.west, mid_lat, mid_lon, self.north),
            BBox(mid_lon, mid_lat, self.east, self.north),
        ]

    @classmethod
    def parse(cls, raw_value: str) -> "BBox":
        parts = [part.strip() for part in raw_value.split(",")]
        if len(parts) != 4:
            raise ValueError("bbox must be west,south,east,north")
        west, south, east, north = (float(part) for part in parts)
        if west >= east or south >= north:
            raise ValueError("bbox must satisfy west < east and south < north")
        return cls(west=west, south=south, east=east, north=north)


def build_url(path: str, items: list[tuple[str, str]]) -> str:
    query = urllib.parse.urlencode(items, doseq=True)
    return f"{API_ROOT}{path}?{query}"


def request_json(url: str) -> Any:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def fetch_pins(
    bbox: BBox,
    *,
    offer_type: str,
    object_category: str,
    max_pin_count: int,
) -> list[dict[str, Any]]:
    query_items = bbox.as_query_items() + [
        ("max_count", str(max_pin_count)),
        ("offer_type", offer_type),
        ("object_category", object_category),
    ]
    return request_json(build_url("/pin/", query_items))


def dedupe_pins(pins: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_pk: dict[int, dict[str, Any]] = {}
    for pin in pins:
        by_pk[int(pin["pk"])] = pin
    return list(by_pk.values())


def collect_pins(
    bbox: BBox,
    *,
    offer_type: str,
    object_category: str,
    max_pin_count: int,
    max_split_depth: int,
    min_span: float,
    warnings: list[str],
    depth: int = 0,
) -> list[dict[str, Any]]:
    pins = fetch_pins(
        bbox,
        offer_type=offer_type,
        object_category=object_category,
        max_pin_count=max_pin_count,
    )
    if len(pins) < max_pin_count:
        return pins

    if depth >= max_split_depth or min(bbox.width, bbox.height) <= min_span:
        warnings.append(
            (
                "Pin query hit the max_count cap without enough room to split "
                f"further: bbox={bbox} count={len(pins)} max_count={max_pin_count}"
            )
        )
        return pins

    merged: list[dict[str, Any]] = []
    for child_bbox in bbox.split():
        merged.extend(
            collect_pins(
                child_bbox,
                offer_type=offer_type,
                object_category=object_category,
                max_pin_count=max_pin_count,
                max_split_depth=max_split_depth,
                min_span=min_span,
                warnings=warnings,
                depth=depth + 1,
            )
        )
    return dedupe_pins(merged)


def chunked(values: list[int], chunk_size: int) -> list[list[int]]:
    return [values[index : index + chunk_size] for index in range(0, len(values), chunk_size)]


def fetch_listing_batch(pks: list[int]) -> list[dict[str, Any]]:
    query_items: list[tuple[str, str]] = [("limit", "0"), ("expand", "cover_image")]
    query_items.extend(("pk", str(pk)) for pk in pks)
    return request_json(build_url("/public-listing/", query_items))


def fetch_listing_detail(pk: int) -> dict[str, Any]:
    return enrich_listing(request_json(f"{API_ROOT}/public-listing/{pk}/"))


def fetch_listing_details(pks: list[int], *, max_workers: int = 16) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(fetch_listing_detail, pk): pk for pk in pks}
        for future in as_completed(futures):
            results.append(future.result())
    return results


def enrich_listing(listing: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(listing)
    if "url" in enriched:
        enriched["absolute_url"] = urllib.parse.urljoin(SITE_ROOT, enriched["url"])
    if "short_url" in enriched:
        enriched["absolute_short_url"] = urllib.parse.urljoin(SITE_ROOT, enriched["short_url"])
    cover_image = enriched.get("cover_image")
    if isinstance(cover_image, dict):
        cover = dict(cover_image)
        for key in ("url", "url_thumb_m", "url_listing_search"):
            if key in cover and cover[key]:
                cover[f"absolute_{key}"] = urllib.parse.urljoin(SITE_ROOT, cover[key])
        enriched["cover_image"] = cover
    return enriched


def listing_timestamp(listing: dict[str, Any]) -> datetime:
    for key in ("published", "created"):
        value = listing.get(key)
        if value:
            return datetime.fromisoformat(value)
    return datetime.fromtimestamp(0, tz=timezone.utc)


def fetch_listings_for_bbox(
    bbox: BBox,
    *,
    offer_type: str,
    object_category: str,
    max_pin_count: int,
    detail_batch_size: int,
    max_split_depth: int,
    min_span: float,
) -> tuple[list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    pins = collect_pins(
        bbox,
        offer_type=offer_type,
        object_category=object_category,
        max_pin_count=max_pin_count,
        max_split_depth=max_split_depth,
        min_span=min_span,
        warnings=warnings,
    )
    pks = sorted({int(pin["pk"]) for pin in pins})
    listings: list[dict[str, Any]] = []
    for pk_batch in chunked(pks, detail_batch_size):
        listings.extend(fetch_listing_batch(pk_batch))

    filtered = [
        enrich_listing(listing)
        for listing in listings
        if listing.get("offer_type") == offer_type and listing.get("object_category") == object_category
    ]
    filtered.sort(
        key=lambda listing: (listing_timestamp(listing), int(listing["pk"])),
        reverse=True,
    )
    return filtered, warnings


def load_seen_pks(state_file: Path) -> set[int]:
    if not state_file.exists():
        return set()
    raw_text = state_file.read_text().strip()
    if not raw_text:
        return set()
    raw_state = json.loads(raw_text)
    return {int(pk) for pk in raw_state.get("seen_pks", [])}


def save_state(state_file: Path, seen_pks: set[int], payload: dict[str, Any]) -> None:
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state = {
        "updated_at": payload["fetched_at"],
        "search": payload["search"],
        "seen_pks": sorted(seen_pks),
    }
    state_file.write_text(json.dumps(state, indent=2, ensure_ascii=True) + "\n")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch Flatfox listings through the public pin + public-listing APIs."
    )
    parser.add_argument(
        "--bbox",
        default="8.45,47.30,8.65,47.45",
        help="Search area as west,south,east,north. Default is a Zurich-area box.",
    )
    parser.add_argument("--offer-type", default="RENT")
    parser.add_argument("--object-category", default="HOUSE")
    parser.add_argument("--max-pin-count", type=int, default=1000)
    parser.add_argument("--detail-batch-size", type=int, default=100)
    parser.add_argument("--max-split-depth", type=int, default=8)
    parser.add_argument(
        "--min-span",
        type=float,
        default=0.002,
        help="Stop splitting when the smaller bbox side drops below this size in degrees.",
    )
    parser.add_argument(
        "--state-file",
        type=Path,
        help="Optional JSON state file used to detect newly seen listings across runs.",
    )
    parser.add_argument(
        "--only-new",
        action="store_true",
        help="When used with --state-file, output only listings that were not seen before.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Trim the output after sorting newest-first.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        bbox = BBox.parse(args.bbox)
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 2

    try:
        listings, warnings = fetch_listings_for_bbox(
            bbox,
            offer_type=args.offer_type,
            object_category=args.object_category,
            max_pin_count=args.max_pin_count,
            detail_batch_size=args.detail_batch_size,
            max_split_depth=args.max_split_depth,
            min_span=args.min_span,
        )
    except urllib.error.HTTPError as error:
        print(f"Flatfox request failed with HTTP {error.code}: {error.reason}", file=sys.stderr)
        return 1
    except urllib.error.URLError as error:
        print(f"Flatfox request failed: {error.reason}", file=sys.stderr)
        return 1

    fetched_at = datetime.now(tz=timezone.utc).isoformat()
    seen_pks_before: set[int] = set()
    new_listings: list[dict[str, Any]] = []
    if args.state_file:
        seen_pks_before = load_seen_pks(args.state_file)
        new_listings = [listing for listing in listings if int(listing["pk"]) not in seen_pks_before]
        save_state(
            args.state_file,
            seen_pks_before | {int(listing["pk"]) for listing in listings},
            {
                "fetched_at": fetched_at,
                "search": {
                    "bbox": args.bbox,
                    "offer_type": args.offer_type,
                    "object_category": args.object_category,
                },
            },
        )

    output_listings = new_listings if args.only_new and args.state_file else listings
    if args.limit is not None:
        output_listings = output_listings[: max(args.limit, 0)]
        new_listings = new_listings[: max(args.limit, 0)]

    payload = {
        "fetched_at": fetched_at,
        "search": {
            "bbox": args.bbox,
            "offer_type": args.offer_type,
            "object_category": args.object_category,
        },
        "counts": {
            "current_listings": len(listings),
            "output_listings": len(output_listings),
            "new_since_previous_run": len(new_listings) if args.state_file else None,
        },
        "warnings": warnings,
        "listings": output_listings,
    }
    if args.state_file:
        payload["new_listings"] = new_listings

    print(json.dumps(payload, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
