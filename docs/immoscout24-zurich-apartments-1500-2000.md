# ImmoScout24 Zurich Apartments 1500-2000 CHF

Date: 2026-04-05

## Scope

Goal:

- Check how many Zurich apartment rental listings I can directly verify on ImmoScout24 in the `CHF 1,500-2,000` range.
- Extract one listing in full and store the details locally as Markdown.

Important limitation:

- The ImmoScout24 website is still blocked from this machine for normal local HTTP clients and automated browsers.
- The data below was fetched through a browser-backed web fetch path that can read the public listing/search pages, not through a repeatable local `curl`/`requests`/Playwright workflow.

## What I Could Directly Verify

Live Zurich apartment search page:

- Search URL: `https://www.immoscout24.ch/de/wohnung/mieten/ort-zuerich`
- Observed page title at fetch time: `1052 Wohnungen zum Mieten: Zürich (ab CHF 1'574.-)`

Listings I could directly see on the accessible search snapshots inside the `CHF 1,500-2,000` range:

1. `CHF 1'971` - Rotbuchstrasse 9, `8006 Zurich`
2. `CHF 1'995` - Bernerstrasse Sud 167-169, `8048 Zurich`
3. `CHF 1'574` - Scharenmoosstrasse 99, `8050 Zurich`

Count I can verify directly from the reachable snapshots: **3**

Why this is not a trustworthy citywide total:

- I could not apply the `1500-2000` filter through a stable URL or local script.
- Page snapshots were inconsistent across requests, including different total hit counts on later pages.
- Local automation still lands on DataDome captcha pages, so I cannot enumerate the full filtered result set reliably from this machine.

## Sample Listing

Source listing URL:

- `https://www.immoscout24.ch/mieten/4002086457`

Listing summary:

- Listing ID: `4002086457`
- Object ref: `ghdf8.o9ta7`
- Title: `City Pop - Deine flexible Losung fur lange und kurzere Aufenthalte um dich wie zu Hause zu fuhlen`
- Property type: `Wohnung`
- Rooms: `1.5`
- Bathrooms: `1`
- Living area: `23 m2`
- Rent: `CHF 1'995.-`
- Availability: `Sofort`
- Address: `Bernerstrasse Sud 167-169, 8048 Zurich`
- Year built: `2022`
- Last renovation year: `2022`

Provider:

- Name: `City Pop AG`
- Provider page: `https://www.immoscout24.ch/anbieter/e335city/city-pop-ag`
- Provider address: `Bernerstrasse Sud 167-169, 8048 Zurich`
- Contact email shown in description: `contact.ch@citypop.com`
- Provider inventory at fetch time: `62 Immobilien zu vermieten`

Property features explicitly listed on the page:

- `Geschirrspuler`
- `Kabel-TV`
- `Aussicht`
- `Ruhige Lage`
- `Parkplatz`
- `Garage`
- `Lift`
- `Hochparterre`

Nearby places shown on the page:

- Station `Grunaustrasse`: `6 min` walk
- Pharmacy `BENU Apotheke`: `6 min` walk
- Supermarket `Coop`: `5 min` walk
- School `Benedict-Schule Zurich`: `4 min` walk
- Public transport stop `Bandliweg`: `5 min` walk

## Description

German text extracted from the listing page:

> Willkommen im City Pop Zurich Altstetten! Unsere stilvoll eingerichteten Apartments an der Bernerstrasse Sud 167-169, 8048 Zurich sind bereits seit einiger Zeit eroffnet und bieten modernes, flexibles Wohnen im lebendigen Stadtteil Altstetten. Ob fur ein paar Wochen oder mehrere Monate - bei uns finden Sie auf 18 bis 67 Quadratmetern alles, was Sie zum Leben brauchen. Ab 495 CHF/Woche stehen Ihnen verschiedene Pop-Typen zur Auswahl: S, M, L, XK und 2.5-Zimmer-Apartments - einige davon sogar mit Balkon.

> Die beigefugten Bilder stammen aus anderen City Pop Apartments und dienen der Veranschaulichung. Die Moblierung ist identisch - lediglich das Layout kann leicht variieren.

> So einfach buchen Sie Ihr Apartment:

> Laden Sie unsere App herunter:
> Fur iOS: City Pop im App Store suchen
> Fur Android: City Pop im Google Play Store suchen

> Einfach App installieren, ein Konto erstellen und dann:
> "Suchen und Jetzt Buchen!" wahlen
> Zurich als Stadt eingeben
> Check-in- und Check-out-Daten auswahlen

> Was Sie erwartet:
> Unsere Apartments sind vollstandig mobliert und ausgestattet, inklusive:
> Kuche, Wohnbereich, Schlafbereich und Bad
> Vollstandiges Kucheninventar (Teller, Glaser, Topfe usw.)
> Handtucher & Bettwasche
> Wi-Fi und Smart TV
> Alle Nebenkosten inklusive

> Der Mindestaufenthalt betragt 4 Wochen. Zusatzliche Services, direkt uber die App buchbar:
> Reinigungsservice (wochentlich oder zweiwochentlich)
> Waschraum zur gemeinschaftlichen Nutzung

> Auserdem stehen Ihnen tolle Gemeinschaftsbereiche zur Verfugung, wie z. B.:
> Co-Living-Zonen
> Co-Working-Spaces
> Eine sonnige Terrasse

> So einfach wie ein Hotel - nur viel mehr Zuhause. Worauf warten Sie noch? Entdecken Sie City Pop Zurich Altstetten an der Bernerstrasse Sud 167-169!

> Bei Fragen oder fur weitere Informationen: contact.ch@citypop.com

## Media And Attachments

Listing page image gallery:

- The listing exposes a 16-image gallery on the detail page.
- The page text indicates the images are representative images from other City Pop apartments, not guaranteed to be photos of this exact unit.

Attachment:

- The detail page exposes one attachment link.
- Resolved attachment URL: `https://cdn.immoscout24.ch/listings/v2/e335city/4002086141/document/91d8c99f0c065f4ff5eda5cde7a7b690.pdf`
- Note: the attachment asset path uses `4002086141`, not the listing page ID `4002086457`, which suggests this is a shared building or project document rather than a listing-unique brochure.

Representative image URL resolved from the page:

- `https://cdn.immoscout24.ch/f_auto/t_web_dp_small/listings/v2/e335city/4002086141/image/107143110dbcbd41e01dfefdf50aa5a6.jpg`

## Reliability Assessment

What worked for this sample:

- Search result page fetch through the browser-backed web path
- Listing detail page fetch through the browser-backed web path
- Attachment URL resolution
- Direct CDN attachment/image fetches once the asset URLs were known

What still does not work locally and consistently:

- `curl` / `requests` against the listing page
- Playwright against the listing page
- Full citywide enumeration of all Zurich apartments in the `CHF 1,500-2,000` range from this machine

Bottom line:

- I can locally store one full listing detail snapshot as Markdown.
- I still cannot claim a repeatable, no-human local fetch path for ImmoScout24 listing details from this environment.
