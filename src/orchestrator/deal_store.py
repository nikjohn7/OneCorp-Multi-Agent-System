"""SQLite persistence layer for deals (Orchestrator).

This module provides a minimal, deterministic persistence API for the
orchestrator state machine. It stores deals, contract versions, audit events,
and SLA deadlines using Python's standard library `sqlite3`.

Design goals:
- Generalizable schema (no demo hardcoding).
- Simple upsert/read/query methods for orchestrator + tests.
- JSON storage for flexible deal/contract metadata.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from src.orchestrator.state_machine import (
    ContractRecord,
    Deal,
    DealEvent,
    DealState,
)


class DealStoreError(Exception):
    """Raised when persistence operations fail."""


def _coerce_dt(value: Any) -> Optional[datetime]:
    """Coerce an ISO string or datetime into a tz-aware datetime."""

    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    if isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value)
        except ValueError:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    return None


def _to_iso(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    coerced = _coerce_dt(dt)
    return coerced.isoformat() if coerced else None


def _to_epoch(dt: Optional[datetime]) -> Optional[int]:
    if dt is None:
        return None
    coerced = _coerce_dt(dt)
    return int(coerced.timestamp()) if coerced else None


def _json_dumps(value: Any) -> str:
    return json.dumps(value if value is not None else {}, default=str)


def _json_loads(text: Optional[str], default: Any) -> Any:
    if not text:
        return default
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return default


class DealStore:
    """SQLite-backed store for deals."""

    def __init__(self, db_path: Union[str, Path] = "deals.db") -> None:
        self.db_path = str(db_path)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self._init_schema()

    def close(self) -> None:
        """Close the underlying SQLite connection."""

        try:
            self.conn.close()
        except sqlite3.Error as e:
            raise DealStoreError(str(e)) from e

    def __enter__(self) -> "DealStore":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _init_schema(self) -> None:
        """Create tables if they do not exist."""

        try:
            cur = self.conn.cursor()
            cur.executescript(
                """
                CREATE TABLE IF NOT EXISTS deals (
                    deal_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    canonical_json TEXT NOT NULL,
                    current_version INTEGER NOT NULL DEFAULT 0,
                    solicitor_email TEXT,
                    solicitor_appointment TEXT,
                    solicitor_appointment_ts INTEGER,
                    sla_deadline TEXT,
                    sla_deadline_ts INTEGER,
                    vendor_email TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS contracts (
                    deal_id TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    filename TEXT,
                    status TEXT NOT NULL,
                    received_at TEXT NOT NULL,
                    validated_at TEXT,
                    is_valid INTEGER,
                    mismatches_json TEXT NOT NULL,
                    risk_score TEXT,
                    PRIMARY KEY (deal_id, version),
                    FOREIGN KEY (deal_id) REFERENCES deals(deal_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    deal_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    source TEXT NOT NULL,
                    old_state TEXT,
                    new_state TEXT,
                    metadata_json TEXT NOT NULL,
                    success INTEGER NOT NULL,
                    reason TEXT,
                    UNIQUE (deal_id, event_type, timestamp, source),
                    FOREIGN KEY (deal_id) REFERENCES deals(deal_id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_events_deal_id ON events(deal_id);
                CREATE INDEX IF NOT EXISTS idx_deals_sla_ts ON deals(sla_deadline_ts);
                """
            )
            self.conn.commit()
        except sqlite3.Error as e:
            raise DealStoreError(f"Failed to initialize schema: {e}") from e

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def upsert_deal(self, deal: Deal, persist_events: bool = True) -> None:
        """Insert or update a deal and its contracts.

        Args:
            deal: Deal object to persist.
            persist_events: If True, insert deal.events (idempotent).
        """

        try:
            cur = self.conn.cursor()
            cur.execute(
                """
                INSERT INTO deals (
                    deal_id, status, canonical_json, current_version,
                    solicitor_email, solicitor_appointment, solicitor_appointment_ts,
                    sla_deadline, sla_deadline_ts,
                    vendor_email, created_at, updated_at
                ) VALUES (
                    :deal_id, :status, :canonical_json, :current_version,
                    :solicitor_email, :solicitor_appointment, :solicitor_appointment_ts,
                    :sla_deadline, :sla_deadline_ts,
                    :vendor_email, :created_at, :updated_at
                )
                ON CONFLICT(deal_id) DO UPDATE SET
                    status=excluded.status,
                    canonical_json=excluded.canonical_json,
                    current_version=excluded.current_version,
                    solicitor_email=excluded.solicitor_email,
                    solicitor_appointment=excluded.solicitor_appointment,
                    solicitor_appointment_ts=excluded.solicitor_appointment_ts,
                    sla_deadline=excluded.sla_deadline,
                    sla_deadline_ts=excluded.sla_deadline_ts,
                    vendor_email=excluded.vendor_email,
                    updated_at=excluded.updated_at
                """,
                {
                    "deal_id": deal.deal_id,
                    "status": deal.status.value,
                    "canonical_json": _json_dumps(deal.canonical),
                    "current_version": int(deal.current_version or 0),
                    "solicitor_email": deal.solicitor_email,
                    "solicitor_appointment": _to_iso(deal.solicitor_appointment),
                    "solicitor_appointment_ts": _to_epoch(deal.solicitor_appointment),
                    "sla_deadline": _to_iso(deal.sla_deadline),
                    "sla_deadline_ts": _to_epoch(deal.sla_deadline),
                    "vendor_email": deal.vendor_email,
                    "created_at": _to_iso(deal.created_at) or datetime.now(timezone.utc).isoformat(),
                    "updated_at": _to_iso(deal.updated_at) or datetime.now(timezone.utc).isoformat(),
                },
            )

            for record in deal.contracts.values():
                self._upsert_contract(cur, deal.deal_id, record)

            if persist_events:
                for ev in deal.events:
                    self._insert_event(cur, deal.deal_id, ev)

            self.conn.commit()
        except sqlite3.Error as e:
            self.conn.rollback()
            raise DealStoreError(f"Failed to upsert deal {deal.deal_id}: {e}") from e

    def record_event(self, deal_id: str, event: Union[DealEvent, Dict[str, Any]]) -> None:
        """Persist a single event for a deal."""

        if isinstance(event, dict):
            event = DealEvent(
                event_type=str(event.get("event_type", "")),
                timestamp=_coerce_dt(event.get("timestamp")) or datetime.now(timezone.utc),
                source=str(event.get("source", "system")),
                old_state=event.get("old_state"),
                new_state=event.get("new_state"),
                metadata=event.get("metadata") or {},
                success=bool(event.get("success", True)),
                reason=event.get("reason"),
            )

        try:
            cur = self.conn.cursor()
            self._insert_event(cur, deal_id, event)
            self.conn.commit()
        except sqlite3.Error as e:
            self.conn.rollback()
            raise DealStoreError(f"Failed to record event for {deal_id}: {e}") from e

    def update_state(
        self,
        deal_id: str,
        new_state: Union[DealState, str],
        updated_at: Optional[datetime] = None,
    ) -> None:
        """Update a deal's state."""

        state_value = new_state.value if isinstance(new_state, DealState) else str(new_state)
        ts = _to_iso(updated_at) or datetime.now(timezone.utc).isoformat()

        try:
            cur = self.conn.cursor()
            cur.execute(
                "UPDATE deals SET status=?, updated_at=? WHERE deal_id=?",
                (state_value, ts, deal_id),
            )
            if cur.rowcount == 0:
                raise DealStoreError(f"Deal not found: {deal_id}")
            self.conn.commit()
        except sqlite3.Error as e:
            self.conn.rollback()
            raise DealStoreError(f"Failed to update state for {deal_id}: {e}") from e

    def get_deal(self, deal_id: str, include_events: bool = True) -> Optional[Deal]:
        """Retrieve a deal (with contracts and optionally events)."""

        cur = self.conn.cursor()
        row = cur.execute(
            "SELECT * FROM deals WHERE deal_id=?",
            (deal_id,),
        ).fetchone()

        if row is None:
            return None

        try:
            status = DealState(row["status"])
        except ValueError as e:
            raise DealStoreError(f"Unknown deal state: {row['status']}") from e

        deal = Deal(
            deal_id=row["deal_id"],
            status=status,
            canonical=_json_loads(row["canonical_json"], {}),
            current_version=int(row["current_version"] or 0),
            solicitor_email=row["solicitor_email"],
            solicitor_appointment=_coerce_dt(row["solicitor_appointment"]),
            sla_deadline=_coerce_dt(row["sla_deadline"]),
            vendor_email=row["vendor_email"],
            created_at=_coerce_dt(row["created_at"]) or datetime.now(timezone.utc),
            updated_at=_coerce_dt(row["updated_at"]) or datetime.now(timezone.utc),
        )

        # Contracts
        contract_rows = cur.execute(
            "SELECT * FROM contracts WHERE deal_id=? ORDER BY version ASC",
            (deal_id,),
        ).fetchall()
        for c in contract_rows:
            mismatches = _json_loads(c["mismatches_json"], [])
            record = ContractRecord(
                version=int(c["version"]),
                filename=str(c["filename"] or ""),
                status=str(c["status"]),
                received_at=_coerce_dt(c["received_at"]) or datetime.now(timezone.utc),
                validated_at=_coerce_dt(c["validated_at"]),
                is_valid=None if c["is_valid"] is None else bool(int(c["is_valid"])),
                mismatches=mismatches if isinstance(mismatches, list) else [],
                risk_score=c["risk_score"],
            )
            deal.contracts[record.version] = record

        # Events
        if include_events:
            event_rows = cur.execute(
                "SELECT * FROM events WHERE deal_id=? ORDER BY timestamp ASC, event_id ASC",
                (deal_id,),
            ).fetchall()
            for e in event_rows:
                metadata = _json_loads(e["metadata_json"], {})
                deal.events.append(
                    DealEvent(
                        event_type=str(e["event_type"]),
                        timestamp=_coerce_dt(e["timestamp"]) or datetime.now(timezone.utc),
                        source=str(e["source"]),
                        old_state=e["old_state"],
                        new_state=e["new_state"],
                        metadata=metadata if isinstance(metadata, dict) else {},
                        success=bool(int(e["success"])),
                        reason=e["reason"],
                    )
                )

        return deal

    def get_pending_sla_checks(self, now: datetime) -> List[Tuple[str, datetime]]:
        """Return deals whose SLA deadline is due.

        Args:
            now: Reference time for pending checks.

        Returns:
            List of (deal_id, sla_deadline) for deals needing SLA evaluation.
        """

        now_dt = _coerce_dt(now) or datetime.now(timezone.utc)
        now_ts = int(now_dt.timestamp())

        pending_states = (
            DealState.DOCUSIGN_RELEASED.value,
            DealState.DOCUSIGN_RELEASE_REQUESTED.value,
        )

        rows = self.conn.execute(
            """
            SELECT deal_id, sla_deadline
            FROM deals
            WHERE sla_deadline_ts IS NOT NULL
              AND sla_deadline_ts <= ?
              AND status IN (?, ?)
            ORDER BY sla_deadline_ts ASC
            """,
            (now_ts, *pending_states),
        ).fetchall()

        results: List[Tuple[str, datetime]] = []
        for r in rows:
            deadline = _coerce_dt(r["sla_deadline"])
            if deadline:
                results.append((str(r["deal_id"]), deadline))
        return results

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _upsert_contract(self, cur: sqlite3.Cursor, deal_id: str, record: ContractRecord) -> None:
        cur.execute(
            """
            INSERT INTO contracts (
                deal_id, version, filename, status, received_at, validated_at,
                is_valid, mismatches_json, risk_score
            ) VALUES (
                :deal_id, :version, :filename, :status, :received_at, :validated_at,
                :is_valid, :mismatches_json, :risk_score
            )
            ON CONFLICT(deal_id, version) DO UPDATE SET
                filename=excluded.filename,
                status=excluded.status,
                received_at=excluded.received_at,
                validated_at=excluded.validated_at,
                is_valid=excluded.is_valid,
                mismatches_json=excluded.mismatches_json,
                risk_score=excluded.risk_score
            """,
            {
                "deal_id": deal_id,
                "version": int(record.version),
                "filename": record.filename,
                "status": record.status,
                "received_at": _to_iso(record.received_at) or datetime.now(timezone.utc).isoformat(),
                "validated_at": _to_iso(record.validated_at),
                "is_valid": None
                if record.is_valid is None
                else (1 if bool(record.is_valid) else 0),
                "mismatches_json": _json_dumps(record.mismatches),
                "risk_score": record.risk_score,
            },
        )

    def _insert_event(self, cur: sqlite3.Cursor, deal_id: str, event: DealEvent) -> None:
        cur.execute(
            """
            INSERT OR IGNORE INTO events (
                deal_id, event_type, timestamp, source, old_state, new_state,
                metadata_json, success, reason
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                deal_id,
                event.event_type,
                _to_iso(event.timestamp) or datetime.now(timezone.utc).isoformat(),
                event.source,
                event.old_state,
                event.new_state,
                _json_dumps(event.metadata),
                1 if event.success else 0,
                event.reason,
            ),
        )
