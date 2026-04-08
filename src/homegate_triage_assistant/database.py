from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from .schemas import EvaluationResult, InboxItem, ListingRecord, ManualDecision, ParsedAlert


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=30.0)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA busy_timeout = 30000;")
            yield connection
            connection.commit()
        finally:
            connection.close()

    def init_db(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                PRAGMA journal_mode = WAL;

                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message_id TEXT NOT NULL UNIQUE,
                    sender TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    received_at TEXT,
                    raw_text TEXT NOT NULL,
                    raw_html TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS alert_listing_refs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    alert_id INTEGER NOT NULL,
                    homegate_id TEXT NOT NULL,
                    listing_url TEXT NOT NULL,
                    UNIQUE(alert_id, homegate_id),
                    FOREIGN KEY (alert_id) REFERENCES alerts(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS listings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL,
                    homegate_id TEXT NOT NULL UNIQUE,
                    url TEXT NOT NULL,
                    title TEXT,
                    address TEXT,
                    postal_code TEXT,
                    city TEXT,
                    rent_chf REAL,
                    extra_costs_chf REAL,
                    total_cost_chf REAL,
                    rooms REAL,
                    living_space_sqm REAL,
                    available_from TEXT,
                    last_refurbishment_year INTEGER,
                    year_built INTEGER,
                    listing_type TEXT,
                    is_roommate_listing INTEGER,
                    public_transport_walk_minutes INTEGER,
                    public_transport_name TEXT,
                    supermarket_walk_minutes INTEGER,
                    supermarket_name TEXT,
                    office_commute_minutes INTEGER,
                    description TEXT,
                    raw_text TEXT,
                    facts_json TEXT NOT NULL DEFAULT '{}',
                    source_email_sender TEXT,
                    source_email_subject TEXT,
                    source_email_received_at TEXT,
                    source_email_excerpt TEXT,
                    extraction_status TEXT NOT NULL DEFAULT 'pending',
                    extraction_error TEXT,
                    first_seen_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS evaluations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    listing_id INTEGER NOT NULL UNIQUE,
                    deterministic_score REAL NOT NULL,
                    total_score REAL NOT NULL,
                    triage_decision TEXT NOT NULL,
                    judge_opinion TEXT NOT NULL,
                    judge_rationale TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    summary_lines_json TEXT NOT NULL,
                    missing_information_json TEXT NOT NULL,
                    critical_missing_fields_json TEXT NOT NULL,
                    factor_scores_json TEXT NOT NULL,
                    hard_filter_reasons_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (listing_id) REFERENCES listings(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS decisions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    listing_id INTEGER NOT NULL UNIQUE,
                    state TEXT NOT NULL,
                    note TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (listing_id) REFERENCES listings(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS notifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    listing_id INTEGER NOT NULL,
                    channel TEXT NOT NULL,
                    sent_at TEXT NOT NULL,
                    UNIQUE(listing_id, channel),
                    FOREIGN KEY (listing_id) REFERENCES listings(id) ON DELETE CASCADE
                );
                """
            )

    def record_alert(
        self,
        alert: ParsedAlert,
        listing_urls: list[tuple[str, str, str | None]],
    ) -> list[int]:
        with self.connect() as conn:
            existing = conn.execute(
                "SELECT id FROM alerts WHERE message_id = ?",
                (alert.message_id,),
            ).fetchone()
            if existing is not None:
                return []

            created_at = utc_now().isoformat()
            cursor = conn.execute(
                """
                INSERT INTO alerts (
                    message_id, sender, subject, received_at, raw_text, raw_html, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    alert.message_id,
                    alert.sender,
                    alert.subject,
                    alert.received_at.isoformat() if alert.received_at else None,
                    alert.raw_text,
                    alert.raw_html,
                    created_at,
                ),
            )
            alert_id = int(cursor.lastrowid)

            listing_ids: list[int] = []
            for homegate_id, url, excerpt in listing_urls:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO alert_listing_refs (alert_id, homegate_id, listing_url)
                    VALUES (?, ?, ?)
                    """,
                    (alert_id, homegate_id, url),
                )

                row = conn.execute(
                    "SELECT id FROM listings WHERE homegate_id = ?",
                    (homegate_id,),
                ).fetchone()
                now = utc_now().isoformat()
                if row is None:
                    result = conn.execute(
                        """
                        INSERT INTO listings (
                            source, homegate_id, url, source_email_sender, source_email_subject,
                            source_email_received_at, source_email_excerpt, extraction_status,
                            first_seen_at, last_seen_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?)
                        """,
                        (
                            "homegate",
                            homegate_id,
                            url,
                            alert.sender,
                            alert.subject,
                            alert.received_at.isoformat() if alert.received_at else None,
                            excerpt,
                            now,
                            now,
                            now,
                        ),
                    )
                    listing_ids.append(int(result.lastrowid))
                else:
                    conn.execute(
                        """
                        UPDATE listings
                        SET url = ?, source_email_sender = ?, source_email_subject = ?,
                            source_email_received_at = ?, source_email_excerpt = ?,
                            last_seen_at = ?, updated_at = ?
                        WHERE id = ?
                        """,
                        (
                            url,
                            alert.sender,
                            alert.subject,
                            alert.received_at.isoformat() if alert.received_at else None,
                            excerpt,
                            now,
                            now,
                            row["id"],
                        ),
                    )
                    listing_ids.append(int(row["id"]))

            return listing_ids

    def get_listing(self, listing_id: int) -> ListingRecord | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM listings WHERE id = ?", (listing_id,)).fetchone()
            return self._row_to_listing(row) if row else None

    def list_all_listing_ids(self) -> list[int]:
        with self.connect() as conn:
            rows = conn.execute("SELECT id FROM listings ORDER BY id").fetchall()
            return [int(row["id"]) for row in rows]

    def update_listing_from_extraction(self, listing_id: int, payload: dict[str, Any]) -> None:
        columns = {
            "title": payload.get("title"),
            "address": payload.get("address"),
            "postal_code": payload.get("postal_code"),
            "city": payload.get("city"),
            "rent_chf": payload.get("rent_chf"),
            "extra_costs_chf": payload.get("extra_costs_chf"),
            "total_cost_chf": payload.get("total_cost_chf"),
            "rooms": payload.get("rooms"),
            "living_space_sqm": payload.get("living_space_sqm"),
            "available_from": payload.get("available_from"),
            "last_refurbishment_year": payload.get("last_refurbishment_year"),
            "year_built": payload.get("year_built"),
            "listing_type": payload.get("listing_type"),
            "is_roommate_listing": payload.get("is_roommate_listing"),
            "public_transport_walk_minutes": payload.get("public_transport_walk_minutes"),
            "public_transport_name": payload.get("public_transport_name"),
            "supermarket_walk_minutes": payload.get("supermarket_walk_minutes"),
            "supermarket_name": payload.get("supermarket_name"),
            "office_commute_minutes": payload.get("office_commute_minutes"),
            "description": payload.get("description"),
            "raw_text": payload.get("raw_text"),
            "facts_json": json.dumps(payload.get("facts", {}), ensure_ascii=True, sort_keys=True),
            "extraction_status": payload.get("extraction_status"),
            "extraction_error": payload.get("extraction_error"),
            "updated_at": utc_now().isoformat(),
        }
        assignments = ", ".join(f"{column} = ?" for column in columns)
        values = [
            value.isoformat() if isinstance(value, date) else value
            for value in columns.values()
        ]
        values.append(listing_id)
        with self.connect() as conn:
            conn.execute(
                f"UPDATE listings SET {assignments} WHERE id = ?",
                values,
            )

    def save_evaluation(self, listing_id: int, evaluation: EvaluationResult) -> None:
        payload = evaluation.model_dump(mode="json")
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO evaluations (
                    listing_id, deterministic_score, total_score, triage_decision,
                    judge_opinion, judge_rationale, confidence, summary_lines_json,
                    missing_information_json, critical_missing_fields_json,
                    factor_scores_json, hard_filter_reasons_json, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(listing_id) DO UPDATE SET
                    deterministic_score = excluded.deterministic_score,
                    total_score = excluded.total_score,
                    triage_decision = excluded.triage_decision,
                    judge_opinion = excluded.judge_opinion,
                    judge_rationale = excluded.judge_rationale,
                    confidence = excluded.confidence,
                    summary_lines_json = excluded.summary_lines_json,
                    missing_information_json = excluded.missing_information_json,
                    critical_missing_fields_json = excluded.critical_missing_fields_json,
                    factor_scores_json = excluded.factor_scores_json,
                    hard_filter_reasons_json = excluded.hard_filter_reasons_json,
                    updated_at = excluded.updated_at
                """,
                (
                    listing_id,
                    payload["deterministic_score"],
                    payload["total_score"],
                    payload["triage_decision"],
                    payload["judge_opinion"],
                    payload["judge_rationale"],
                    payload["confidence"],
                    json.dumps(payload["summary_lines"], ensure_ascii=True),
                    json.dumps(payload["missing_information"], ensure_ascii=True),
                    json.dumps(payload["critical_missing_fields"], ensure_ascii=True),
                    json.dumps(payload["factor_scores"], ensure_ascii=True),
                    json.dumps(payload["hard_filter_reasons"], ensure_ascii=True),
                    utc_now().isoformat(),
                ),
            )

    def set_manual_decision(self, listing_id: int, state: ManualDecision, note: str = "") -> None:
        now = utc_now().isoformat()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO decisions (listing_id, state, note, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(listing_id) DO UPDATE SET
                    state = excluded.state,
                    note = excluded.note,
                    updated_at = excluded.updated_at
                """,
                (listing_id, state, note, now),
            )

    def list_inbox_items(self) -> list[InboxItem]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    l.*,
                    e.deterministic_score,
                    e.total_score,
                    e.triage_decision,
                    e.judge_opinion,
                    e.judge_rationale,
                    e.confidence,
                    e.summary_lines_json,
                    e.missing_information_json,
                    e.critical_missing_fields_json,
                    e.factor_scores_json,
                    e.hard_filter_reasons_json,
                    d.state AS manual_state,
                    d.note AS manual_note
                FROM listings AS l
                LEFT JOIN evaluations AS e ON e.listing_id = l.id
                LEFT JOIN decisions AS d ON d.listing_id = l.id
                ORDER BY l.first_seen_at DESC, l.id DESC
                """
            ).fetchall()

        items: list[InboxItem] = []
        for row in rows:
            evaluation = None
            if row["triage_decision"] is not None:
                evaluation = EvaluationResult.model_validate(
                    {
                        "deterministic_score": row["deterministic_score"],
                        "total_score": row["total_score"],
                        "triage_decision": row["triage_decision"],
                        "judge_opinion": row["judge_opinion"],
                        "judge_rationale": row["judge_rationale"],
                        "confidence": row["confidence"],
                        "summary_lines": json.loads(row["summary_lines_json"]),
                        "missing_information": json.loads(row["missing_information_json"]),
                        "critical_missing_fields": json.loads(row["critical_missing_fields_json"]),
                        "factor_scores": json.loads(row["factor_scores_json"]),
                        "hard_filter_reasons": json.loads(row["hard_filter_reasons_json"]),
                    }
                )
            items.append(
                InboxItem(
                    listing=self._row_to_listing(row),
                    evaluation=evaluation,
                    manual_state=row["manual_state"],
                    manual_note=row["manual_note"] or "",
                )
            )
        return items

    def has_notification(self, listing_id: int, channel: str) -> bool:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM notifications WHERE listing_id = ? AND channel = ?",
                (listing_id, channel),
            ).fetchone()
            return row is not None

    def mark_notification(self, listing_id: int, channel: str) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO notifications (listing_id, channel, sent_at)
                VALUES (?, ?, ?)
                """,
                (listing_id, channel, utc_now().isoformat()),
            )

    @staticmethod
    def _row_to_listing(row: sqlite3.Row) -> ListingRecord:
        def parse_datetime(value: str | None) -> datetime | None:
            return datetime.fromisoformat(value) if value else None

        def parse_date(value: str | None) -> date | None:
            return date.fromisoformat(value) if value else None

        return ListingRecord(
            id=int(row["id"]),
            source=str(row["source"]),
            homegate_id=str(row["homegate_id"]),
            url=str(row["url"]),
            title=row["title"],
            address=row["address"],
            postal_code=row["postal_code"],
            city=row["city"],
            rent_chf=row["rent_chf"],
            extra_costs_chf=row["extra_costs_chf"],
            total_cost_chf=row["total_cost_chf"],
            rooms=row["rooms"],
            living_space_sqm=row["living_space_sqm"],
            available_from=parse_date(row["available_from"]),
            last_refurbishment_year=row["last_refurbishment_year"],
            year_built=row["year_built"],
            listing_type=row["listing_type"],
            is_roommate_listing=(
                None if row["is_roommate_listing"] is None else bool(row["is_roommate_listing"])
            ),
            public_transport_walk_minutes=row["public_transport_walk_minutes"],
            public_transport_name=row["public_transport_name"],
            supermarket_walk_minutes=row["supermarket_walk_minutes"],
            supermarket_name=row["supermarket_name"],
            office_commute_minutes=row["office_commute_minutes"],
            description=row["description"],
            raw_text=row["raw_text"],
            facts=json.loads(row["facts_json"] or "{}"),
            source_email_sender=row["source_email_sender"],
            source_email_subject=row["source_email_subject"],
            source_email_received_at=parse_datetime(row["source_email_received_at"]),
            source_email_excerpt=row["source_email_excerpt"],
            extraction_status=row["extraction_status"],
            extraction_error=row["extraction_error"],
            first_seen_at=parse_datetime(row["first_seen_at"]) or utc_now(),
            last_seen_at=parse_datetime(row["last_seen_at"]) or utc_now(),
            updated_at=parse_datetime(row["updated_at"]) or utc_now(),
        )
