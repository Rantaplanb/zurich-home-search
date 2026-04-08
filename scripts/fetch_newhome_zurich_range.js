#!/usr/bin/env node

const fs = require("fs");
const os = require("os");
const path = require("path");

function loadPlaywright() {
  try {
    return require("playwright");
  } catch (_error) {
    // Fall through to npm's npx cache. This keeps the script usable even if
    // Playwright is only available through `npx playwright`.
  }

  const npxRoot = path.join(os.homedir(), ".npm", "_npx");
  if (!fs.existsSync(npxRoot)) {
    throw new Error("Playwright not found locally or in ~/.npm/_npx");
  }

  const candidates = [];
  for (const entry of fs.readdirSync(npxRoot, { withFileTypes: true })) {
    if (!entry.isDirectory()) continue;
    const packageDir = path.join(
      npxRoot,
      entry.name,
      "node_modules",
      "playwright",
    );
    const packageJson = path.join(packageDir, "package.json");
    if (!fs.existsSync(packageJson)) continue;
    const stat = fs.statSync(packageJson);
    candidates.push({ packageDir, mtimeMs: stat.mtimeMs });
  }

  candidates.sort((a, b) => b.mtimeMs - a.mtimeMs);

  if (!candidates.length) {
    throw new Error("Playwright not found in ~/.npm/_npx");
  }

  return require(candidates[0].packageDir);
}

function toQuery(params) {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null) continue;
    if (Array.isArray(value)) {
      for (const item of value) search.append(key, String(item));
      continue;
    }
    search.append(key, String(value));
  }
  return search.toString();
}

async function fetchText(page, relativeUrl, options = {}) {
  return page.evaluate(
    async ({ relativeUrl, options }) => {
      const response = await fetch(relativeUrl, {
        credentials: "include",
        ...options,
      });
      const text = await response.text();
      return {
        ok: response.ok,
        status: response.status,
        text,
      };
    },
    { relativeUrl, options },
  );
}

async function fetchJson(page, relativeUrl, options = {}) {
  const result = await fetchText(page, relativeUrl, options);
  if (!result.ok) {
    throw new Error(
      `Request failed: ${relativeUrl} -> ${result.status}\n${result.text.slice(0, 500)}`,
    );
  }
  return JSON.parse(result.text);
}

async function launchWorkingBrowser(playwright, headless) {
  const attempts = [
    { channel: "chrome", headless },
    { channel: "msedge", headless },
  ];

  let lastError = null;
  for (const launchOptions of attempts) {
    try {
      return await playwright.chromium.launch(launchOptions);
    } catch (error) {
      lastError = error;
    }
  }

  throw lastError || new Error("Unable to launch Chrome or Edge");
}

function buildMarkdown({
  city,
  cityIdentifier,
  priceMin,
  priceMax,
  count,
  sampleEntry,
  detailResponse,
  generatedAt,
}) {
  const detail = detailResponse.detail;
  const detailInfo = detail.detail || {};
  const featureInfo = detail.feature || {};
  const priceInfo = detail.price || {};
  const availability = detailInfo.availabilityDate || "n/a";
  const address = [detail.street, detail.postalCode, detail.city]
    .filter(Boolean)
    .join(", ");

  return `# newhome.ch Zurich ${priceMin}-${priceMax} CHF Apartment Sample

Generated at: \`${generatedAt}\`

## Query

- City: \`${city}\`
- City identifier: \`${cityIdentifier}\`
- Offer type: \`2\` (rent)
- Property type: \`2\` (apartment)
- Price range: \`${priceMin}-${priceMax} CHF\`
- Ordering: \`NewestByListingDate\`

## Count

Zurich apartment rentals in the \`${priceMin}-${priceMax} CHF\` range: **${count}**

## Sample Listing

- ImmoCode: \`${sampleEntry.immocode}\`
- Title: ${sampleEntry.title}
- Address: ${address || "n/a"}
- Price: ${priceInfo.price ?? sampleEntry.price ?? "n/a"} CHF
- Rooms: ${detailInfo.rooms ?? sampleEntry.rooms ?? "n/a"}
- Living area: ${detailInfo.livingArea ?? sampleEntry.livingArea ?? "n/a"} m2
- Availability type: ${detailInfo.availabilityType ?? sampleEntry.availabilityType ?? "n/a"}
- Availability date: ${availability}
- Company: ${detail.contactCompanyName || sampleEntry.contactCompanyName || "n/a"}
- Original link: ${detail.linkUrl || "n/a"}

## Detail Summary

- Property subtype: ${detailInfo.propertySubType ?? detail.propertySubType ?? "n/a"}
- Floor: ${detailInfo.floor ?? sampleEntry.floor ?? "n/a"}
- Construction year: ${detailInfo.constructionYear ?? "n/a"}
- Object condition: ${detailInfo.objectCondition ?? "n/a"}
- Minergie: ${featureInfo.minergie ?? "n/a"}
- Balcony/Terrace: ${featureInfo.balconyTerrace ?? "n/a"}
- Lift: ${featureInfo.lift ?? "n/a"}
- Pets allowed: ${featureInfo.petsAllowed ?? "n/a"}
- Garage parking: ${featureInfo.garageParkingSpace ?? "n/a"}
- Parking space: ${featureInfo.parkingSpace ?? "n/a"}
- Child friendly: ${featureInfo.childFriendly ?? "n/a"}
- New building: ${featureInfo.newBuilding ?? "n/a"}
- Old building: ${featureInfo.oldBuilding ?? "n/a"}

## Raw Search Entry JSON

\`\`\`json
${JSON.stringify(sampleEntry, null, 2)}
\`\`\`

## Raw Listing Detail JSON

\`\`\`json
${JSON.stringify(detailResponse, null, 2)}
\`\`\`
`;
}

