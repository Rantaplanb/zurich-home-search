# `newhome.ch` Programmatic Access Report

Tested on `2026-04-05` from `Europe/Athens` against the live site.

## Bottom Line

There is a real backend API behind `newhome.ch`, and it does return full listing data programmatically.

The reliable path I found is:

- use a **headed** real browser session (`Google Chrome` or `Microsoft Edge`)
- talk directly to `https://service.newhome.ch/api/api/...`
- poll `SearchListingRequest` ordered by newest
- diff on `immocode`
- fetch full records with `ListingDetailRequest`

The unreliable or non-working paths are:

- plain `curl` / direct HTTP client requests
- copied browser cookies replayed via `curl`
- Playwright `headless: true`
- Playwright `APIRequestContext` / non-browser HTTP after bootstrapping cookies
- scraping `www.newhome.ch` HTML as the primary source

## What Worked

### 1. Direct service API access through a headed browser

The backend is on `https://service.newhome.ch/api`.

These endpoints returned live JSON when opened in a **headed** Chrome/Edge session:

- `GET /api/api/HealthCheckPingRequest`
- `GET /api/api/LocationResolveRequest?keyword=city-zurich`
- `GET /api/api/SearchLocationRequest?keyword=zurich&languageIso=en`
- `GET /api/api/SearchListingRequest?offerType=2&propertyType=2&location=1;2560&languageIso=en&rowCount=3&order=1`
- `GET /api/api/GetAdvertSearchCountRequest?offerType=2&propertyType=2&location=1;2560`
- `GET /api/api/SearchListingCoordinatesRequest?offerType=2&propertyType=2&location=1;2560&languageIso=en`
- `GET /api/api/ListingDetailRequest?immoCode=6064256&languageIso=en`
- `GET /api/api/AdvertActiveRequest?immoCode=6064256`

Concrete results I verified:

- `LocationResolveRequest?keyword=city-zurich` returned Zurich with identifier `1;2560`
- `SearchLocationRequest?keyword=zurich&languageIso=en` returned multiple location choices including:
  - city Zurich: `1;2560`
  - region Zurich: `3;4797`
  - canton Zurich: `4;26`
- `SearchListingRequest` returned live rental listings with fields including:
  - `immocode`
  - `title`
  - `price`
  - `rooms`
  - `livingArea`
  - `postalCode`
  - `latitude` / `longitude`
  - `images`
  - `isNewResult`
- `GetAdvertSearchCountRequest` returned `560` for Zurich apartment rentals with that sample filter
- `ListingDetailRequest` returned the full detail payload for `immocode=6064256`, including image formats and richer detail data

### 2. Same-origin browser `fetch()` after landing on `service.newhome.ch`

After first loading any page on `service.newhome.ch` in a headed Chrome session, same-origin JavaScript `fetch()` calls from that page also worked.

That means you do not need to keep navigating top-level pages for every request. A practical pattern is:

1. open `https://service.newhome.ch/api/api/HealthCheckPingRequest` in a headed browser
2. use browser-side `fetch()` to call `SearchListingRequest`
3. diff new `immocode` values
4. call `ListingDetailRequest` for each new `immocode`

### 3. Anonymous email search subscription creation

I verified that the API can create an unconfirmed email search subscription programmatically, anonymously, via:

- `POST /api/api/CreateSearchSubscriptionRequest`

Minimum body shape that worked:

```json
{
  "subscriptionDetails": {
    "languageIso": "en",
    "frequency": 1,
    "eMail": "not-an-email",
    "name": "Probe Search",
    "filter": {
      "offerType": 2,
      "propertyType": 2,
      "location": ["1;2560"]
    }
  }
}
```

The response was:

```json
{
  "id": 2631033,
  "guid": "e161626e-b510-4c46-b9ba-f29205bb565a",
  "name": "Probe Search",
  "assignedToUser": false,
  "needEmailConfirmation": true
}
```

I also verified cleanup worked via:

- `DELETE /api/api/DeleteSearchSubscriptionRequest?guid=<guid>`

## What Did Not Work

### 1. Plain HTTP clients

These were blocked by Cloudflare with `403` and `cf-mitigated: challenge`:

- `curl https://www.newhome.ch/...`
- `curl https://service.newhome.ch/api/api/...`

This stayed blocked even when I replayed:

- browser cookies
- a real Chrome user-agent
- the exact same API URL

### 2. Playwright headless mode

`Playwright` with `headless: true` failed against `service.newhome.ch` and landed on the Cloudflare verification page instead of JSON.

`headless: false` succeeded immediately for the same URL.

### 3. Playwright HTTP client / storage-state replay

I bootstrapped a valid headed browser session first, saved storage state, then retried via `Playwright`’s non-browser request client.

That still returned `403` with the Cloudflare challenge page.

So this is not a “solve once, then switch to raw HTTP” setup.

### 4. Scraping `www.newhome.ch` itself

The main site was inconsistent:

- sometimes a headed browser could load it
- other times even the homepage fell into Cloudflare verification
- cross-origin API calls from `www.newhome.ch` to `service.newhome.ch` returned `403` before the service host had been opened directly

Because of that, I would not rely on DOM scraping from `www.newhome.ch` as the primary pipeline.

## Subscription / Email Caveats

I verified subscription creation and deletion, but I did **not** verify real email contents because no mailbox was wired into the test.

Other subscription endpoints were quirky:

- `GET /api/api/GetSearchSubscriptionsRequest` returned empty arrays anonymously
- `GET /api/api/GetSearchSubscriptionRequest?guid=...` returned a backend `500` serialization error
- `GET /api/api/LeadAllowedSearchSubscriptionRequest` returned `405 NotImplementedException`

So email subscriptions exist, but I would not make them the primary data source. At best they are a secondary trigger if you already have mailbox automation.

## Recommended Extraction Strategy

Use the service API directly from a headed Chrome/Edge Playwright session.

Suggested polling flow:

1. bootstrap a headed browser on `https://service.newhome.ch/api/api/HealthCheckPingRequest`
2. call `SearchLocationRequest?keyword=zurich&languageIso=en` once and persist the chosen identifier
3. poll `SearchListingRequest?...&order=1&rowCount=<n>` for your search
4. diff on `immocode`
5. for new IDs, call `ListingDetailRequest?immoCode=<id>&languageIso=en`
6. persist your own seen-set and timestamps locally

For “new listing” detection, prefer your own `immocode` diff over `isNewResult`. The `isNewResult` flag exists and is useful, but it looks presentation-oriented rather than like a canonical event feed.

## Sample Query Set

Zurich apartment rentals:

```text
LocationResolveRequest?keyword=city-zurich
SearchLocationRequest?keyword=zurich&languageIso=en
SearchListingRequest?offerType=2&propertyType=2&location=1;2560&languageIso=en&rowCount=20&order=1
ListingDetailRequest?immoCode=<IMMOCODE>&languageIso=en
```

## Practical Recommendation

If you want automation for `newhome.ch`, build it around:

- headed Playwright
- direct calls to `service.newhome.ch`
- `immocode`-based diffing
- detail enrichment via `ListingDetailRequest`

Do not build it around:

- `curl`
- headless Playwright
- raw HTTP replay after copying cookies
- scraping `www.newhome.ch` result pages
