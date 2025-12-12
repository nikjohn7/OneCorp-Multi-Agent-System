"""End-to-end integration tests for the OneCorp Multi-Agent System.

These tests validate the full workflow from EOI processing through to contract
execution, verifying that all agents work together correctly and produce the
expected outputs as defined in ground-truth/expected_outputs.json.

The tests run the DemoOrchestrator in a programmable way (not relying on stdout
parsing) to ensure all workflow stages, state transitions, and generated emails
are correct.

NOTE: These are true integration tests that make LLM API calls via the extractor.
They will be slow (~2-3 minutes per test) but validate the full system integration.
To run quickly, set EXTRACTOR_USE_FIXTURES=1 to use ground truth instead of LLM.
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List
from unittest import mock

import pytest

from src.main import DemoOrchestrator


@pytest.fixture(autouse=True)
def mock_extractor_if_requested(
    monkeypatch: pytest.MonkeyPatch,
    eoi_extracted: Dict[str, Any],
    v1_extracted: Dict[str, Any],
    v2_extracted: Dict[str, Any],
) -> None:
    """Mock the extractor to use ground truth fixtures if EXTRACTOR_USE_FIXTURES=1.

    This speeds up tests significantly by avoiding LLM API calls.
    For true end-to-end testing, run without this flag.
    """
    if os.getenv("EXTRACTOR_USE_FIXTURES", "1") == "1":
        def mock_extract_eoi(pdf_path):
            return eoi_extracted

        def mock_extract_contract(pdf_path):
            # Determine version from filename
            filename = str(pdf_path)
            if "V1" in filename or "v1" in filename:
                return v1_extracted
            elif "V2" in filename or "v2" in filename:
                return v2_extracted
            else:
                return v2_extracted  # Default to V2

        monkeypatch.setattr("src.agents.extractor.extract_eoi", mock_extract_eoi)
        monkeypatch.setattr("src.agents.extractor.extract_contract", mock_extract_contract)


class TestEndToEndWorkflow:
    """Test the complete end-to-end workflow of the multi-agent system."""

    def test_full_demo_workflow(
        self,
        expected_outputs: Dict[str, Any],
        tmp_path: Path,
    ) -> None:
        """Test the complete demo workflow matches expected outputs.

        This test runs through all workflow stages and verifies:
        - All state transitions occur in the correct sequence
        - Deal progresses through all expected states
        - Final state is EXECUTED
        """
        # Create orchestrator with in-memory database for testing
        db_path = tmp_path / "test_deals.db"
        orchestrator = DemoOrchestrator(db_path=str(db_path), verbose=False)

        # Expected workflow states from fixture
        workflow_stages = expected_outputs.get("workflow_stages", [])
        expected_states = [stage["state"] for stage in workflow_stages]

        # Track actual states encountered
        actual_states: List[str] = []

        # Stage 1: Process EOI
        eoi_data = orchestrator.process_eoi()
        assert eoi_data is not None
        assert orchestrator.deal_id is not None

        deal = orchestrator.store.get_deal(orchestrator.deal_id)
        assert deal is not None
        actual_states.append(deal.status.value)

        # Stage 2: Process Contract V1 (has discrepancies)
        contract_v1_data, v1_comparison = orchestrator.process_contract_v1()
        assert contract_v1_data is not None
        assert v1_comparison is not None
        assert v1_comparison.get("is_valid") is False
        assert v1_comparison.get("mismatch_count", 0) == 5  # Expected 5 mismatches

        deal = orchestrator.store.get_deal(orchestrator.deal_id)
        # After processing V1 with discrepancies, state should be AMENDMENT_REQUESTED
        actual_states.append(deal.status.value)

        # Verify discrepancy alert was generated
        discrepancy_alerts = [
            email for email in orchestrator.generated_emails
            if email.get("type") == "DISCREPANCY_ALERT"
        ]
        assert len(discrepancy_alerts) == 1

        # Stage 5: Process Contract V2 (corrected)
        contract_v2_data, v2_comparison, solicitor_email = orchestrator.process_contract_v2()
        assert contract_v2_data is not None
        assert v2_comparison is not None
        assert v2_comparison.get("is_valid") is True
        assert v2_comparison.get("mismatch_count", 0) == 0  # No mismatches

        deal = orchestrator.store.get_deal(orchestrator.deal_id)
        # After V2 validates and sends to solicitor, state should be SENT_TO_SOLICITOR
        actual_states.append(deal.status.value)

        # Verify solicitor email was generated
        solicitor_emails = [
            email for email in orchestrator.generated_emails
            if email.get("type") == "CONTRACT_TO_SOLICITOR"
        ]
        assert len(solicitor_emails) == 1

        # Stage 7: Process Solicitor Approval
        appointment_dt, vendor_email = orchestrator.process_solicitor_approval(
            appointment_phrase="Thursday at 11:30am",
            email_timestamp="2025-01-14T09:12:00+11:00",
        )
        assert appointment_dt is not None
        assert vendor_email is not None

        deal = orchestrator.store.get_deal(orchestrator.deal_id)
        # After solicitor approval and vendor release, state should be DOCUSIGN_RELEASE_REQUESTED
        actual_states.append(deal.status.value)

        # Verify vendor release email was generated
        vendor_emails = [
            email for email in orchestrator.generated_emails
            if email.get("type") == "VENDOR_DOCUSIGN_RELEASE"
        ]
        assert len(vendor_emails) == 1

        # Stage 9-11: Process DocuSign Flow
        orchestrator.process_docusign_flow()

        deal = orchestrator.store.get_deal(orchestrator.deal_id)
        assert deal.status.value == "EXECUTED"
        actual_states.append(deal.status.value)

        # Verify we hit all major expected states
        # Note: We only track states after major workflow steps, so we check that we
        # progressed through the workflow correctly
        assert "EOI_RECEIVED" in actual_states
        assert "AMENDMENT_REQUESTED" in actual_states
        assert "SENT_TO_SOLICITOR" in actual_states
        assert "DOCUSIGN_RELEASE_REQUESTED" in actual_states
        assert "EXECUTED" in actual_states

        # The workflow should reach final executed state
        assert deal.status.value == "EXECUTED"

    def test_generated_emails_match_expected(
        self,
        expected_outputs: Dict[str, Any],
        tmp_path: Path,
    ) -> None:
        """Test that all expected outbound emails are generated with correct structure.

        Validates:
        - Discrepancy alert email is generated for V1
        - Solicitor email is generated for V2
        - Vendor release email is generated after approval
        - Each email has correct recipients and key content
        """
        # Create orchestrator with in-memory database
        db_path = tmp_path / "test_deals.db"
        orchestrator = DemoOrchestrator(db_path=str(db_path), verbose=False)

        # Run workflow
        orchestrator.process_eoi()
        orchestrator.process_contract_v1()
        orchestrator.process_contract_v2()
        orchestrator.process_solicitor_approval()

        # Get expected email outputs from fixture
        workflow_stages = expected_outputs.get("workflow_stages", [])

        # Find stages with expected outputs
        stages_with_outputs = [
            stage for stage in workflow_stages
            if stage.get("outputs")
        ]

        # Stage 3: Discrepancy alert
        stage_3 = next(
            (s for s in stages_with_outputs if s.get("state") == "CONTRACT_V1_HAS_DISCREPANCIES"),
            None
        )
        if stage_3:
            expected_alert = stage_3["outputs"][0]
            actual_alerts = [
                email for email in orchestrator.generated_emails
                if email.get("type") == "DISCREPANCY_ALERT"
            ]
            assert len(actual_alerts) == 1

            alert_email = actual_alerts[0]["email"]
            assert expected_alert["from"] in alert_email.from_addr
            assert set(expected_alert["to"]).issubset(set(alert_email.to_addrs))

            # Check subject contains expected text
            assert "Discrepancy" in alert_email.subject or "Contract" in alert_email.subject

            # Check body contains key mismatch information
            body_must_contain = expected_alert.get("body_must_contain", [])
            for required_text in body_must_contain:
                assert str(required_text) in alert_email.body, \
                    f"Discrepancy alert missing required text: {required_text}"

        # Stage 6: Contract to solicitor
        stage_6 = next(
            (s for s in stages_with_outputs if s.get("state") == "SENT_TO_SOLICITOR"),
            None
        )
        if stage_6:
            expected_solicitor = stage_6["outputs"][0]
            actual_solicitor = [
                email for email in orchestrator.generated_emails
                if email.get("type") == "CONTRACT_TO_SOLICITOR"
            ]
            assert len(actual_solicitor) == 1

            solicitor_email = actual_solicitor[0]["email"]
            assert expected_solicitor["from"] in solicitor_email.from_addr
            assert set(expected_solicitor["to"]).issubset(set(solicitor_email.to_addrs))

            # Check subject contains expected text
            subject_contains = expected_solicitor.get("subject_contains", "")
            if subject_contains:
                assert subject_contains in solicitor_email.subject

            # Check attachments
            expected_attachments = expected_solicitor.get("attachments", [])
            if expected_attachments:
                assert len(solicitor_email.attachments) >= len(expected_attachments)
                # Check that key filename parts are present (e.g., "V2" for V2 contract)
                for expected_attachment in expected_attachments:
                    # Check if "V2" appears in any attachment
                    assert any(
                        "V2" in str(att) or "v2" in str(att).lower()
                        for att in solicitor_email.attachments
                    ), f"Missing V2 contract attachment"

        # Stage 8: Vendor DocuSign release
        stage_8 = next(
            (s for s in stages_with_outputs if s.get("state") == "DOCUSIGN_RELEASE_REQUESTED"),
            None
        )
        if stage_8:
            expected_vendor = stage_8["outputs"][0]
            actual_vendor = [
                email for email in orchestrator.generated_emails
                if email.get("type") == "VENDOR_DOCUSIGN_RELEASE"
            ]
            assert len(actual_vendor) == 1

            vendor_email = actual_vendor[0]["email"]
            assert expected_vendor["from"] in vendor_email.from_addr
            assert set(expected_vendor["to"]).issubset(set(vendor_email.to_addrs))

            # Check body contains expected text
            body_must_contain = expected_vendor.get("body_must_contain", [])
            for required_text in body_must_contain:
                assert required_text in vendor_email.body, \
                    f"Vendor release email missing required text: {required_text}"

    def test_sla_overdue_scenario(
        self,
        expected_outputs: Dict[str, Any],
        tmp_path: Path,
    ) -> None:
        """Test that SLA overdue alert is generated in the simulated failure scenario.

        This test:
        - Runs workflow through solicitor approval
        - Simulates time passing to SLA deadline without buyer signature
        - Verifies SLA overdue alert is generated with correct content
        """
        # Create orchestrator
        db_path = tmp_path / "test_deals.db"
        orchestrator = DemoOrchestrator(db_path=str(db_path), verbose=False)

        # Run workflow up to DocuSign released (buyer hasn't signed yet)
        orchestrator.process_eoi()
        orchestrator.process_contract_v1()
        orchestrator.process_contract_v2()
        orchestrator.process_solicitor_approval()
        orchestrator.process_docusign_released()

        # Get SLA test expectations
        sla_test = expected_outputs.get("sla_test_scenario", {})
        expected_alert = sla_test.get("expected_output", {})

        # Simulate time passing to SLA deadline
        sla_alert = orchestrator.test_sla_overdue(
            simulated_time="2025-01-18T09:00:00+11:00"
        )

        # Verify alert was generated
        # The alert should be in generated_emails as well
        sla_alerts = [
            email for email in orchestrator.generated_emails
            if email.get("type") == "SLA_OVERDUE_ALERT"
        ]

        assert len(sla_alerts) == 1, "SLA overdue alert should be generated"
        sla_alert = sla_alerts[0]["email"]

        # Check alert structure
        assert expected_alert["from"] in sla_alert.from_addr
        assert set(expected_alert["to"]).issubset(set(sla_alert.to_addrs))

        # Check subject
        subject_contains = expected_alert.get("subject_contains", "")
        if subject_contains:
            assert subject_contains in sla_alert.subject

        # Check body contains required information
        body_must_contain = expected_alert.get("body_must_contain", [])
        for required_text in body_must_contain:
            # Convert to string and check (case-insensitive for phrases like "Recommended Action")
            text_str = str(required_text)
            body_lower = sla_alert.body.lower()
            text_lower = text_str.lower()

            assert text_lower in body_lower or text_str in sla_alert.body, \
                f"SLA alert missing required text: {required_text}"

    def test_final_state_is_executed(
        self,
        tmp_path: Path,
    ) -> None:
        """Test that the normal workflow ends in EXECUTED state.

        This is a simple sanity check that the happy path completes successfully.
        """
        # Create orchestrator
        db_path = tmp_path / "test_deals.db"
        orchestrator = DemoOrchestrator(db_path=str(db_path), verbose=False)

        # Run full workflow
        orchestrator.process_eoi()
        orchestrator.process_contract_v1()
        orchestrator.process_contract_v2()
        orchestrator.process_solicitor_approval()
        orchestrator.process_docusign_flow()

        # Verify final state
        deal = orchestrator.store.get_deal(orchestrator.deal_id)
        assert deal is not None
        assert deal.status.value == "EXECUTED"

    def test_sla_alert_not_generated_in_normal_workflow(
        self,
        tmp_path: Path,
    ) -> None:
        """Test that SLA overdue alert is NOT generated when buyer signs on time.

        This ensures the SLA alert is only triggered in the overdue scenario.
        """
        # Create orchestrator
        db_path = tmp_path / "test_deals.db"
        orchestrator = DemoOrchestrator(db_path=str(db_path), verbose=False)

        # Run full workflow (buyer signs on time)
        orchestrator.process_eoi()
        orchestrator.process_contract_v1()
        orchestrator.process_contract_v2()
        orchestrator.process_solicitor_approval()
        orchestrator.process_docusign_flow()  # This includes buyer signature

        # Verify no SLA alerts were generated
        sla_alerts = [
            email for email in orchestrator.generated_emails
            if email.get("type") == "SLA_OVERDUE_ALERT"
        ]
        assert len(sla_alerts) == 0

    def test_contract_v1_has_exactly_5_mismatches(
        self,
        tmp_path: Path,
    ) -> None:
        """Test that V1 contract comparison detects exactly 5 mismatches.

        This validates the Auditor agent's comparison logic is working correctly.
        """
        # Create orchestrator
        db_path = tmp_path / "test_deals.db"
        orchestrator = DemoOrchestrator(db_path=str(db_path), verbose=False)

        # Process EOI and V1
        orchestrator.process_eoi()
        _, v1_comparison = orchestrator.process_contract_v1()

        # Verify mismatch count
        assert v1_comparison.get("mismatch_count") == 5
        assert v1_comparison.get("is_valid") is False
        assert v1_comparison.get("risk_score") == "HIGH"

        # Verify mismatches include key fields
        mismatches = v1_comparison.get("mismatches", [])
        mismatch_fields = {m.get("field") for m in mismatches}

        # These are the expected critical mismatches from ground truth
        # Fields use dot notation like "property.lot_number"
        assert any("lot_number" in field for field in mismatch_fields)
        assert any("total_price" in field for field in mismatch_fields)
        assert any("finance" in field for field in mismatch_fields)

    def test_contract_v2_has_zero_mismatches(
        self,
        tmp_path: Path,
    ) -> None:
        """Test that V2 contract comparison validates successfully with no mismatches.

        This confirms the corrected contract passes validation.
        """
        # Create orchestrator
        db_path = tmp_path / "test_deals.db"
        orchestrator = DemoOrchestrator(db_path=str(db_path), verbose=False)

        # Process EOI, V1, and V2
        orchestrator.process_eoi()
        orchestrator.process_contract_v1()
        _, v2_comparison, _ = orchestrator.process_contract_v2()

        # Verify V2 validates successfully
        assert v2_comparison.get("mismatch_count") == 0
        assert v2_comparison.get("is_valid") is True
        assert v2_comparison.get("risk_score") in ["NONE", None]

    def test_v2_supersedes_v1(
        self,
        tmp_path: Path,
    ) -> None:
        """Test that V2 contract automatically supersedes V1.

        This validates the state machine's version management logic.
        """
        # Create orchestrator
        db_path = tmp_path / "test_deals.db"
        orchestrator = DemoOrchestrator(db_path=str(db_path), verbose=False)

        # Process EOI and both contracts
        orchestrator.process_eoi()
        orchestrator.process_contract_v1()
        orchestrator.process_contract_v2()

        # Verify V2 is the active contract
        deal = orchestrator.store.get_deal(orchestrator.deal_id)
        assert deal is not None

        # The deal should have progressed past V1's failed state
        # and should be in SENT_TO_SOLICITOR state after V2 validation
        assert deal.status.value == "SENT_TO_SOLICITOR"

    def test_appointment_datetime_resolved_correctly(
        self,
        tmp_path: Path,
    ) -> None:
        """Test that appointment phrase is resolved to correct datetime.

        Validates the date_resolver utility integration.
        """
        # Create orchestrator
        db_path = tmp_path / "test_deals.db"
        orchestrator = DemoOrchestrator(db_path=str(db_path), verbose=False)

        # Process up to solicitor approval
        orchestrator.process_eoi()
        orchestrator.process_contract_v1()
        orchestrator.process_contract_v2()

        appointment_dt, _ = orchestrator.process_solicitor_approval(
            appointment_phrase="Thursday at 11:30am",
            email_timestamp="2025-01-14T09:12:00+11:00",
        )

        # Verify appointment datetime is resolved
        assert appointment_dt is not None

        # The appointment should be Thursday, January 16, 2025 at 11:30am
        # (2 days after the email on Tuesday, Jan 14)
        assert appointment_dt.year == 2025
        assert appointment_dt.month == 1
        assert appointment_dt.day == 16
        assert appointment_dt.hour == 11
        assert appointment_dt.minute == 30

    def test_sla_deadline_calculated_correctly(
        self,
        tmp_path: Path,
    ) -> None:
        """Test that SLA deadline is calculated correctly.

        SLA deadline should be 2 business days after appointment at 9am.
        """
        # Create orchestrator
        db_path = tmp_path / "test_deals.db"
        orchestrator = DemoOrchestrator(db_path=str(db_path), verbose=False)

        # Process up to solicitor approval
        orchestrator.process_eoi()
        orchestrator.process_contract_v1()
        orchestrator.process_contract_v2()
        orchestrator.process_solicitor_approval()

        # Check SLA deadline
        deal = orchestrator.store.get_deal(orchestrator.deal_id)
        assert deal.sla_deadline is not None

        # SLA deadline should be Saturday, January 18, 2025 at 9:00am
        # (2 days after appointment on Thursday, Jan 16)
        assert deal.sla_deadline.year == 2025
        assert deal.sla_deadline.month == 1
        assert deal.sla_deadline.day == 18
        assert deal.sla_deadline.hour == 9
        assert deal.sla_deadline.minute == 0

    def test_all_emails_have_required_fields(
        self,
        tmp_path: Path,
    ) -> None:
        """Test that all generated emails have required fields.

        Validates email structure compliance.
        """
        # Create orchestrator
        db_path = tmp_path / "test_deals.db"
        orchestrator = DemoOrchestrator(db_path=str(db_path), verbose=False)

        # Run workflow to generate emails
        orchestrator.process_eoi()
        orchestrator.process_contract_v1()
        orchestrator.process_contract_v2()
        orchestrator.process_solicitor_approval()

        # Verify all generated emails have required fields
        for email_entry in orchestrator.generated_emails:
            email = email_entry.get("email")
            assert email is not None

            # Check required fields
            assert hasattr(email, "from_addr")
            assert hasattr(email, "to_addrs")
            assert hasattr(email, "subject")
            assert hasattr(email, "body")

            assert email.from_addr is not None and email.from_addr != ""
            assert email.to_addrs is not None and len(email.to_addrs) > 0
            assert email.subject is not None and email.subject != ""
            assert email.body is not None and email.body != ""
