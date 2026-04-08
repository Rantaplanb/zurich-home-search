# Homegate Zurich CHF 1500-2000 Example

Date: 2026-04-05

## Count I could directly verify

From the accessible Homegate Zurich apartment search snapshot, I could directly verify **4** apartment listings in the **CHF 1,500-2,000** range on the visible first page:

- CHF 1,971: Rotbuchstrasse 9, 8006 Zürich
- CHF 1,600: Viktoriastrasse 29, 8057 Zürich
- CHF 1,995: Bernerstrasse Süd 167-169, 8048 Zürich
- CHF 1,574: Schärenmoosstrasse 99, 8050 Zürich

Important:

- This is **not** a verified full-city total for Homegate.
- It is the number I could directly confirm from the accessible search page content.
- Homegate's protected search API still blocks reliable end-to-end counting.

## Example listing fetched in detail

Chosen listing:

- Title: `City Pop - Deine flexible Lösung für lange und kürzere Aufenthalte um dich wie zu Hause zu fühlen`
- Listing page: `https://www.homegate.ch/rent/4002086457`
- Attached brochure URL: `https://media2.homegate.ch/listings/v2/e335city/4002086141/document/91d8c99f0c065f4ff5eda5cde7a7b690.pdf`

## Structured details

### Identity

- Listing ID: `4002086457`
- Object reference: `ghdf8.o9ta7`
- Type: `Apartment`
- Advertiser: `City Pop AG`

### Price and size

- Rent: `CHF 1,995.–`
- Rooms: `1.5`
- Bathrooms: `1`
- Living space: `23 m²`

### Dates and building

- Available from: `Immediately`
- Year built: `2022`
- Last refurbishment: `2022`

### Address

- Bernerstrasse Süd 167-169
- 8048 Zürich
- District path on Homegate:
  - Switzerland
  - Canton Zurich
  - Zurich
  - Kreis 9 (Zurich)
  - Altstetten (Zurich)

### Features and furnishings

- Dishwasher
- Cable TV
- View
- Quiet neighborhood
- Parking space
- Garage
- Elevator
- Raised ground floor

### Nearby on foot

- Public transport:
  - `5 min` to `Bändliweg`
- Train/tram station:
  - `6 min` to `Grünaustrasse`
- Supermarket:
  - `5 min` to `Coop`
- Pharmacy:
  - `6 min` to `BENU Apotheke`
- School:
  - `4 min` to `Benedict-Schule Zürich`

### Description

`City Pop Zurich Altstetten` offers fully furnished apartments at `Bernerstrasse Süd 167-169, 8048 Zürich`.

Key details from the listing page:

- Flexible stays for a few weeks or several months
- Apartment sizes in the building range from `18 to 67 m²`
- Starting prices in the building are advertised from `CHF 495/week`
- Some apartment variants have balconies
- Images are representative; layout may vary
- Minimum stay: `4 weeks`
- Included:
  - Kitchen, living area, sleeping area, bathroom
  - Full kitchen inventory
  - Towels and bed linen
  - Wi-Fi
  - Smart TV
  - Utilities included
- Extra services bookable via app:
  - Cleaning service
  - Shared laundry room
- Shared spaces:
  - Co-living areas
  - Co-working spaces
  - Sunny terrace

### Contact

- Advertiser: `City Pop AG`
- Address: `Bernerstrasse Süd 167-169, 8048 Zürich`
- Email shown in the description: `contact.ch@citypop.com`
- Website: `https://www.citypop.com`

## What was fetched locally

Verified locally from this machine:

- The attached brochure PDF downloads successfully from `media2.homegate.ch`.
- The listing detail page content is accessible through the browser-backed web fetch.

## Reliability note

For this listing, the most reliable locally fetchable artifact is the **attached brochure/document URL on `media2.homegate.ch`**.

That is useful for local archival and repeat fetches of a known listing.

What is still not solved reliably:

- enumerating all new Homegate listings end-to-end
- fetching arbitrary listing details directly from Homegate's protected API without first obtaining a listing/document URL
