# Comparis.ch Access Report

Tested on April 5, 2026 from this workspace and network.

## What Works

### 1. `curl_cffi` with browser TLS impersonation

`Comparis` is behind `DataDome`, so plain HTTP clients are blocked. The first reliable path I found was:

- Python `curl_cffi`
- browser impersonation such as `impersonate="chrome136"`
- a realistic `Referer` header for the internal API calls

This works repeatedly for both the search results API and the listing detail API.

### 2. Search results API

The result page bundle calls:

- `/immobilien/api/v1/singlepage/resultitems`

Request shape:

```json
{
  "Header": { "Language": "de" },
  "SearchParams": { "...": "..." },
  "Page": 1
}
```

Working request conditions:

- `Referer: https://www.comparis.ch/immobilien/marktplatz/...`
- browser impersonation through `curl_cffi`
- `Accept: application/json, text/plain, */*` if you want JSON

Observed behavior:

- `Referer` only: response is `200` and XML
- `Referer` + JSON `Accept`: response is `200` and JSON
- no `Referer`: `403` from `DataDome`

Useful fields returned:

- `AdIdList`
- `ResultItems`
- `CurrentPage`
- `NumberOfResults`
- `SearchParamsActivityGuid`
- each result item includes `AdId`, `Title`, `Address`, `Price`, `PriceValue`, `AreaValue`, `Date`, `PartnerName`

### 3. Listing detail API

The detail page bundle calls:

- `/immobilien/api/v1/singlepage/addetail`

Request shape:

```json
{
  "Header": { "Language": "de" },
  "AdId": 37050625,
  "SearchSubscriptionGuid": ""
}
```

Working request conditions:

- `Referer: https://www.comparis.ch/immobilien/marktplatz/details/show/<ad_id>`
- browser impersonation through `curl_cffi`
- JSON `Accept` if you want JSON instead of XML

Useful fields returned:

- `Ad`
- `ContactInformation`
- `SourceLinks`
- `TargetingInformation`
- `MortgageProviderInfo`
- `RecommenderEnabled`

The `Ad` object includes the description, address segments, room count, price, area, image URLs, and `FoundForTheFirstTime`.

### 4. HTML page bootstrap

The public result page HTML is fetchable with `curl_cffi` and includes `__NEXT_DATA__`. That is useful for bootstrapping the live `SearchParams` payload instead of hardcoding it.

The public detail page HTML is also fetchable with `curl_cffi` and includes the same detail data in `__NEXT_DATA__`.

### 5. Original provider redirect

The source link redirect works:

- `/immobilien/redirect/tooriginalad?adId=<ad_id>`

For example, ad `37050625` returned `302` to:

- `https://www.immoscout24.ch/mieten/4003056757`

This is useful as a fallback or for cross-checking provider-side data.

### 6. XML is a viable fallback

If you omit the JSON `Accept` header but keep a valid `Referer`, both working APIs still respond with `200` in XML. That is a second programmatic path if you prefer XML parsing.

## What Does Not Work Reliably

### 1. Plain `curl`

Plain `curl` gets an immediate `403` with `x-datadome: protected`.

### 2. Plain `requests`

Standard Python `requests` also gets blocked, even if I copy working cookies over from `curl_cffi`.

The cookie alone is not enough. The browser-like TLS fingerprint is still required.

### 3. Headless Playwright as the primary fetcher

Raw Playwright headless navigation was blocked with a temporary access block page.

I was able to improve that by injecting cookies from a successful `curl_cffi` session, but even then the page shell loaded while some browser-side API calls still returned `403`.

That makes headless Playwright a weak primary ingestion path here. It is not the most reliable option from this environment.

### 4. Server-side pagination through `?page=`

Fetching:

- `/immobilien/marktplatz/zuerich/wohnung/mieten?page=1`
- `/immobilien/marktplatz/zuerich/wohnung/mieten?page=2`

changes the page number inside `__NEXT_DATA__`, but the embedded result items stay on page 0. The real pagination happens through the internal `resultitems` API, not through server-rendered HTML.

So HTML-only pagination is not reliable.

## Important Limits

### Result API page cap

The result API appears capped at 100 pages:

- pages `0..99` return distinct data
- page `99` returned 9 items in my test
- page `100` and above wrapped back to page `0`

### Result API ID cap

The same API returned:

- `NumberOfResults` above 2400
- `AdIdList` length `999`

So Comparis appears to expose only the first 999 result IDs through this path. For a "new listings" poller that sorts by newest first, that is acceptable. It would be a problem for a full-history crawler.

## Practical Recommendation

For Comparis, the most reliable programmatic path I found is:

1. Fetch the public result HTML with `curl_cffi`.
2. Parse `__NEXT_DATA__` and extract `initialResultData.searchParams`.
3. Call `/immobilien/api/v1/singlepage/resultitems` with:
   - browser impersonation
   - the result page as `Referer`
   - JSON `Accept`
4. Track new listings by `AdId` and `FoundForTheFirstTime` / `Date`.
5. For each new `AdId`, call `/immobilien/api/v1/singlepage/addetail`.
6. Optionally resolve `/immobilien/redirect/tooriginalad?adId=<id>` to store the original portal URL.

That path is implemented in [scripts/fetch_comparis.py](/Users/mert/dev/personal/zurich-home-search/scripts/fetch_comparis.py).

## Email Notifications

Comparis clearly has a search subscription flow in the frontend, but I did not execute an end-to-end alert signup from this workspace because:

- it requires email ownership / confirmation semantics
- it is unnecessary as a primary ingestion path once the two internal APIs above are working
- email alone would still not be enough, because you still need the listing detail fetch after notification

So my conclusion is:

- email alerts may be a useful secondary signal
- they are not the best primary extraction method here
- the direct `resultitems` + `addetail` API route is the better solution
