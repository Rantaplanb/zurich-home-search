#!/usr/bin/env python3

import argparse
import json
import re
import sys
import urllib.parse
from urllib.parse import urlparse
from typing import Any, Dict, List, Optional

try:
    from curl_cffi import requests
except ImportError as exc:  # pragma: no cover - import guard for local use
    raise SystemExit(
        "Missing dependency: curl_cffi. Install it with "
        "`python3 -m pip install --user curl_cffi`."
    ) from exc


NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
    re.S,
)

DEFAULT_SEARCH_URL = (
    "https://www.comparis.ch/immobilien/marktplatz/zuerich/wohnung/mieten?sort=3"
)


class ComparisError(RuntimeError):
    pass


class ComparisClient:
    def __init__(self, impersonate: str = "chrome136") -> None:
        self.session = requests.Session(impersonate=impersonate)

    def _request(
        self,
        url: str,
        *,
        referer: Optional[str] = None,
        accept_json: bool = False,
        allow_redirects: bool = True,
    ) -> requests.Response:
        headers: Dict[str, str] = {}
        if referer:
            headers["referer"] = referer
        if accept_json:
            headers["accept"] = "application/json, text/plain, */*"
        response = self.session.get(
            url,
            headers=headers,
            allow_redirects=allow_redirects,
            timeout=30,
        )
        if response.status_code >= 400:
            body = response.text[:400].replace("\n", " ")
            raise ComparisError(f"{response.status_code} for {url}: {body}")
        return response

    def fetch_bootstrap(self, search_url: str) -> Dict[str, Any]:
        response = self._request(search_url)
        match = NEXT_DATA_RE.search(response.text)
        if not match:
            raise ComparisError(
                "Comparis search page did not include __NEXT_DATA__. "
                "The anti-bot response likely changed."
            )
        data = json.loads(match.group(1))
        page_props = data["props"]["pageProps"]
        initial = page_props["initialResultData"]
        language = infer_language(search_url, response.text)
        return {
            "language": language,
            "search_params": initial["searchParams"],
            "bootstrap_page": initial["page"],
            "bootstrap_total_pages": initial["totalPages"],
            "bootstrap_number_of_results": initial["numberOfResults"],
            "initial_sort": initial["sort"],
        }

    def fetch_result_page(
        self,
        *,
        search_url: str,
        search_params: Dict[str, Any],
        language: str,
        page: int,
    ) -> Dict[str, Any]:
        request_object = {
            "Header": {"Language": language},
            "SearchParams": search_params,
            "Page": page,
        }
        url = (
            "https://www.comparis.ch/immobilien/api/v1/singlepage/resultitems"
            "?requestObject="
            + urllib.parse.quote(json.dumps(request_object, separators=(",", ":")))
        )
        response = self._request(url, referer=search_url, accept_json=True)
        return response.json()

    def fetch_detail(self, ad_id: int, *, language: str) -> Dict[str, Any]:
        referer = (
            f"https://www.comparis.ch/immobilien/marktplatz/details/show/{ad_id}"
        )
        request_object = {
            "Header": {"Language": language},
            "AdId": ad_id,
            "SearchSubscriptionGuid": "",
        }
        url = (
            "https://www.comparis.ch/immobilien/api/v1/singlepage/addetail"
            "?requestObject="
            + urllib.parse.quote(json.dumps(request_object, separators=(",", ":")))
        )
        response = self._request(url, referer=referer, accept_json=True)
        payload = response.json()
        payload["OriginalAdUrl"] = self.fetch_original_url(ad_id)
        return payload

    def fetch_original_url(self, ad_id: int) -> Optional[str]:
        referer = (
            f"https://www.comparis.ch/immobilien/marktplatz/details/show/{ad_id}"
        )
        url = f"https://www.comparis.ch/immobilien/redirect/tooriginalad?adId={ad_id}"
        response = self._request(url, referer=referer, allow_redirects=False)
        if response.status_code in (301, 302, 303, 307, 308):
            return response.headers.get("location")
        return None


