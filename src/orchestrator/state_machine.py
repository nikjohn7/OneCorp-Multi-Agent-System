"""Deterministic deal workflow state machine (Orchestrator).

This module defines:
- A DealState enum covering the demo workflow and extensible states.
- Event-driven transition rules with guard conditions.
- Lightweight in-memory deal/contract records and audit trail.

The logic is generalizable and pattern-based. It must not contain any
hardcoded demo data values, and it must not read ground-truth fixtures
at runtime.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class DealState(Enum):
    """All supported deal states.

    Versioned contract states (e.g., CONTRACT_V1_RECEIVED) are included
    to match the demo fixtures, but the state machine logic is not limited
    to these versions.
    """

    # Initial / waiting
    EOI_RECEIVED = "EOI_RECEIVED"
    AWAITING_FIRST_CONTRACT = "AWAITING_FIRST_CONTRACT"

    # Generic contract stages
    CONTRACT_RECEIVED = "CONTRACT_RECEIVED"
    CONTRACT_VALIDATED_OK = "CONTRACT_VALIDATED_OK"
    CONTRACT_HAS_DISCREPANCIES = "CONTRACT_HAS_DISCREPANCIES"

    # Demo versioned contract stages (aliases)
    CONTRACT_V1_RECEIVED = "CONTRACT_V1_RECEIVED"
    CONTRACT_V1_VALIDATED_OK = "CONTRACT_V1_VALIDATED_OK"
    CONTRACT_V1_HAS_DISCREPANCIES = "CONTRACT_V1_HAS_DISCREPANCIES"
    CONTRACT_V2_RECEIVED = "CONTRACT_V2_RECEIVED"
    CONTRACT_V2_VALIDATED_OK = "CONTRACT_V2_VALIDATED_OK"
    CONTRACT_V2_HAS_DISCREPANCIES = "CONTRACT_V2_HAS_DISCREPANCIES"

    # Amendment cycle
    AMENDMENT_REQUESTED = "AMENDMENT_REQUESTED"
    AWAITING_AMENDED_CONTRACT = "AWAITING_AMENDED_CONTRACT"

    # Solicitor / DocuSign
    SENT_TO_SOLICITOR = "SENT_TO_SOLICITOR"
    SOLICITOR_APPROVED = "SOLICITOR_APPROVED"
    DOCUSIGN_RELEASE_REQUESTED = "DOCUSIGN_RELEASE_REQUESTED"
    DOCUSIGN_RELEASED = "DOCUSIGN_RELEASED"
    BUYER_SIGNED = "BUYER_SIGNED"
    EXECUTED = "EXECUTED"

    # Alerts / terminal
    SLA_OVERDUE_ALERT_SENT = "SLA_OVERDUE_ALERT_SENT"
    HUMAN_REVIEW_REQUIRED = "HUMAN_REVIEW_REQUIRED"


CONTRACT_STATE_RE = re.compile(
    r"^CONTRACT_V(?P<version>\d+)_(?P<stage>RECEIVED|VALIDATED_OK|HAS_DISCREPANCIES)$"
)


@dataclass
class DealEvent:
    """Audit trail event for a deal."""

    event_type: str
    timestamp: datetime
    source: str
    old_state: Optional[str]
    new_state: Optional[str]
    metadata: Dict[str, Any] = field(default_factory=dict)
    success: bool = True
    reason: Optional[str] = None


@dataclass
class ContractRecord:
    """A tracked contract version."""

    version: int
    filename: str
    status: str  # RECEIVED, VALIDATED_OK, HAS_DISCREPANCIES, SUPERSEDED, EXECUTED
    received_at: datetime
    validated_at: Optional[datetime] = None
    is_valid: Optional[bool] = None
    mismatches: List[Dict[str, Any]] = field(default_factory=list)
    risk_score: Optional[str] = None


@dataclass
class Deal:
    """In-memory representation of a deal."""

    deal_id: str
    status: DealState = DealState.EOI_RECEIVED

    # Canonical EOI fields (source of truth)
    canonical: Dict[str, Any] = field(default_factory=dict)

    # Contract tracking
    contracts: Dict[int, ContractRecord] = field(default_factory=dict)
    current_version: int = 0

    # Solicitor appointment / SLA
    solicitor_email: Optional[str] = None
    solicitor_appointment: Optional[datetime] = None
    sla_deadline: Optional[datetime] = None

    # Vendor
    vendor_email: Optional[str] = None

    # Audit trail
    events: List[DealEvent] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


def generate_deal_id(lot_number: str, property_address: str) -> str:
    """Generate a generalizable deal ID from lot + address."""

    address_slug = re.sub(r"[^A-Za-z0-9]+", "_", property_address).upper().strip("_")
    lot_digits = re.sub(r"\D+", "", lot_number)
    return f"LOT{lot_digits}_{address_slug}"


# Map of base-state transitions. Versioned states are resolved dynamically.
BASE_TRANSITIONS: Dict[DealState, Dict[str, DealState]] = {
    DealState.EOI_RECEIVED: {
        "EOI_SIGNED": DealState.EOI_RECEIVED,
        "CONTRACT_FROM_VENDOR": DealState.CONTRACT_RECEIVED,
    },
    DealState.AWAITING_FIRST_CONTRACT: {
        "EOI_SIGNED": DealState.EOI_RECEIVED,
        "CONTRACT_FROM_VENDOR": DealState.CONTRACT_RECEIVED,
    },
    DealState.CONTRACT_RECEIVED: {
        "VALIDATION_PASSED": DealState.CONTRACT_VALIDATED_OK,
        "VALIDATION_FAILED": DealState.CONTRACT_HAS_DISCREPANCIES,
        "HUMAN_REVIEW_NEEDED": DealState.HUMAN_REVIEW_REQUIRED,
        "CONTRACT_FROM_VENDOR": DealState.CONTRACT_RECEIVED,  # new version
    },
    DealState.CONTRACT_HAS_DISCREPANCIES: {
        "DISCREPANCY_ALERT_SENT": DealState.AMENDMENT_REQUESTED,
        "CONTRACT_FROM_VENDOR": DealState.CONTRACT_RECEIVED,  # amended version
    },
    DealState.AMENDMENT_REQUESTED: {
        "AUTO": DealState.AWAITING_AMENDED_CONTRACT,
        "CONTRACT_FROM_VENDOR": DealState.CONTRACT_RECEIVED,
    },
    DealState.AWAITING_AMENDED_CONTRACT: {
        "CONTRACT_FROM_VENDOR": DealState.CONTRACT_RECEIVED,
    },
    DealState.CONTRACT_VALIDATED_OK: {
        "SOLICITOR_EMAIL_SENT": DealState.SENT_TO_SOLICITOR,
        "CONTRACT_FROM_VENDOR": DealState.CONTRACT_RECEIVED,  # higher version arrives
    },
    DealState.SENT_TO_SOLICITOR: {
        "SOLICITOR_APPROVED_WITH_APPOINTMENT": DealState.SOLICITOR_APPROVED,
    },
    DealState.SOLICITOR_APPROVED: {
        "DOCUSIGN_RELEASE_REQUESTED": DealState.DOCUSIGN_RELEASE_REQUESTED,
    },
    DealState.DOCUSIGN_RELEASE_REQUESTED: {
        "DOCUSIGN_RELEASED": DealState.DOCUSIGN_RELEASED,
        "SLA_OVERDUE": DealState.SLA_OVERDUE_ALERT_SENT,
    },
    DealState.DOCUSIGN_RELEASED: {
        "DOCUSIGN_BUYER_SIGNED": DealState.BUYER_SIGNED,
        "SLA_OVERDUE": DealState.SLA_OVERDUE_ALERT_SENT,
    },
    DealState.SLA_OVERDUE_ALERT_SENT: {
        "DOCUSIGN_BUYER_SIGNED": DealState.BUYER_SIGNED,
    },
    DealState.BUYER_SIGNED: {
        "DOCUSIGN_EXECUTED": DealState.EXECUTED,
    },
    DealState.EXECUTED: {},
    DealState.HUMAN_REVIEW_REQUIRED: {},
}


# Alias external/output event names to internal transition events.
EVENT_ALIASES: Dict[str, str] = {
    "CONTRACT_TO_SOLICITOR": "SOLICITOR_EMAIL_SENT",
    "DISCREPANCY_ALERT": "DISCREPANCY_ALERT_SENT",
}


class InvalidTransitionError(Exception):
    """Raised when an invalid transition is attempted."""


class StateMachine:
    """Event-driven state machine for a single deal."""

    def __init__(
        self,
        deal_id: str,
        initial_state: DealState = DealState.EOI_RECEIVED,
        canonical: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.deal = Deal(deal_id=deal_id, status=initial_state, canonical=canonical or {})

    # ---------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------

    @property
    def current_state(self) -> DealState:
        return self.deal.status

    @property
    def current_version(self) -> int:
        return self.deal.current_version

    def can_transition(self, event: str) -> bool:
        """Return True if event is allowed from current state."""

        normalized = self._normalize_event(event)
        base_state, _ = self._parse_contract_state(self.current_state)
        return normalized in BASE_TRANSITIONS.get(base_state, {})

    def get_allowed_events(self) -> List[str]:
        """List allowed events from current state (internal names)."""

        base_state, _ = self._parse_contract_state(self.current_state)
        return list(BASE_TRANSITIONS.get(base_state, {}).keys())

    def transition(
        self,
        event: str,
        source: str = "system",
        timestamp: Optional[datetime] = None,
        **context: Any,
    ) -> bool:
        """Attempt a transition based on an event.

        Args:
            event: Event type string (router or internal).
            source: Event source identifier (email_id, "system", etc.).
            timestamp: Event time. Defaults to current UTC time.
            context: Optional event-specific metadata.

        Returns:
            True if transition occurred, False otherwise.
        """

        normalized = self._normalize_event(event)
        base_state, _ = self._parse_contract_state(self.current_state)
        allowed = BASE_TRANSITIONS.get(base_state, {})

        if normalized not in allowed:
            self._log_event(
                normalized,
                source,
                timestamp,
                old_state=self.current_state,
                new_state=None,
                metadata=context,
                success=False,
                reason="Invalid transition",
            )
            return False

        # Guards
        if normalized == "SOLICITOR_EMAIL_SENT" and not self.can_send_to_solicitor():
            self._log_event(
                normalized,
                source,
                timestamp,
                old_state=self.current_state,
                new_state=None,
                metadata=context,
                success=False,
                reason="Solicitor email guard failed",
            )
            return False

        if normalized == "DOCUSIGN_RELEASE_REQUESTED":
            has_appt = self.deal.solicitor_appointment is not None or context.get("appointment_datetime")
            if not has_appt:
                self._log_event(
                    normalized,
                    source,
                    timestamp,
                    old_state=self.current_state,
                    new_state=None,
                    metadata=context,
                    success=False,
                    reason="DocuSign release requires appointment datetime",
                )
                return False

        old_state = self.current_state
        self._pre_transition(normalized, context, timestamp)

        next_base = allowed[normalized]
        new_state = self._resolve_next_state(next_base)

        self.deal.status = new_state
        self.deal.updated_at = self._coerce_dt(timestamp) or self._utcnow()

        self._log_event(
            normalized,
            source,
            timestamp,
            old_state=old_state,
            new_state=new_state,
            metadata=context,
            success=True,
        )

        self._post_transition(normalized, context, timestamp)
        return True

    def check_sla(self, now: Optional[datetime] = None, source: str = "system") -> bool:
        """Evaluate SLA status and transition to alert state if overdue."""

        if not self.deal.sla_deadline:
            return False

        current_now = self._coerce_dt(now) or self._utcnow()

        # Overdue at or after the deadline moment.
        if current_now < self.deal.sla_deadline:
            return False

        if self.current_state in (DealState.BUYER_SIGNED, DealState.EXECUTED):
            return False

        if self.current_state not in (
            DealState.DOCUSIGN_RELEASED,
            DealState.DOCUSIGN_RELEASE_REQUESTED,
        ):
            return False

        return self.transition("SLA_OVERDUE", source=source, timestamp=current_now)

    def can_send_to_solicitor(self, version: Optional[int] = None) -> bool:
        """Guard: only highest validated contract can be sent to solicitor."""

        if not self.deal.contracts:
            return False

        v = version or self.deal.current_version
        record = self.deal.contracts.get(v)
        if not record:
            return False

        if record.status != "VALIDATED_OK" or not record.is_valid:
            return False

        highest = max(self.deal.contracts.keys())
        if v != highest:
            return False

        if self.current_state in (DealState.SENT_TO_SOLICITOR, DealState.SOLICITOR_APPROVED):
            return False

        return True

    # ---------------------------------------------------------------------
    # Internal helpers
    # ---------------------------------------------------------------------

    def _normalize_event(self, event: str) -> str:
        """Map alias events to internal names."""

        return EVENT_ALIASES.get(event, event)

    def _parse_contract_state(self, state: DealState) -> Tuple[DealState, Optional[int]]:
        """Return (base_state, version) for a possibly versioned state."""

        match = CONTRACT_STATE_RE.match(state.value)
        if not match:
            return state, None

        stage = match.group("stage")
        version = int(match.group("version"))
        if stage == "RECEIVED":
            return DealState.CONTRACT_RECEIVED, version
        if stage == "VALIDATED_OK":
            return DealState.CONTRACT_VALIDATED_OK, version
        if stage == "HAS_DISCREPANCIES":
            return DealState.CONTRACT_HAS_DISCREPANCIES, version
        return state, version

    def _versioned_state(self, base: DealState, version: int) -> DealState:
        """Resolve a base contract state to a versioned state if defined."""

        if base == DealState.CONTRACT_RECEIVED:
            name = f"CONTRACT_V{version}_RECEIVED"
        elif base == DealState.CONTRACT_VALIDATED_OK:
            name = f"CONTRACT_V{version}_VALIDATED_OK"
        elif base == DealState.CONTRACT_HAS_DISCREPANCIES:
            name = f"CONTRACT_V{version}_HAS_DISCREPANCIES"
        else:
            return base

        if name in DealState.__members__:
            return DealState[name]
        return base

    def _resolve_next_state(self, next_base: DealState) -> DealState:
        """Resolve base next state to final state, applying current version."""

        if next_base in (
            DealState.CONTRACT_RECEIVED,
            DealState.CONTRACT_VALIDATED_OK,
            DealState.CONTRACT_HAS_DISCREPANCIES,
        ):
            if self.deal.current_version > 0:
                return self._versioned_state(next_base, self.deal.current_version)
        return next_base

    def _pre_transition(
        self,
        event: str,
        context: Dict[str, Any],
        timestamp: Optional[datetime],
    ) -> None:
        """Pre-transition hooks for side effects on the in-memory model."""

        if event == "CONTRACT_FROM_VENDOR":
            new_version = self._determine_contract_version(context.get("contract_version"))
            self._supersede_old_contracts(new_version, timestamp)
            self.deal.current_version = new_version

            filename = str(context.get("contract_filename") or context.get("filename") or "")
            received_at = self._coerce_dt(timestamp) or self._utcnow()

            self.deal.contracts[new_version] = ContractRecord(
                version=new_version,
                filename=filename,
                status="RECEIVED",
                received_at=received_at,
            )

        if event in ("VALIDATION_PASSED", "VALIDATION_FAILED"):
            self._record_validation(event, context, timestamp)

        if event == "SOLICITOR_APPROVED_WITH_APPOINTMENT":
            appt_dt = context.get("appointment_datetime")
            appt_parsed = self._coerce_dt(appt_dt)
            if appt_parsed:
                self.deal.solicitor_appointment = appt_parsed
                self.deal.sla_deadline = self._compute_sla_deadline(appt_parsed)

        if event == "DOCUSIGN_BUYER_SIGNED":
            # Cancel SLA timer if set.
            self.deal.sla_deadline = None

    def _post_transition(
        self,
        event: str,
        context: Dict[str, Any],
        timestamp: Optional[datetime],
    ) -> None:
        """Post-transition hooks.

        Auto-advances are opt-in via context flags to keep simulations explicit.
        """

        if event == "VALIDATION_PASSED":
            auto_flag = bool(context.get("auto_send_to_solicitor"))
            comparison_result = context.get("comparison_result")
            if isinstance(comparison_result, dict):
                auto_flag = auto_flag or bool(comparison_result.get("should_send_to_solicitor"))

            if auto_flag and self.can_send_to_solicitor():
                self.transition(
                    "SOLICITOR_EMAIL_SENT",
                    source="system",
                    timestamp=timestamp,
                )

        return None

    def _determine_contract_version(self, raw_version: Any) -> int:
        """Determine the next contract version from context or history."""

        existing_max = max(self.deal.contracts.keys(), default=0)

        if raw_version is None:
            return existing_max + 1

        if isinstance(raw_version, int):
            parsed = raw_version
        else:
            match = re.search(r"(\d+)", str(raw_version))
            parsed = int(match.group(1)) if match else 0

        if parsed <= 0:
            return existing_max + 1

        if parsed < existing_max:
            return existing_max + 1

        return parsed

    def _supersede_old_contracts(self, new_version: int, timestamp: Optional[datetime]) -> None:
        """Mark existing contracts as superseded when a higher version arrives."""

        if new_version <= 0:
            return

        for v, record in self.deal.contracts.items():
            if v < new_version and record.status not in ("SUPERSEDED", "EXECUTED"):
                record.status = "SUPERSEDED"
                self._log_event(
                    "CONTRACT_SUPERSEDED",
                    source="system",
                    timestamp=timestamp,
                    old_state=None,
                    new_state=None,
                    metadata={"version": v, "reason": f"Superseded by V{new_version}"},
                    success=True,
                )

    def _record_validation(
        self,
        event: str,
        context: Dict[str, Any],
        timestamp: Optional[datetime],
    ) -> None:
        """Update current contract record based on validation outcome."""

        v = self.deal.current_version
        record = self.deal.contracts.get(v)
        if not record:
            return

        validated_at = self._coerce_dt(timestamp) or self._utcnow()

        comparison_result = context.get("comparison_result")
        is_valid = event == "VALIDATION_PASSED"

        mismatches: List[Dict[str, Any]] = []
        risk_score: Optional[str] = None
        if isinstance(comparison_result, dict):
            mismatches_raw = comparison_result.get("mismatches") or []
            if isinstance(mismatches_raw, list):
                mismatches = [m for m in mismatches_raw if isinstance(m, dict)]
            risk_score = comparison_result.get("risk_score")

        record.is_valid = is_valid
        record.mismatches = mismatches
        record.risk_score = str(risk_score) if risk_score is not None else record.risk_score
        record.validated_at = validated_at
        record.status = "VALIDATED_OK" if is_valid else "HAS_DISCREPANCIES"

    def _compute_sla_deadline(self, appointment: datetime) -> datetime:
        """Compute SLA deadline from appointment datetime.

        Rule: appointment + 2 days, set to 09:00 local time of appointment tz.
        """

        deadline = appointment + timedelta(days=2)
        return deadline.replace(hour=9, minute=0, second=0, microsecond=0)

    def _log_event(
        self,
        event_type: str,
        source: str,
        timestamp: Optional[datetime],
        old_state: Optional[DealState],
        new_state: Optional[DealState],
        metadata: Dict[str, Any],
        success: bool,
        reason: Optional[str] = None,
    ) -> None:
        ts = self._coerce_dt(timestamp) or self._utcnow()
        self.deal.events.append(
            DealEvent(
                event_type=event_type,
                timestamp=ts,
                source=source,
                old_state=old_state.value if isinstance(old_state, DealState) else None,
                new_state=new_state.value if isinstance(new_state, DealState) else None,
                metadata=dict(metadata or {}),
                success=success,
                reason=reason,
            )
        )

    def _utcnow(self) -> datetime:
        return datetime.now(timezone.utc)

    def _coerce_dt(self, value: Any) -> Optional[datetime]:
        """Coerce an ISO string or datetime into a timezone-aware datetime."""

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