async function main() {
  const playwright = loadPlaywright();

  const priceMin = Number(process.env.NEW_HOME_PRICE_MIN || 1500);
  const priceMax = Number(process.env.NEW_HOME_PRICE_MAX || 2000);
  const cityKeyword = process.env.NEW_HOME_CITY_KEYWORD || "city-zurich";
  const languageIso = process.env.NEW_HOME_LANGUAGE || "en";
  const rowCount = Number(process.env.NEW_HOME_ROW_COUNT || 5);
  const headless = process.env.NEW_HOME_HEADLESS === "1";
  const outputPath =
    process.env.NEW_HOME_OUTPUT ||
    path.join(
      process.cwd(),
      "docs",
      "newhome-zurich-1500-2000-sample.md",
    );

  const browser = await launchWorkingBrowser(playwright, headless);
  try {
    const context = await browser.newContext({
      viewport: { width: 1400, height: 900 },
      locale: "en-US",
    });
    const page = await context.newPage();

    const bootstrap = await page.goto(
      "https://service.newhome.ch/api/api/HealthCheckPingRequest",
      { waitUntil: "domcontentloaded", timeout: 60_000 },
    );

    if (!bootstrap || bootstrap.status() !== 200) {
      throw new Error(
        `Bootstrap failed with status ${bootstrap ? bootstrap.status() : "null"}`,
      );
    }

    const location = await fetchJson(
      page,
      `/api/api/LocationResolveRequest?${toQuery({ keyword: cityKeyword })}`,
    );

    const countResponse = await fetchJson(
      page,
      `/api/api/GetAdvertSearchCountRequest?${toQuery({
        offerType: 2,
        propertyType: 2,
        location: location.identifier,
        priceMin,
        priceMax,
      })}`,
    );

    const searchResponse = await fetchJson(
      page,
      `/api/api/SearchListingRequest?${toQuery({
        offerType: 2,
        propertyType: 2,
        location: location.identifier,
        priceMin,
        priceMax,
        languageIso,
        rowCount,
        order: 1,
      })}`,
    );

    if (!searchResponse.entries || !searchResponse.entries.length) {
      throw new Error("No listings found for the requested range");
    }

    const sampleEntry = searchResponse.entries[0];
    const detailResponse = await fetchJson(
      page,
      `/api/api/ListingDetailRequest?${toQuery({
        immoCode: sampleEntry.immocode,
        languageIso,
      })}`,
    );

    const markdown = buildMarkdown({
      city: location.displayName,
      cityIdentifier: location.identifier,
      priceMin,
      priceMax,
      count: countResponse.totalResultCount,
      sampleEntry,
      detailResponse,
      generatedAt: new Date().toISOString(),
    });

    fs.mkdirSync(path.dirname(outputPath), { recursive: true });
    fs.writeFileSync(outputPath, markdown);

    console.log(
      JSON.stringify(
        {
          outputPath,
          count: countResponse.totalResultCount,
          sampleImmoCode: sampleEntry.immocode,
          sampleTitle: sampleEntry.title,
        },
        null,
        2,
      ),
    );
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  console.error(error.stack || String(error));
  process.exit(1);
});