def compact_result_item(item: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "ad_id": item["AdId"],
        "title": item["Title"],
        "property_type": item.get("PropertyTypeText"),
        "address": item.get("Address"),
        "summary": item.get("EssentialInformation"),
        "price": item.get("Price"),
        "price_value": item.get("PriceValue"),
        "currency": item.get("Currency"),
        "date": item.get("Date"),
        "partner_name": item.get("PartnerName"),
        "detail_url": f"https://www.comparis.ch/immobilien/marktplatz/details/show/{item['AdId']}",
    }


def infer_language(search_url: str, html: str) -> str:
    parsed = urlparse(search_url)
    host = parsed.netloc.lower()
    if host.startswith("en."):
        return "en"
    if host.startswith("fr."):
        return "fr"
    if host.startswith("it."):
        return "it"

    html_lang = re.search(r"<html[^>]+lang=\"([a-z]{2})", html, re.I)
    if html_lang:
        return html_lang.group(1).lower()
    return "de"


def compact_detail(payload: Dict[str, Any]) -> Dict[str, Any]:
    ad = payload["Ad"]
    return {
        "ad_id": ad["AdId"],
        "title": ad.get("Title"),
        "display_title": ad.get("DisplayTitle"),
        "property_type": ad.get("PropertyTypeText"),
        "price": ad.get("Price"),
        "price_text": ad.get("PriceText"),
        "area": ad.get("Area"),
        "num_rooms": ad.get("NumRooms"),
        "found_for_the_first_time": ad.get("FoundForTheFirstTime"),
        "address": ad.get("AddressSegments"),
        "main_data": ad.get("MainData"),
        "features": ad.get("Features"),
        "price_information": ad.get("PriceInformation"),
        "remarks": ad.get("Remarks"),
        "image_urls": ad.get("ImageUrls"),
        "contact_information": payload.get("ContactInformation"),
        "source_links": payload.get("SourceLinks"),
        "original_ad_url": payload.get("OriginalAdUrl"),
        "sharing_url": ad.get("SharingUrl"),
    }


def build_output(
    client: ComparisClient,
    *,
    search_url: str,
    pages: int,
    detail_count: int,
) -> Dict[str, Any]:
    bootstrap = client.fetch_bootstrap(search_url)
    result_pages: List[Dict[str, Any]] = []
    collected_ids: List[int] = []

    for page in range(pages):
        payload = client.fetch_result_page(
            search_url=search_url,
            search_params=bootstrap["search_params"],
            language=bootstrap["language"],
            page=page,
        )
        items = [compact_result_item(item) for item in payload["ResultItems"]]
        result_pages.append(
            {
                "requested_page": page,
                "current_page": payload.get("CurrentPage"),
                "returned_item_count": len(items),
                "number_of_results": payload.get("NumberOfResults"),
                "ad_id_list_size": len(payload.get("AdIdList", [])),
                "items": items,
            }
        )
        collected_ids.extend(item["ad_id"] for item in items)

    details: List[Dict[str, Any]] = []
    for ad_id in collected_ids[:detail_count]:
        details.append(compact_detail(client.fetch_detail(ad_id, language=bootstrap["language"])))

    return {
        "search_url": search_url,
        "language": bootstrap["language"],
        "bootstrap_page": bootstrap["bootstrap_page"],
        "bootstrap_total_pages": bootstrap["bootstrap_total_pages"],
        "bootstrap_number_of_results": bootstrap["bootstrap_number_of_results"],
        "initial_sort": bootstrap["initial_sort"],
        "pages_requested": pages,
        "detail_records_requested": detail_count,
        "result_pages": result_pages,
        "details": details,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Fetch Comparis rental listings through the working internal endpoints "
            "discovered on 2026-04-05."
        )
    )
    parser.add_argument(
        "--search-url",
        default=DEFAULT_SEARCH_URL,
        help="Comparis result page to bootstrap search parameters from.",
    )
    parser.add_argument(
        "--pages",
        type=int,
        default=1,
        help="How many result pages to fetch from the internal resultitems API.",
    )
    parser.add_argument(
        "--details",
        type=int,
        default=0,
        help="How many returned ad IDs to enrich through the addetail API.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.pages < 1:
        print("--pages must be >= 1", file=sys.stderr)
        return 2
    if args.details < 0:
        print("--details must be >= 0", file=sys.stderr)
        return 2

    client = ComparisClient()
    try:
        payload = build_output(
            client,
            search_url=args.search_url,
            pages=args.pages,
            detail_count=args.details,
        )
    except ComparisError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
