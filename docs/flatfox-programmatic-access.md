# Flatfox Programmatic Access Findings

Date of probing: `2026-04-05`

## What Works

### 1. Public JSON discovery API

`GET https://flatfox.ch/api/v1/pin/` works without authentication and returns lightweight listing records for a map bounding box.

Reliable query parameters I verified:

- `west`, `south`, `east`, `north`
- `max_count`
- `offer_type`
- `object_category`

Example that worked for rental houses around Zurich:

```text
https://flatfox.ch/api/v1/pin/?west=8.45&south=47.30&east=8.65&north=47.45&max_count=1000&offer_type=RENT&object_category=HOUSE
```

Observed behavior:

- `max_count` worked at `100`, `400`, and `1000`
- `max_count=2000` returned `400 Bad Request`
- large search areas can hit the cap, so the reliable approach is bbox subdivision

### 2. Public JSON hydration API

`GET https://flatfox.ch/api/v1/public-listing/<pk>/` works without authentication and returns the full public listing JSON for a specific listing id.

Example that worked:

```text
https://flatfox.ch/api/v1/public-listing/85929279/
```

This returned fields such as:

- `created`
- `published`
- `offer_type`
- `object_category`
- `object_type`
- `public_title`
- `description`
- `surface_living`
- `number_of_rooms`
- `images`

### 3. Batched listing hydration

`GET https://flatfox.ch/api/v1/public-listing/?limit=0&pk=<id>&pk=<id>...` works without authentication and returns a JSON list.

Reliable additions:

- repeated `pk` parameters
- `limit=0`
- `expand=cover_image`

However, in later checks on `2026-04-05`, this batched endpoint was not reliable for authoritative detail fields. For the same `pk`, it disagreed with the direct endpoint on fields such as:

- `price_display`
- `public_title`
- `surface_living`
- `number_of_rooms`

So it is useful for reverse-engineering and bulk convenience, but not as the source of truth for final listing details.

### 4. Playwright as reverse-engineering fallback

The search page at `/en/search/` is not server-rendered with listing data, but Playwright confirmed the browser itself uses the same public API flow:

1. call `/api/v1/pin/` for ids in the visible bbox
2. call `/api/v1/public-listing/?limit=0&pk=...` to hydrate visible pins

That means browser automation is useful for discovery and regression checks, but not required for production fetching.

## What Partially Works

### 1. Search page HTML

`GET /en/search/` works anonymously, but it returns only the app shell plus bootstrap config. The actual listing data is fetched later via XHR.

This is not a reliable primary source for scraping listings directly from HTML.

### 2. List endpoint filtering on `public-listing`

I tested list-style filters like:

- `offer_type=RENT`
- `object_category=HOUSE`
- `ordering=-published`

on `GET /api/v1/public-listing/`.

In my tests on `2026-04-05`, those filters did not reliably affect the returned list. `limit`, `offset`, repeated `pk`, and `expand=cover_image` did work.

So the reliable pattern is:

1. filter with `/api/v1/pin/`
2. fetch authoritative final details with `/api/v1/public-listing/<pk>/`

## What Does Not Work Reliably

### 1. Authenticated listing endpoint

`GET /api/v1/listing/` returned `403` with:

- `Authentication credentials were not provided.`

So it is not usable anonymously.

### 2. RSS / feed style endpoints

I tested:

- `/rss`
- `/rss/`
- `/feed`
- `/feed/`
- `/feeds`
- `/feeds/`
- `/api/v1/feed/`

Observed behavior:

- the feed-style paths redirected to localized variants and then ended in `404`
- `/api/v1/feed/` returned `404`

I did not find a usable public RSS/Atom feed.

### 3. Generic listing-page scraping by guessed slug

If you guess a detail-page slug incorrectly, Flatfox can redirect you into generic marketing content instead of a listing page. That makes slug-guessing HTML scraping unreliable compared with direct JSON by `pk`.

## Recommended Approach

Use the public APIs directly:

1. Query `/api/v1/pin/` with bbox + `offer_type=RENT` + `object_category=HOUSE`
2. If the result count reaches `max_count`, split the bbox into smaller tiles and repeat
3. Use the pin response for lightweight discovery and price-band filtering
4. Fetch final details with `/api/v1/public-listing/<pk>/`
5. Sort locally by `published` or `created`
6. Track seen `pk` values locally to detect newly seen listings across runs

## Repo Artifact

The module [`src/homegate_triage_assistant/flatfox.py`](/Users/mert/dev/personal/zurich-home-search/src/homegate_triage_assistant/flatfox.py) now contains:

- bbox subdivision
- batched hydration
- direct per-listing hydration helpers
- optional stateful new-listing detection
- JSON output
