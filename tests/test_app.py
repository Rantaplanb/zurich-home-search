from __future__ import annotations

from datetime import date, datetime, timezone

from fastapi.testclient import TestClient

from homegate_triage_assistant.database import Database
from homegate_triage_assistant.review import create_app
from homegate_triage_assistant.schemas import ExtractedListing, LLMReview, ParsedAlert
from homegate_triage_assistant.service import TriageService


class FakeFetcher:
    def __init__(self) -> None:
        self._used = False

    def poll(self) -> list[ParsedAlert]:
        if self._used:
            return []
        self._used = True
        return [
            ParsedAlert(
                message_id="<fixture-alert@example.com>",
                sender="searchalert@homegate.ch",
                subject="Homegate alert",
                received_at=datetime.now(timezone.utc),
                raw_text="https://www.homegate.ch/rent/4003058517",
                raw_html=None,
                listing_urls=["https://www.homegate.ch/rent/4003058517"],
            )
        ]

    @staticmethod
    def build_listing_refs(alert: ParsedAlert) -> list[tuple[str, str, str | None]]:
        return [("4003058517", "https://www.homegate.ch/rent/4003058517", "Fixture listing")]


class FakeExtractor:
    def __init__(self, extracted: ExtractedListing) -> None:
        self.extracted = extracted

    def extract(self, listing):  # noqa: ANN001
        return self.extracted


class FakeJudge:
    def evaluate(self, listing: ExtractedListing) -> LLMReview:
        return LLMReview(
            vfm_score=8,
            kitchen_quality_score=8,
            condition_score=8,
            judge_opinion="positive",
            judge_rationale="Good first-pass fit.",
            confidence=0.85,
            summary_lines=[
                "Good price for Zurich.",
                "Commute is in target range.",
                "Private apartment with no WG signal.",
                "Move-in timing is aligned.",
                "Open and contact soon.",
            ],
            missing_information=[],
        )


class NoopNotifier:
    def __init__(self) -> None:
        self.calls = 0

    def notify_listing(self, listing, evaluation):  # noqa: ANN001
        self.calls += 1


def test_app_renders_listing_and_accepts_manual_decision(test_config) -> None:
    database = Database(test_config.app.database_path)
    notifier = NoopNotifier()
    service = TriageService(
        test_config,
        database=database,
        alert_fetcher=FakeFetcher(),
        extractor=FakeExtractor(
            ExtractedListing(
                homegate_id="4003058517",
                url="https://www.homegate.ch/rent/4003058517",
                title="Fixture apartment",
                address="Lerchenrain 1, 8046 Zurich",
                city="Zurich",
                total_cost_chf=1650,
                living_space_sqm=61,
                office_commute_minutes=24,
                supermarket_walk_minutes=6,
                public_transport_walk_minutes=3,
                available_from=date.today(),
                is_roommate_listing=False,
                extraction_status="success",
            )
        ),
        judge=FakeJudge(),
        notifier=notifier,
    )
    service.run_cycle()
    assert notifier.calls == 1

    app = create_app(service, enable_background_poller=False)
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    assert "Fixture apartment" in response.text
    assert "contact_candidate" in response.text

    listing_id = database.list_all_listing_ids()[0]
    post = client.post(
        f"/decision/{listing_id}",
        data={"state": "contact", "note": "Sent intro."},
        follow_redirects=False,
    )
    assert post.status_code == 303
    response = client.get("/")
    assert "Manual state: contact" in response.text
