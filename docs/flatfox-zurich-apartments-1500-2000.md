# Flatfox Zurich Apartments in CHF 1500-2000

Date checked: `2026-04-05`

## Result

- Zurich bbox used for discovery: `west=8.45`, `south=47.30`, `east=8.65`, `north=47.45`
- Object filter: `offer_type=RENT`, `object_category=APARTMENT`
- Wider Zurich bbox apartment rentals found: `1594`
- Wider Zurich bbox apartments in CHF `1500-2000`: `87`
- Zurich city proper apartments in CHF `1500-2000`: `67`

Important consistency note:

- I first tested the batched hydration endpoint `GET /api/v1/public-listing/?pk=...`
- For multiple listings, it returned stale or wrong values for price, rooms, surface, and even address text
- The counts in this document therefore use `pin` for discovery and `public-listing/<pk>` for authoritative per-listing detail checks

For the city-proper count, I filtered the direct-detail results to listings whose `city` is `Zürich` or `Zurich`.

## Reliable Local Fetch Path

The consistent path is:

1. `GET /api/v1/pin/` with bbox + `offer_type=RENT` + `object_category=APARTMENT`
2. If a tile hits the `max_count` cap, split the bbox and repeat
3. Use the pin results for initial price-band filtering
4. Fetch final details directly with `GET /api/v1/public-listing/<pk>/`

This is local and repeatable. It does not depend on Playwright or DOM scraping.

## Sample Listing

I picked the newest Zurich city listing in the CHF `1500-2000` band at the time of the check, using the direct single-listing endpoint as the source of truth.

