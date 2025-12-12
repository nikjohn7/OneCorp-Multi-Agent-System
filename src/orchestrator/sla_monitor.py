"""SLA monitoring for the orchestrator.

The SLA monitor is a deterministic helper that:
- Registers SLA deadlines after solicitor appointment is confirmed.
- Cancels deadlines when buyer signs.
- Periodically checks for overdue deadlines and emits an SLA_OVERDUE event.

It integrates with `DealStore` for persistence and uses `StateMachine`
for guard/transition logic, keeping business rules centralized.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from src.orchestrator.deal_store import DealStore
from src.orchestrator.state_machine import Deal, DealEvent, DealState, StateMachine


class SLAMonitorError(Exception):
    """Raised when SLA monitor operations fail."""


@dataclass
class SLARule:
    """Configuration for an SLA deadline."""

    offset_days: int = 2
    check_time_local: time = time(9, 0, 0)

    def compute_deadline(self, appointment: datetime) -> datetime:
        """Compute deadline from appointment datetime.

        Rule: appointment + offset_days, at check_time_local in the
        appointment timezone.
        """

        appt = appointment
        if appt.tzinfo is None:
            appt = appt.replace(tzinfo=timezone.utc)

        deadline = appt + timedelta(days=self.offset_days)
        return deadline.replace(
            hour=self.check_time_local.hour,
            minute=self.check_time_local.minute,
            second=self.check_time_local.second,
            microsecond=0,
        )


class SLAMonitor:
    """Monitors and enforces SLA deadlines using a DealStore."""

    def __init__(self, store: DealStore, rule: Optional[SLARule] = None) -> None:
        self.store = store
        self.rule = rule or SLARule()

    # ------------------------------------------------------------------
    # Registration / cancellation
    # ------------------------------------------------------------------

    def register_timer(
        self,
        deal_id: str,
        appointment_datetime: Union[str, datetime],
        source: str = "system",
        timestamp: Optional[Union[str, datetime]] = None,
    ) -> datetime:
        """Register/update an SLA timer for a deal.

        Args:
            deal_id: Deal identifier.
            appointment_datetime: Appointment datetime (ISO string or datetime).
            source: Event source for audit trail.

        Returns:
            The computed SLA deadline.
        """

        deal = self.store.get_deal(deal_id, include_events=True)
        if deal is None:
            raise SLAMonitorError(f"Deal not found: {deal_id}")

        appt_dt = self._coerce_dt(appointment_datetime)
        if appt_dt is None:
            raise SLAMonitorError("Invalid appointment datetime")

        deadline = self.rule.compute_deadline(appt_dt)
        deal.solicitor_appointment = appt_dt
        deal.sla_deadline = deadline

        # Add an audit event (idempotent insert in store).
        event_ts = self._coerce_dt(timestamp) or datetime.now(timezone.utc)
        deal.events.append(
            DealEvent(
                event_type="SLA_TIMER_REGISTERED",
                timestamp=event_ts,
                source=source,
                old_state=None,
                new_state=None,
                metadata={
                    "appointment_datetime": appt_dt.isoformat(),
                    "sla_deadline": deadline.isoformat(),
                },
            )
        )

        self.store.upsert_deal(deal)
        return deadline

    # Compatibility aliases (helpful for tests/callers)

    def register_sla_timer(
        self,
        deal_id: str,
        appointment_datetime: Union[str, datetime],
        source: str = "system",
        timestamp: Optional[Union[str, datetime]] = None,
    ) -> datetime:
        return self.register_timer(
            deal_id=deal_id,
            appointment_datetime=appointment_datetime,
            source=source,
            timestamp=timestamp,
        )

    def cancel_timer(self, deal_id: str, reason: str = "buyer_signed", source: str = "system") -> None:
        """Cancel an SLA timer for a deal (if present)."""

        deal = self.store.get_deal(deal_id, include_events=True)
        if deal is None:
            raise SLAMonitorError(f"Deal not found: {deal_id}")

        if deal.sla_deadline is None:
            return

        old_deadline = deal.sla_deadline
        deal.sla_deadline = None

        deal.events.append(
            DealEvent(
                event_type="SLA_TIMER_CANCELLED",
                timestamp=datetime.now(timezone.utc),
                source=source,
                old_state=None,
                new_state=None,
                metadata={"old_deadline": old_deadline.isoformat(), "reason": reason},
            )
        )

        self.store.upsert_deal(deal)

    def cancel_sla_timer(self, deal_id: str, reason: str = "buyer_signed", source: str = "system") -> None:
        return self.cancel_timer(deal_id=deal_id, reason=reason, source=source)

    # ------------------------------------------------------------------
    # Periodic evaluation
    # ------------------------------------------------------------------

    def evaluate_due_deadlines(
        self,
        now: Union[str, datetime],
        source: str = "system",
    ) -> List[str]:
        """Evaluate all deals with due SLA deadlines.

        For each due deal, this calls `StateMachine.check_sla(now)` to
        ensure guard conditions are respected, and persists any transition.

        Args:
            now: Current time (ISO string or datetime).
            source: Source for generated SLA_OVERDUE events.

        Returns:
            List of deal_ids for which an SLA overdue alert was emitted.
        """

        now_dt = self._coerce_dt(now)
        if now_dt is None:
            raise SLAMonitorError("Invalid now datetime")

        pending = self.store.get_pending_sla_checks(now_dt)
        fired: List[str] = []

        for deal_id, _deadline in pending:
            deal = self.store.get_deal(deal_id, include_events=True)
            if deal is None:
                continue

            sm = StateMachine(deal_id, initial_state=deal.status, canonical=deal.canonical)
            sm.deal = deal  # reuse loaded deal model

            transitioned = sm.check_sla(now=now_dt, source=source)
            if transitioned:
                fired.append(deal_id)
                self.store.upsert_deal(sm.deal)

        return fired

    def run(self, now: Union[str, datetime], source: str = "system") -> List[str]:
        """Alias for periodic evaluation."""

        return self.evaluate_due_deadlines(now=now, source=source)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _coerce_dt(self, value: Any) -> Optional[datetime]:
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
