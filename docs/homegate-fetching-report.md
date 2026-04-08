# Homegate Fetching Report

Date: 2026-04-05

## Goal

Find a programmatically reliable way to fetch new Homegate rental house listings and retrieve actual listing data, not just a notification that something new exists.

## Tested Paths

### 1. Raw website fetches

Tested:

- `GET https://www.homegate.ch/en`
- `GET https://www.homegate.ch/robots.txt`

Result:

- Blocked by Cloudflare + DataDome.
- Returned a JS/captcha/interstitial page instead of usable HTML.

Conclusion:

- Not reliable for scraping with `curl`, `requests`, or similar plain HTTP clients.

### 2. Official-looking API endpoints on `api.homegate.ch`

Reverse-engineered sources found:

- `GET /geo/locations`
- `POST /search/listings`
- `GET /listings/listing/{id}?sanitize=true`

Observed behavior:

- `GET https://api.homegate.ch/geo/locations?lang=en&name=8001&size=1`
  - Worked.
  - Returned structured JSON with geo IDs such as `geo-zipcode-8001`.
- `POST https://api.homegate.ch/search/listings`
  - Blocked with HTTP `403`.
  - Response body was a DataDome captcha URL.
- `GET https://api.homegate.ch/listings/listing/{id}?sanitize=true`
  - Blocked with HTTP `403`.
  - Response body was a DataDome captcha URL.

Conclusion:

- Geo lookup works.
- Listing search and listing detail APIs are currently protected and not usable directly.

### 3. Browser automation

Tested:

- Playwright with bundled Chromium, headless
- Playwright with bundled Chromium, headed
- Playwright connected to stock Google Chrome over CDP
- Stealthier Chrome launch:
  - `ignoreDefaultArgs: ['--enable-automation']`
  - `--disable-blink-features=AutomationControlled`
  - patched `navigator.webdriver`, `navigator.languages`, `window.chrome`
- Long waits up to 60 seconds

Result:

- All variants still landed on a DataDome captcha/device-check page.
- No real Homegate app HTML or listing XHR traffic became available.

Conclusion:

- I could not verify any no-human Playwright path that reliably reaches listing data.

### 4. Cookie replay from a browser session

Tested:

- Load Homegate in real Chrome
- Export cookies from the browser session
- Replay `POST /search/listings` with those cookies and browser-like headers

Result:

- Still blocked with HTTP `403`.

Conclusion:

- Browser-issued cookies alone are not enough.

### 5. In-browser fetches from a live browser page

Tested:

- `fetch('https://api.homegate.ch/search/listings', ...)` from a browser page context

Result:

- Still blocked with HTTP `403` and a DataDome captcha payload.

Conclusion:

- Even requests originating from the browser runtime remain blocked unless the anti-bot challenge is fully cleared.

### 6. TLS / browser impersonation HTTP client

Tested:

- Python `curl_cffi` with Chrome impersonation

Result:

- `GET /geo/locations` worked
- `POST /search/listings` blocked
- `GET /listings/listing/{id}` blocked

Conclusion:

- Transport impersonation does not unlock the protected listing endpoints.

### 7. Public listing media assets

Tested:

- Direct brochure/document URL on `media2.homegate.ch`

Example:

- `https://media2.homegate.ch/listings/v2/hgonif/4002330640/document/63b15011ae582948780b4679fc4df827.pdf`

Result:

- Worked without Homegate anti-bot blocking.
- The brochure PDF contained rich listing data:
  - title
  - address
  - rent and charges
  - move-in date
  - description
  - contact name, email, phone

Conclusion:

- `media2.homegate.ch` is a viable detail source if you already know the asset URL.
- The hard part is discovery. I did not find a reliable first-party way to enumerate new listing asset URLs programmatically.

### 8. Search alerts and app notifications

Verified from Homegate’s public advisor/app pages:

- Search alert emails are sent immediately when a new matching listing is posted.
- The mobile app can send instant push notifications for saved searches.

Important limitation:

- I did not verify an end-to-end machine-readable payload for these notifications.
- They are reliable for detection, but I could not prove a programmatic path from notification to full listing data without hitting the protected site/API.

## What Works

Verified working:

- `GET /geo/locations` for structured location resolution
- Direct fetch of known brochure/document PDFs on `media2.homegate.ch`
- Official notification channels for new listings:
  - search alert emails
  - app push notifications

## What Does Not Work

Verified not working:

- Raw scraping of `www.homegate.ch`
- Raw scraping of `robots.txt`
- `POST /search/listings`
- `GET /listings/listing/{id}`
- Playwright, headed or headless
- Stock Chrome over CDP
- Stealthier Playwright tweaks
- Cookie replay
- In-browser `fetch`
- TLS impersonation via `curl_cffi`

## Bottom Line

I did not find a verified no-human, first-party, programmatically reliable path to:

1. enumerate brand-new Homegate listings, and
2. fetch full listing data for each of them

through Homegate’s current protected search/detail endpoints.

The strongest verified building blocks are:

- Homegate search alerts or app push for new-listing detection
- `media2.homegate.ch` brochure PDFs for rich listing details, when the document URL is known

But I did not verify a reliable bridge between those two pieces.

## Most Promising Next Step

If you want the most practical path forward, the next thing to test is:

1. Create a real Homegate search alert manually.
2. Capture one or more alert emails.
3. Check whether the email body contains enough structured listing fields or direct media links.
4. If it does, treat the mailbox as the ingestion source instead of the website.

That is the only first-party route I found that still looks plausibly reliable, but it remains unverified until we inspect real alert emails.

## Useful Sources

- Homegate search alert page:
  - https://www.homegate.ch/c/en/advisor/renting/find-an-apartment/search-alert
- Homegate app page:
  - https://www.homegate.ch/c/en/advisor/renting/find-an-apartment/mobile-app
- Homegate TenantPlus page:
  - https://www.homegate.ch/en/tenantplus
- Reverse-engineered Homegate API client:
  - https://github.com/babiscodelab/ch-homegate/tree/main