- `pk`: `85929980`
- `published`: `2026-04-04T12:08:38.519874+02:00`
- `title`: `Konradstrasse 52, 8005 Zürich - CHF 1’690 incl. utilities per month`
- `absolute_url`: [https://flatfox.ch/en/flat/konradstrasse-52-8005-zurich/85929980/](https://flatfox.ch/en/flat/konradstrasse-52-8005-zurich/85929980/)
- Full-detail endpoint: [https://flatfox.ch/api/v1/public-listing/85929980/](https://flatfox.ch/api/v1/public-listing/85929980/)

### Human Summary

- Type: `APARTMENT`
- Rooms: `3.5`
- Living area: not provided in the direct detail response
- Floor: `-3`
- Price: `CHF 1690 / month`
- Address: `Konradstrasse 52, 8005 Zürich`
- Move-in date: `2026-05-01`
- Furnished: `false`
- Selling furniture: `false`
- Shared-flat style listing: yes, based on title and description

Description summary:

> The listing is for a room in a shared flat on Konradstrasse, near Zürich HB, with two existing flatmates looking for a longer-term new roommate from May 1.

### Full Direct Listing JSON

The JSON below comes from the direct endpoint `GET /api/v1/public-listing/85929980/`.

```json
{
  "pk": 85929980,
  "slug": "konradstrasse-52-8005-zurich",
  "url": "/en/flat/konradstrasse-52-8005-zurich/85929980/",
  "short_url": "/85929980/",
  "submit_url": "/en/listing/85929980/submit/",
  "status": "act",
  "created": "2026-04-04T12:08:38.446320+02:00",
  "offer_type": "RENT",
  "object_category": "APARTMENT",
  "object_type": "APARTMENT",
  "reference": "",
  "ref_property": "",
  "ref_house": "",
  "ref_object": "",
  "alternative_reference": null,
  "price_display": 1690,
  "price_display_type": "TOTAL",
  "price_unit": "monthly",
  "published": "2026-04-04T12:08:38.519874+02:00",
  "rent_net": null,
  "rent_charges": null,
  "rent_gross": 1690,
  "short_title": "3 ½ rooms apartment",
  "public_title": "Konradstrasse 52, 8005 Zürich - CHF 1’690 incl. utilities per month",
  "pitch_title": "Rent a 3 ½ rooms apartment in Zürich",
  "description_title": "Zimmer in WG / Room in Shared Flat",
  "description": "DE:  \n  \nWir sind Maximilian (28) und Lukas (34) und suchen per 1.5. eine:n neue:n Mitbewohner:in in der wunderbar renovierten 3.5-Zimmer Wohnung an der Konradstrasse, nur 5min entfernt vom Hauptbahnhof.  \n  \nWir suchen eine Person, die bereit ist längerfristig in der WG zu wohnen, die auch gerne Sachen unternimmt, beim Tatort-Schauen am Sonntagabend dabei ist, und generell daran interessiert ist, was so beieinander läuft. Natürlich schätzen wir aber genauso unsere Privatsphäre, was auch bei der Raumaufteilung super funktioniert in der Wohnung.  \n  \nWir sind ein Architekt (Maxi) und ein Marketing Manager (Luki) bei einer grossen Kunstgalerie und nebenbei noch Spinning-Instructor – wir wünschen uns jemanden der genauso gerne mal über Kunst, Design, Architektur und Sport spricht oder mal in diesem Kontext etwas unternimmt. Wichtig ist uns auch, dass du LGBTQIA friendly bist.  \n  \nUnsere WG ist sehr ordentlich und würden uns wünschen, dass du deinen Teil im gemeinschaftlichen Ämtliplan beiträgst.  \n  \nWenn du Interesse hast, freuen wir uns über ein paar Zeilen zu dir: Wer bist du, was machst du und wie dein Leben aktuell so aussieht.  \n  \nDie Wohnung ist leider nicht rollstuhlgängig.  \n––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––  \n  \nEN:  \n  \nWe are Maximilian and Lukas and are looking for a new flatmate starting May 1st for our newly renovated 3.5-room apartment on Konradstrasse – just 5 minutes from the main station.  \n  \nWe’re looking for someone who’s interested in staying longer-term, enjoys doing things together from time to time, or joining for a Tatort evening on Sundays. At the same time, we really value our privacy – which works well thanks to the layout of the apartment.  \n  \nAbout us: Maxi is an architect, and Lukas works in marketing for a major art gallery and is also a spinning instructor. We often find ourselves talking about art, design, architecture, and sports – so it would be great if you share some of these interests.  \n  \nIt’s important to us to have a respectful and open living environment – being LGBTQIA friendly is a must.  \n  \nWe also keep the flat tidy and expect everyone to contribute to shared chores.  \n  \nIf you’re interested, we’d love to hear a few lines about you: who you are, what you do, and what your life currently looks like.  \n  \nPlease note that the apartment is not wheelchair accessible.",
  "surface_living": null,
  "surface_property": null,
  "surface_usable": null,
  "surface_usable_minimum": null,
  "volume": null,
  "space_display": null,
  "number_of_rooms": "3.5",
  "floor": -3,
  "attributes": [
    {
      "name": "dishwasher"
    },
    {
      "name": "tumbler"
    },
    {
      "name": "washingmachine"
    }
  ],
  "is_furnished": false,
  "is_temporary": false,
  "is_selling_furniture": false,
  "is_swap": false,
  "street": "Konradstrasse 52",
  "zipcode": 8005,
  "city": "Zürich",
  "public_address": "Konradstrasse 52, 8005 Zürich",
  "latitude": 47.38136427,
  "longitude": 8.534814599999999,
  "year_built": null,
  "year_renovated": null,
  "moving_date_type": "dat",
  "moving_date": "2026-05-01",
  "video_url": "",
  "tour_url": "",
  "website_url": "",
  "live_viewing_url": "",
  "cover_image": 34950402,
  "images": [
    34950402,
    34950405,
    34950401,
    34950403,
    34950404
  ],
  "documents": [],
  "agency": {
    "name": null,
    "name_2": null,
    "street": null,
    "zipcode": null,
    "city": null,
    "country": null,
    "logo": null
  },
  "reserved": false,
  "state": null,
  "country": "CH",
  "smg_id": "",
  "flatfox_priority_exclusive_until": "2026-04-11T23:59:59+02:00",
  "rent_title": "Rent a 3 ½ rooms apartment in Zürich",
  "livingspace": null,
  "can_direct_apply": false
}
```

## Consistency Check

For this report, I explicitly did not use `GET /api/v1/public-listing/?pk=...` as the source of truth for sample details.

On `2026-04-05`, Flatfox returned mismatched values between:

- `GET /api/v1/public-listing/<pk>/`
- `GET /api/v1/public-listing/?limit=0&expand=cover_image&pk=<pk>`

for the same listing ids.

The mismatch affected fields like:

- `price_display`
- `public_title`
- `surface_living`
- `number_of_rooms`

Repeated calls to the direct endpoint were stable, so the direct endpoint is the one to use for final details.

## Local Reproduction

This repo already contains Flatfox helpers at [`src/homegate_triage_assistant/flatfox.py`](/Users/mert/dev/personal/zurich-home-search/src/homegate_triage_assistant/flatfox.py).

To reproduce this count safely, use `pin` for discovery and the direct endpoint for the in-band listings:

```bash
python3 - <<'PY'
import json
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

BBOX = {'west':'8.45','south':'47.30','east':'8.65','north':'47.45'}
MAX_COUNT = 1000

def fetch_json(url):
    req = urllib.request.Request(url, headers={'User-Agent':'zurich-home-search flatfox-audit/1.0','Accept':'application/json'})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)

def fetch_pin_page(box):
    params = dict(box)
    params.update({'max_count':str(MAX_COUNT),'offer_type':'RENT','object_category':'APARTMENT'})
    return fetch_json('https://flatfox.ch/api/v1/pin/?' + urllib.parse.urlencode(params))

pins = fetch_pin_page(BBOX)
band_pks = [
    pin['pk']
    for pin in pins
    if pin.get('price_unit') == 'monthly'
    and pin.get('price_display_type') == 'TOTAL'
    and isinstance(pin.get('price_display'), (int, float))
    and 1500 <= pin['price_display'] <= 2000
]

def fetch_direct(pk):
    return fetch_json(f'https://flatfox.ch/api/v1/public-listing/{pk}/')

details = []
with ThreadPoolExecutor(max_workers=16) as executor:
    futures = {executor.submit(fetch_direct, pk): pk for pk in band_pks}
    for future in as_completed(futures):
        details.append(future.result())

city = [item for item in details if item.get('city') in {'Zürich', 'Zurich'}]
print(len(city))
PY
```
