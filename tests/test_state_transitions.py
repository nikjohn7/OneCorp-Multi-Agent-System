"""Tests for orchestrator state transitions and SLA behavior.

These tests replay the demo workflow in a deterministic way using:
- Ground-truth extracted EOI/contract fixtures for validation events.
- Email manifest event ordering for external triggers.
- Orchestrator components (StateMachine, DealStore, SLAMonitor).

Ground truth is used only as test fixtures.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import pytest

from src.agents.auditor import compare_contract_to_eoi
from src.orchestrator.deal_store import DealStore
from src.orchestrator.sla_monitor import SLAMonitor
from src.orchestrator.state_machine import DealState, StateMachine


def _email_by_id(manifest: Dict[str, Any], email_id: str) -> Dict[str, Any]:
    for e in manifest.get("emails", []):
        if e.get("email_id") == email_id:
            return e
    raise KeyError(f"Email not found in manifest: {email_id}")


def _expected_stage_states(expected_outputs: Dict[str, Any]) -> List[DealState]:
    stages = expected_outputs.get("workflow_stages", [])
    return [DealState(stage["state"]) for stage in stages]


def _apply_external_email_event(
    sm: StateMachine,
    email_meta: Dict[str, Any],
    extra_context: Optional[Dict[str, Any]] = None,
) -> bool:
    context = dict(extra_context or {})
    if email_meta.get("event_type") == "CONTRACT_FROM_VENDOR":
        context.setdefault("contract_version", email_meta.get("contract_version"))
        attachments = email_meta.get("attachments") or []
        if attachments:
            context.setdefault("contract_filename", attachments[0])

    if email_meta.get("event_type") == "SOLICITOR_APPROVED_WITH_APPOINTMENT":
        extracted = email_meta.get("extracted_data") or {}
        context.setdefault("appointment_datetime", extracted.get("appointment_datetime"))

    return sm.transition(
        email_meta["event_type"],
        source=email_meta["email_id"],
        timestamp=email_meta.get("timestamp"),
        **context,
    )


def _run_happy_path(
    monkeypatch: pytest.MonkeyPatch,
    emails_manifest: Dict[str, Any],
    eoi_extracted: Dict[str, Any],
    v1_extracted: Dict[str, Any],
    v2_extracted: Dict[str, Any],
    store: Optional[DealStore] = None,
) -> Tuple[StateMachine, List[DealState]]:
    monkeypatch.setenv("AUDITOR_DISABLE_LLM", "1")

    deal_id = emails_manifest["deal_id"]
    sm = StateMachine(deal_id)

    stage_states: List[DealState] = []

    # Stage 1: EOI signed
    _apply_external_email_event(sm, _email_by_id(emails_manifest, "email_1"))
    stage_states.append(sm.current_state)

    # Stage 2: V1 contract arrives
    email_2 = _email_by_id(emails_manifest, "email_2")
    _apply_external_email_event(sm, email_2)
    stage_states.append(sm.current_state)

    # Stage 3: Validation fails for V1
    v1_result = compare_contract_to_eoi(eoi_extracted, v1_extracted, use_llm="deterministic")
    assert v1_result["is_valid"] is False
    sm.transition(
        "VALIDATION_FAILED",
        source="system",
        timestamp=email_2.get("timestamp"),
        comparison_result=v1_result,
    )
    stage_states.append(sm.current_state)

    # Stage 4: Discrepancy alert sent
    sm.transition("DISCREPANCY_ALERT_SENT", source="system", timestamp=email_2.get("timestamp"))
    stage_states.append(sm.current_state)

    # Internal auto-step: awaiting amended contract
    assert sm.transition("AUTO", source="system", timestamp=email_2.get("timestamp"))
    assert sm.current_state == DealState.AWAITING_AMENDED_CONTRACT

    # Stage 5: V2 contract arrives (supersedes V1)
    email_2b = _email_by_id(emails_manifest, "email_2b")
    _apply_external_email_event(sm, email_2b)
    stage_states.append(sm.current_state)

    # Stage 6: Validation passes for V2 and auto-sends to solicitor
    v2_result = compare_contract_to_eoi(eoi_extracted, v2_extracted, use_llm="deterministic")
    assert v2_result["is_valid"] is True
    sm.transition(
        "VALIDATION_PASSED",
        source="system",
        timestamp=email_2b.get("timestamp"),
        comparison_result=v2_result,
    )
    stage_states.append(sm.current_state)

    # Stage 7: Solicitor approval with appointment
    email_4 = _email_by_id(emails_manifest, "email_4")
    _apply_external_email_event(sm, email_4)
    stage_states.append(sm.current_state)

    # Stage 8: Request vendor DocuSign release
    sm.transition(
        "DOCUSIGN_RELEASE_REQUESTED",
        source="system",
        timestamp=email_4.get("timestamp"),
        appointment_datetime=(email_4.get("extracted_data") or {}).get("appointment_datetime"),
    )
    stage_states.append(sm.current_state)

    # Stage 9: DocuSign released
    _apply_external_email_event(sm, _email_by_id(emails_manifest, "email_6"))
    stage_states.append(sm.current_state)

    # Stage 10: Buyer signed (cancels SLA)
    _apply_external_email_event(sm, _email_by_id(emails_manifest, "email_7"))
    stage_states.append(sm.current_state)

    # Stage 11: Executed
    _apply_external_email_event(sm, _email_by_id(emails_manifest, "email_8"))
    stage_states.append(sm.current_state)

    if store is not None:
        store.upsert_deal(sm.deal)

    return sm, stage_states


def test_happy_path_transitions(
    monkeypatch: pytest.MonkeyPatch,
    emails_manifest: Dict[str, Any],
    expected_outputs: Dict[str, Any],
    eoi_extracted: Dict[str, Any],
    v1_extracted: Dict[str, Any],
    v2_extracted: Dict[str, Any],
) -> None:
    """Replays the happy-path workflow and matches expected stage states."""

    sm, stage_states = _run_happy_path(
        monkeypatch, emails_manifest, eoi_extracted, v1_extracted, v2_extracted
    )

    expected_states = _expected_stage_states(expected_outputs)
    assert [s.value for s in stage_states] == [s.value for s in expected_states]

    # Versioning expectations.
    assert sm.deal.current_version == 2
    assert sm.deal.contracts[1].status == "SUPERSEDED"
    assert sm.deal.contracts[2].status == "VALIDATED_OK"

    # SLA cancelled after buyer signature.
    assert sm.deal.sla_deadline is None


def test_persistence_of_deal_state(
    monkeypatch: pytest.MonkeyPatch,
    emails_manifest: Dict[str, Any],
    eoi_extracted: Dict[str, Any],
    v1_extracted: Dict[str, Any],
    v2_extracted: Dict[str, Any],
) -> None:
    """DealStore persists and retrieves state, contracts, and events."""

    with DealStore(":memory:") as store:
        sm, _ = _run_happy_path(
            monkeypatch, emails_manifest, eoi_extracted, v1_extracted, v2_extracted, store=store
        )

        loaded = store.get_deal(sm.deal.deal_id)
        assert loaded is not None
        assert loaded.status == sm.current_state
        assert loaded.current_version == sm.current_version
        assert set(loaded.contracts.keys()) == set(sm.deal.contracts.keys())

        # Contracts survive round-trip.
        assert loaded.contracts[1].status == "SUPERSEDED"
        assert loaded.contracts[2].status == "VALIDATED_OK"

        # Some audit events recorded.
        event_types = {e.event_type for e in loaded.events}
        assert "CONTRACT_FROM_VENDOR" in event_types
        assert "CONTRACT_SUPERSEDED" in event_types


def test_sla_overdue_scenario(
    monkeypatch: pytest.MonkeyPatch,
    emails_manifest: Dict[str, Any],
    expected_outputs: Dict[str, Any],
    eoi_extracted: Dict[str, Any],
    v1_extracted: Dict[str, Any],
    v2_extracted: Dict[str, Any],
) -> None:
    """Removing buyer-signed event causes SLA overdue alert at deadline."""

    monkeypatch.setenv("AUDITOR_DISABLE_LLM", "1")

    with DealStore(":memory:") as store:
        sm = StateMachine(emails_manifest["deal_id"])

        # Process emails 1-6 and internal events (omit buyer signed and executed).
        _apply_external_email_event(sm, _email_by_id(emails_manifest, "email_1"))
        email_2 = _email_by_id(emails_manifest, "email_2")
        _apply_external_email_event(sm, email_2)
        v1_result = compare_contract_to_eoi(eoi_extracted, v1_extracted, use_llm="deterministic")
        sm.transition("VALIDATION_FAILED", comparison_result=v1_result)
        sm.transition("DISCREPANCY_ALERT_SENT")
        sm.transition("AUTO")

        email_2b = _email_by_id(emails_manifest, "email_2b")
        _apply_external_email_event(sm, email_2b)
        v2_result = compare_contract_to_eoi(eoi_extracted, v2_extracted, use_llm="deterministic")
        sm.transition("VALIDATION_PASSED", comparison_result=v2_result)

        email_4 = _email_by_id(emails_manifest, "email_4")
        _apply_external_email_event(sm, email_4)
        sm.transition(
            "DOCUSIGN_RELEASE_REQUESTED",
            appointment_datetime=(email_4.get("extracted_data") or {}).get("appointment_datetime"),
        )
        _apply_external_email_event(sm, _email_by_id(emails_manifest, "email_6"))

        assert sm.current_state == DealState.DOCUSIGN_RELEASED
        assert sm.deal.sla_deadline is not None

        store.upsert_deal(sm.deal)

        monitor = SLAMonitor(store)

        # Evaluate at the deadline time.
        deadline = sm.deal.sla_deadline
        fired = monitor.run(deadline)

        assert fired == [sm.deal.deal_id]
        loaded = store.get_deal(sm.deal.deal_id)
        assert loaded is not None
        assert loaded.status == DealState.SLA_OVERDUE_ALERT_SENT


def test_invalid_transition_guards() -> None:
    """Guards prevent invalid transitions."""

    sm = StateMachine("GUARD_TEST")

    # Cannot send to solicitor before validation.
    assert sm.can_transition("SOLICITOR_EMAIL_SENT") is False
    assert sm.transition("SOLICITOR_EMAIL_SENT") is False
    assert sm.current_state == DealState.EOI_RECEIVED

    # Highest-version guard blocks sending older version.
    sm.transition("CONTRACT_FROM_VENDOR", contract_version="V1")
    # Keep in validated-ok state without auto-sending to solicitor.
    sm.transition(
        "VALIDATION_PASSED",
        comparison_result={"is_valid": True, "should_send_to_solicitor": False},
    )
    assert sm.current_state in (DealState.CONTRACT_V1_VALIDATED_OK, DealState.CONTRACT_VALIDATED_OK)
    sm.transition("CONTRACT_FROM_VENDOR", contract_version="V2")
    assert sm.deal.current_version == 2
    assert sm.can_send_to_solicitor(version=1) is False
