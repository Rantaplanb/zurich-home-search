from __future__ import annotations

import threading

from .config import Config
from .database import Database
from .extract import HomegateExtractor
from .gmail import GmailAlertFetcher
from .ingest import IMAPAlertFetcher
from .llm import LLMJudge
from .notifications import NotificationService
from .schemas import ExtractedListing, ListingRecord, TriageRunSummary
from .score import ListingScorer


class TriageService:
    def __init__(
        self,
        config: Config,
        database: Database | None = None,
        alert_fetcher: IMAPAlertFetcher | GmailAlertFetcher | None = None,
        extractor: HomegateExtractor | None = None,
        judge: LLMJudge | None = None,
        notifier: NotificationService | None = None,
    ) -> None:
        self.config = config
        self.database = database or Database(config.app.database_path)
        self.alert_fetcher = alert_fetcher or _build_default_fetcher(config)
        self.extractor = extractor or HomegateExtractor(config)
        self.judge = judge or LLMJudge(config)
        self.notifier = notifier or NotificationService()
        self.scorer = ListingScorer(config, self.judge)
        self.database.init_db()

    def run_cycle(self) -> TriageRunSummary:
        summary = TriageRunSummary()
        touched_listing_ids: list[int] = []
        alerts = self.alert_fetcher.poll()
        summary.processed_alerts = len(alerts)
        for alert in alerts:
            refs = self.alert_fetcher.build_listing_refs(alert)
            listing_ids = self.database.record_alert(alert, refs)
            touched_listing_ids.extend(listing_ids)
        summary.touched_listings = len(set(touched_listing_ids))

        for listing_id in sorted(set(touched_listing_ids)):
            listing = self.database.get_listing(listing_id)
            if listing is None:
                continue
            extracted = self.extractor.extract(listing)
            self.database.update_listing_from_extraction(listing_id, extracted.model_dump(mode="json"))
            summary.extracted_listings += 1
            stored = self.database.get_listing(listing_id)
            if stored is None:
                continue
            evaluation = self.scorer.evaluate(_record_to_extracted(stored))
            self.database.save_evaluation(listing_id, evaluation)
            summary.evaluated_listings += 1
            if evaluation.triage_decision == "contact_candidate" and not self.database.has_notification(
                listing_id, self.config.notifications.channel
            ):
                self.notifier.notify_listing(stored, evaluation)
                self.database.mark_notification(listing_id, self.config.notifications.channel)
                summary.notified_listings += 1

        return summary

    def rescore_all(self) -> int:
        rescored = 0
        for listing_id in self.database.list_all_listing_ids():
            listing = self.database.get_listing(listing_id)
            if listing is None:
                continue
            evaluation = self.scorer.evaluate(_record_to_extracted(listing))
            self.database.save_evaluation(listing_id, evaluation)
            rescored += 1
        return rescored


class Poller:
    def __init__(self, service: TriageService, interval_seconds: int) -> None:
        self.service = service
        self.interval_seconds = interval_seconds
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run, name="homegate-poller", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                self.service.run_cycle()
            except Exception:
                pass
            self._stop_event.wait(self.interval_seconds)


def _record_to_extracted(record: ListingRecord) -> ExtractedListing:
    return ExtractedListing(
        homegate_id=record.homegate_id,
        url=record.url,
        title=record.title,
        address=record.address,
        postal_code=record.postal_code,
        city=record.city,
        rent_chf=record.rent_chf,
        extra_costs_chf=record.extra_costs_chf,
        total_cost_chf=record.total_cost_chf,
        rooms=record.rooms,
        living_space_sqm=record.living_space_sqm,
        available_from=record.available_from,
        last_refurbishment_year=record.last_refurbishment_year,
        year_built=record.year_built,
        listing_type=record.listing_type,
        is_roommate_listing=record.is_roommate_listing,
        public_transport_walk_minutes=record.public_transport_walk_minutes,
        public_transport_name=record.public_transport_name,
        supermarket_walk_minutes=record.supermarket_walk_minutes,
        supermarket_name=record.supermarket_name,
        office_commute_minutes=record.office_commute_minutes,
        description=record.description,
        raw_text=record.raw_text or record.source_email_excerpt,
        facts=record.facts,
        extraction_status=record.extraction_status,
        extraction_error=record.extraction_error,
    )


def _build_default_fetcher(config: Config) -> IMAPAlertFetcher | GmailAlertFetcher:
    if config.imap.is_configured:
        return IMAPAlertFetcher(config)
    if config.gmail.is_configured:
        return GmailAlertFetcher(config)
    return IMAPAlertFetcher(config)
