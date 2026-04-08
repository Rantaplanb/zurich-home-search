from __future__ import annotations

from contextlib import asynccontextmanager

from jinja2 import Template
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from .service import Poller, TriageService


INBOX_TEMPLATE = Template(
    """
    <!doctype html>
    <html lang="en">
      <head>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <title>Homegate Triage Assistant</title>
        <style>
          :root {
            color-scheme: light;
            --bg: #f5f1e8;
            --card: #fffdf8;
            --ink: #20201c;
            --muted: #6a665c;
            --line: #d9d1c2;
            --accent: #0d5c63;
            --warn: #c97b2c;
            --good: #24713e;
            --bad: #a63939;
          }
          body {
            margin: 0;
            font-family: "Iowan Old Style", "Palatino Linotype", serif;
            background: radial-gradient(circle at top, #fff9ef 0%, var(--bg) 55%, #e6dfd1 100%);
            color: var(--ink);
          }
          main {
            max-width: 1180px;
            margin: 0 auto;
            padding: 32px 18px 64px;
          }
          h1 {
            margin: 0;
            font-size: 2.2rem;
          }
          .toolbar {
            display: flex;
            justify-content: space-between;
            gap: 12px;
            align-items: center;
            margin: 20px 0 28px;
            flex-wrap: wrap;
          }
          .meta {
            color: var(--muted);
          }
          .button, button {
            border: 1px solid var(--ink);
            background: var(--card);
            color: var(--ink);
            padding: 8px 12px;
            font: inherit;
            cursor: pointer;
          }
          .items {
            display: grid;
            gap: 18px;
          }
          .item {
            background: rgba(255, 253, 248, 0.96);
            border: 1px solid var(--line);
            padding: 18px;
            box-shadow: 0 12px 24px rgba(58, 46, 18, 0.06);
          }
          .topline {
            display: flex;
            justify-content: space-between;
            gap: 12px;
            align-items: start;
            flex-wrap: wrap;
          }
          .triage {
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.04em;
          }
          .triage.contact_candidate { color: var(--good); }
          .triage.inspect { color: var(--warn); }
          .triage.ignore { color: var(--bad); }
          .facts, .summary, .missing, .factors {
            margin-top: 12px;
            color: var(--muted);
          }
          .summary div {
            color: var(--ink);
          }
          .actions {
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
            align-items: center;
            margin-top: 16px;
          }
          .actions input[type="text"] {
            flex: 1;
            min-width: 200px;
            padding: 8px 10px;
            border: 1px solid var(--line);
            background: white;
            font: inherit;
          }
          .factor-grid {
            display: grid;
            gap: 8px;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            margin-top: 10px;
          }
          .factor {
            border-top: 1px solid var(--line);
            padding-top: 8px;
          }
          a {
            color: var(--accent);
          }
        </style>
      </head>
      <body>
        <main>
          <h1>Homegate Triage Assistant</h1>
          <div class="toolbar">
            <div class="meta">
              <div>{{ items|length }} listing{{ '' if items|length == 1 else 's' }}</div>
              <div>Local-first inbox for inspect / ignore / contact.</div>
            </div>
            <form action="/triage-once" method="post">
              <button type="submit">Run Triage Once</button>
            </form>
          </div>

          <section class="items">
            {% for item in items %}
              <article class="item">
                <div class="topline">
                  <div>
                    <h2 style="margin:0 0 6px 0; font-size:1.35rem;">{{ item.listing.title or item.listing.url }}</h2>
                    <div class="meta">
                      {{ item.listing.address or 'Address unknown' }}
                      {% if item.listing.total_cost_chf %} · CHF {{ '%.0f'|format(item.listing.total_cost_chf) }}{% endif %}
                      {% if item.listing.living_space_sqm %} · {{ '%.0f'|format(item.listing.living_space_sqm) }} sqm{% endif %}
                    </div>
                  </div>
                  <div style="text-align:right;">
                    <div class="triage {{ item.evaluation.triage_decision if item.evaluation else 'inspect' }}">
                      {{ item.evaluation.triage_decision if item.evaluation else 'pending' }}
                    </div>
                    <div>{{ '%.2f'|format(item.evaluation.total_score) if item.evaluation else 'n/a' }} / 10</div>
                    <div class="meta">
                      Judge: {{ item.evaluation.judge_opinion if item.evaluation else 'n/a' }}
                      {% if item.evaluation %} · confidence {{ '%.2f'|format(item.evaluation.confidence) }}{% endif %}
                    </div>
                  </div>
                </div>

                <div class="summary">
                  {% if item.evaluation %}
                    {% for line in item.evaluation.summary_lines %}
                      <div>{{ line }}</div>
                    {% endfor %}
                  {% else %}
                    <div>Awaiting evaluation.</div>
                  {% endif %}
                </div>

                <div class="facts">
                  Extraction: {{ item.listing.extraction_status }}
                  {% if item.listing.office_commute_minutes %} · Office {{ item.listing.office_commute_minutes }} min{% endif %}
                  {% if item.listing.public_transport_walk_minutes %} · PT {{ item.listing.public_transport_walk_minutes }} min{% endif %}
                  {% if item.listing.supermarket_walk_minutes %} · Supermarket {{ item.listing.supermarket_walk_minutes }} min{% endif %}
                  {% if item.listing.available_from %} · Move-in {{ item.listing.available_from }}{% endif %}
                </div>

                {% if item.evaluation %}
                  <div class="missing">
                    Missing:
                    {% if item.evaluation.missing_information %}
                      {{ item.evaluation.missing_information | map(attribute='field') | join(', ') }}
                    {% else %}
                      none
                    {% endif %}
                  </div>
                  <div class="factors">
                    <strong>Factor scores</strong>
                    <div class="factor-grid">
                      {% for name, factor in item.evaluation.factor_scores.items() %}
                        <div class="factor">
                          <div><strong>{{ name }}</strong>: {{ '%.1f'|format(factor.score) }} / 10</div>
                          <div class="meta">{{ factor.evidence }}</div>
                        </div>
                      {% endfor %}
                    </div>
                  </div>
                {% endif %}

                <div class="actions">
                  <a class="button" href="{{ item.listing.url }}" target="_blank" rel="noreferrer">Open Homegate</a>
                  <form action="/decision/{{ item.listing.id }}" method="post" style="display:flex; gap:8px; flex-wrap:wrap; width:100%;">
                    <input type="text" name="note" value="{{ item.manual_note }}" placeholder="Optional note" />
                    <button type="submit" name="state" value="inspect">Inspect</button>
                    <button type="submit" name="state" value="ignore">Ignore</button>
                    <button type="submit" name="state" value="contact">Contact</button>
                  </form>
                  {% if item.manual_state %}
                    <div class="meta">Manual state: {{ item.manual_state }}</div>
                  {% endif %}
                </div>
              </article>
            {% endfor %}
          </section>
        </main>
      </body>
    </html>
    """
)


def create_app(service: TriageService, enable_background_poller: bool = True) -> FastAPI:
    poller = Poller(service, interval_seconds=service.config.app.poll_interval_seconds)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        if enable_background_poller:
            poller.start()
        try:
            yield
        finally:
            poller.stop()

    app = FastAPI(title="Homegate Triage Assistant", lifespan=lifespan)

    @app.get("/", response_class=HTMLResponse)
    def inbox() -> HTMLResponse:
        rendered = INBOX_TEMPLATE.render(items=service.database.list_inbox_items())
        return HTMLResponse(rendered)

    @app.post("/triage-once")
    def triage_once() -> RedirectResponse:
        service.run_cycle()
        return RedirectResponse("/", status_code=303)

    @app.post("/decision/{listing_id}")
    def set_decision(listing_id: int, state: str = Form(...), note: str = Form("")) -> RedirectResponse:
        service.database.set_manual_decision(listing_id, state=state, note=note)
        return RedirectResponse("/", status_code=303)

    return app
