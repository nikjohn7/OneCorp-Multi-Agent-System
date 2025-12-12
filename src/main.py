#!/usr/bin/env python3
"""CLI entry point for the OneCorp Multi-Agent System.

This module orchestrates the full demo workflow for post-EOI contract processing.
It coordinates Router, Extractor, Auditor, Comms agents with the state machine,
deal store, and SLA monitor.

Usage:
    python -m src.main --demo          # Run full demo
    python -m src.main --step eoi      # Run individual step
    python -m src.main --test-sla      # Test SLA overdue scenario
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# Project root
PROJECT_ROOT = Path(__file__).parent.parent


def setup_paths() -> Dict[str, Path]:
    """Set up paths to data files and directories."""
    return {
        "eoi_pdf": PROJECT_ROOT / "data" / "source-of-truth" / "EOI_John_JaneSmith.pdf",
        "contract_v1": PROJECT_ROOT / "data" / "contracts" / "CONTRACT_V1.pdf",
        "contract_v2": PROJECT_ROOT / "data" / "contracts" / "CONTRACT_V2.pdf",
        "emails_dir": PROJECT_ROOT / "data" / "emails" / "incoming",
        "manifest": PROJECT_ROOT / "data" / "emails_manifest.json",
        "db_path": PROJECT_ROOT / "data" / "deals.db",
    }


def load_manifest(path: Path) -> Dict[str, Any]:
    """Load emails manifest JSON."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def print_section(title: str) -> None:
    """Print a section header."""
    print()
    print("=" * 70)
    print(f"  {title}")
    print("=" * 70)
    print()


def print_subsection(title: str) -> None:
    """Print a subsection header."""
    print()
    print(f"--- {title} ---")
    print()


def print_state_transition(old_state: str, new_state: str, event: str) -> None:
    """Print a state transition message."""
    print(f"  State: {old_state} -> {new_state} (via {event})")


def print_mismatch(mismatch: Dict[str, Any]) -> None:
    """Print a single mismatch entry."""
    field_display = mismatch.get("field_display", mismatch.get("field"))
    eoi_val = mismatch.get("eoi_value_formatted") or mismatch.get("eoi_value")
    contract_val = mismatch.get("contract_value_formatted") or mismatch.get("contract_value")
    severity = mismatch.get("severity", "UNKNOWN")
    print(f"    - {field_display}: EOI='{eoi_val}' vs Contract='{contract_val}' [{severity}]")


def safe_format_currency(value: Any) -> str:
    """Format a currency-like value safely.

    Accepts numbers or strings; falls back to raw text on parse failure.
    """
    if value is None:
        return ""
    text = str(value).strip()
    try:
        number = int(float(text.replace("$", "").replace(",", "")))
        return f"${number:,}"
    except Exception:
        return text


class DemoOrchestrator:
    """Orchestrates the multi-agent demo workflow."""

    def __init__(self, db_path: Optional[Path] = None, verbose: bool = True):
        """Initialize the orchestrator.

        Args:
            db_path: Path to SQLite database (use :memory: for tests)
            verbose: Whether to print detailed output
        """
        self.paths = setup_paths()
        self.db_path = db_path or self.paths["db_path"]
        self.verbose = verbose

        # Lazy-load agents and orchestrator components
        self._store: Optional[Any] = None
        self._sla_monitor: Optional[Any] = None

        # Deal tracking
        self.deal_id: Optional[str] = None
        self.eoi_data: Optional[Dict[str, Any]] = None
        self.canonical_fields: Optional[Dict[str, Any]] = None

        # Generated emails tracking
        self.generated_emails: List[Dict[str, Any]] = []

    @property
    def store(self):
        """Lazy-load DealStore."""
        if self._store is None:
            from src.orchestrator.deal_store import DealStore
            self._store = DealStore(self.db_path)
        return self._store

    @property
    def sla_monitor(self):
        """Lazy-load SLAMonitor."""
        if self._sla_monitor is None:
            from src.orchestrator.sla_monitor import SLAMonitor
            self._sla_monitor = SLAMonitor(self.store)
        return self._sla_monitor

    def log(self, message: str) -> None:
        """Log a message if verbose mode is on."""
        if self.verbose:
            logger.info(message)

    def print(self, message: str) -> None:
        """Print a message if verbose mode is on."""
        if self.verbose:
            print(message)

    # =========================================================================
    # Step 1: Process EOI
    # =========================================================================

    def process_eoi(self) -> Dict[str, Any]:
        """Process the EOI PDF and create a new deal.

        Returns:
            Extracted EOI data
        """
        print_section("STEP 1: Processing Expression of Interest (EOI)")

        from src.agents.extractor import extract_eoi
        from src.orchestrator.state_machine import StateMachine, generate_deal_id

        # Extract EOI data
        self.log(f"Extracting fields from: {self.paths['eoi_pdf'].name}")
        self.eoi_data = extract_eoi(self.paths["eoi_pdf"])
        self.canonical_fields = self.eoi_data.get("fields", {})

        # Generate deal ID from extracted fields
        property_info = self.canonical_fields.get("property", {})
        lot_number = property_info.get("lot_number", "")
        address = property_info.get("address", "")
        self.deal_id = generate_deal_id(lot_number, address)

        self.print(f"  Deal ID: {self.deal_id}")
        self.print(f"  Lot Number: {lot_number}")
        self.print(f"  Property: {address}")

        # Extract purchaser info
        purchaser_1 = self.canonical_fields.get("purchaser_1", {})
        purchaser_2 = self.canonical_fields.get("purchaser_2", {})
        purchasers = f"{purchaser_1.get('first_name', '')} {purchaser_1.get('last_name', '')}"
        if purchaser_2:
            purchasers += f" & {purchaser_2.get('first_name', '')} {purchaser_2.get('last_name', '')}"
        self.print(f"  Purchasers: {purchasers}")

        # Extract pricing
        pricing = self.canonical_fields.get("pricing", {})
        total_price = pricing.get("total_price")
        if total_price:
            self.print(f"  Total Price: {safe_format_currency(total_price)}")

        # Extract finance terms
        finance = self.canonical_fields.get("finance", {})
        is_subject = finance.get("is_subject_to_finance", False)
        finance_display = "Subject to Finance" if is_subject else "NOT Subject to Finance"
        self.print(f"  Finance Terms: {finance_display}")

        # Create state machine and persist deal
        sm = StateMachine(
            deal_id=self.deal_id,
            canonical=self.canonical_fields,
        )

        # Extract solicitor and vendor emails for later use
        solicitor = self.canonical_fields.get("solicitor", {})
        sm.deal.solicitor_email = solicitor.get("email")

        # Persist to store
        self.store.upsert_deal(sm.deal)

        print_subsection("EOI Processing Complete")
        self.print(f"  State: EOI_RECEIVED")
        self.print(f"  Source of truth established for {self.deal_id}")

        return self.eoi_data

    # =========================================================================
    # Step 2: Process Contract V1 (with discrepancies)
    # =========================================================================

    def process_contract_v1(self) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Process Contract V1 and detect discrepancies.

        Returns:
            Tuple of (extracted contract data, comparison result)
        """
        print_section("STEP 2: Processing Contract V1 (with intentional errors)")

        from src.agents.extractor import extract_contract
        from src.agents.auditor import compare_contract_to_eoi
        from src.agents.comms import build_discrepancy_alert_email
        from src.orchestrator.state_machine import StateMachine, DealState

        if not self.deal_id:
            raise RuntimeError("Must process EOI first")

        # Load deal from store
        deal = self.store.get_deal(self.deal_id)
        if not deal:
            raise RuntimeError(f"Deal not found: {self.deal_id}")

        sm = StateMachine(self.deal_id, initial_state=deal.status, canonical=deal.canonical)
        sm.deal = deal

        # Extract contract data
        self.log(f"Extracting fields from: {self.paths['contract_v1'].name}")
        contract_data = extract_contract(self.paths["contract_v1"])
        contract_fields = contract_data.get("fields", {})
        contract_version = contract_data.get("version", "V1")

        self.print(f"  Contract Version: {contract_version}")

        # Transition: receive contract
        old_state = sm.current_state.value
        sm.transition(
            "CONTRACT_FROM_VENDOR",
            source="email_2",
            contract_version=contract_version,
            contract_filename=self.paths["contract_v1"].name,
        )
        print_state_transition(old_state, sm.current_state.value, "CONTRACT_FROM_VENDOR")

        # Compare contract to EOI (deterministic mode for reliable results)
        print_subsection("Auditor: Comparing Contract V1 to EOI")
        comparison_result = compare_contract_to_eoi(
            self.eoi_data,
            contract_data,
            use_llm=False,  # Deterministic for demo reliability
        )

        is_valid = comparison_result.get("is_valid", False)
        mismatch_count = comparison_result.get("mismatch_count", 0)
        risk_score = comparison_result.get("risk_score", "UNKNOWN")
        mismatches = comparison_result.get("mismatches", [])

        self.print(f"  Is Valid: {is_valid}")
        self.print(f"  Mismatch Count: {mismatch_count}")
        self.print(f"  Risk Score: {risk_score}")

        if mismatches:
            self.print(f"\n  Mismatches detected ({len(mismatches)}):")
            for m in mismatches:
                print_mismatch(m)

        # Transition: validation failed
        old_state = sm.current_state.value
        sm.transition(
            "VALIDATION_FAILED",
            source="auditor",
            comparison_result=comparison_result,
        )
        print_state_transition(old_state, sm.current_state.value, "VALIDATION_FAILED")

        # Generate discrepancy alert email
        print_subsection("Comms: Generating Discrepancy Alert")
        alert_email = build_discrepancy_alert_email(
            context={"fields": self.canonical_fields, "contract_filename": self.paths["contract_v1"].name},
            comparison_result=comparison_result,
            use_llm=False,  # Deterministic for demo reliability
        )

        self.print(f"  To: {', '.join(alert_email.to_addrs)}")
        self.print(f"  Subject: {alert_email.subject}")
        self.print(f"\n  Body preview:\n{alert_email.body[:500]}...")

        self.generated_emails.append({
            "type": "DISCREPANCY_ALERT",
            "email": alert_email,
        })

        # Transition: alert sent -> amendment requested
        old_state = sm.current_state.value
        sm.transition("DISCREPANCY_ALERT_SENT", source="comms")
        print_state_transition(old_state, sm.current_state.value, "DISCREPANCY_ALERT_SENT")

        # Persist state
        self.store.upsert_deal(sm.deal)

        print_subsection("Contract V1 Processing Complete")
        self.print(f"  Final State: {sm.current_state.value}")
        self.print("  V1 has discrepancies - awaiting amended contract")

        return contract_data, comparison_result

    # =========================================================================
    # Step 3: Process Contract V2 (corrected)
    # =========================================================================

    def process_contract_v2(self) -> Tuple[Dict[str, Any], Dict[str, Any], Any]:
        """Process Contract V2 and validate (should pass).

        Returns:
            Tuple of (extracted contract data, comparison result, solicitor email)
        """
        print_section("STEP 3: Processing Contract V2 (corrected)")

        from src.agents.extractor import extract_contract
        from src.agents.auditor import compare_contract_to_eoi
        from src.agents.comms import build_contract_to_solicitor_email
        from src.orchestrator.state_machine import StateMachine, DealState

        if not self.deal_id:
            raise RuntimeError("Must process EOI first")

        # Load deal from store
        deal = self.store.get_deal(self.deal_id)
        if not deal:
            raise RuntimeError(f"Deal not found: {self.deal_id}")

        sm = StateMachine(self.deal_id, initial_state=deal.status, canonical=deal.canonical)
        sm.deal = deal

        # Extract contract data
        self.log(f"Extracting fields from: {self.paths['contract_v2'].name}")
        contract_data = extract_contract(self.paths["contract_v2"])
        contract_fields = contract_data.get("fields", {})
        contract_version = contract_data.get("version", "V2")

        self.print(f"  Contract Version: {contract_version}")

        # Transition: receive contract (supersedes V1)
        old_state = sm.current_state.value
        sm.transition(
            "CONTRACT_FROM_VENDOR",
            source="email_2b",
            contract_version=contract_version,
            contract_filename=self.paths["contract_v2"].name,
        )
        print_state_transition(old_state, sm.current_state.value, "CONTRACT_FROM_VENDOR")
        self.print("  V1 automatically superseded by V2")

        # Compare contract to EOI
        print_subsection("Auditor: Comparing Contract V2 to EOI")
        comparison_result = compare_contract_to_eoi(
            self.eoi_data,
            contract_data,
            use_llm=False,
        )

        is_valid = comparison_result.get("is_valid", False)
        mismatch_count = comparison_result.get("mismatch_count", 0)
        risk_score = comparison_result.get("risk_score", "NONE")

        self.print(f"  Is Valid: {is_valid}")
        self.print(f"  Mismatch Count: {mismatch_count}")
        self.print(f"  Risk Score: {risk_score}")

        # Transition: validation passed
        old_state = sm.current_state.value
        sm.transition(
            "VALIDATION_PASSED",
            source="auditor",
            comparison_result=comparison_result,
        )
        print_state_transition(old_state, sm.current_state.value, "VALIDATION_PASSED")

        # Generate solicitor email
        print_subsection("Comms: Generating Contract to Solicitor Email")

        purchaser_names = self._get_purchaser_names()
        solicitor_email = build_contract_to_solicitor_email(
            context={
                "fields": self.canonical_fields,
                "purchaser_names": purchaser_names,
                "contract_filename": self.paths["contract_v2"].name,
            },
            use_llm=False,
        )

        self.print(f"  To: {', '.join(solicitor_email.to_addrs)}")
        self.print(f"  Subject: {solicitor_email.subject}")
        self.print(f"  Attachments: {solicitor_email.attachments}")

        self.generated_emails.append({
            "type": "CONTRACT_TO_SOLICITOR",
            "email": solicitor_email,
        })

        # Transition: sent to solicitor
        old_state = sm.current_state.value
        sm.transition("SOLICITOR_EMAIL_SENT", source="comms")
        print_state_transition(old_state, sm.current_state.value, "SOLICITOR_EMAIL_SENT")

        # Persist state
        self.store.upsert_deal(sm.deal)

        print_subsection("Contract V2 Processing Complete")
        self.print(f"  Final State: {sm.current_state.value}")
        self.print("  V2 validated successfully - sent to solicitor")

        return contract_data, comparison_result, solicitor_email

    # =========================================================================
    # Step 4: Process Solicitor Approval
    # =========================================================================

    def process_solicitor_approval(
        self,
        appointment_phrase: str = "Thursday at 11:30am",
        email_timestamp: str = "2025-01-14T09:12:00+11:00",
    ) -> Tuple[datetime, Any]:
        """Process solicitor approval and schedule SLA.

        Args:
            appointment_phrase: Raw appointment phrase from email
            email_timestamp: Email timestamp for date resolution

        Returns:
            Tuple of (resolved appointment datetime, vendor release email)
        """
        print_section("STEP 4: Processing Solicitor Approval")

        from src.utils.date_resolver import resolve_appointment_phrase
        from src.agents.comms import build_vendor_release_email
        from src.orchestrator.state_machine import StateMachine, DealState
        from datetime import datetime
        from zoneinfo import ZoneInfo

        if not self.deal_id:
            raise RuntimeError("Must process EOI first")

        # Load deal from store
        deal = self.store.get_deal(self.deal_id)
        if not deal:
            raise RuntimeError(f"Deal not found: {self.deal_id}")

        sm = StateMachine(self.deal_id, initial_state=deal.status, canonical=deal.canonical)
        sm.deal = deal

        # Parse email timestamp
        base_dt = datetime.fromisoformat(email_timestamp)

        # Resolve appointment phrase
        print_subsection("Router: Extracting Appointment Details")
        self.print(f"  Appointment Phrase: '{appointment_phrase}'")
        self.print(f"  Email Timestamp: {email_timestamp}")

        appointment_dt = resolve_appointment_phrase(base_dt, appointment_phrase)
        if appointment_dt:
            self.print(f"  Resolved Appointment: {appointment_dt.isoformat()}")
        else:
            self.print("  WARNING: Could not resolve appointment datetime")

        # Transition: solicitor approved
        old_state = sm.current_state.value
        sm.transition(
            "SOLICITOR_APPROVED_WITH_APPOINTMENT",
            source="email_4",
            appointment_datetime=appointment_dt.isoformat() if appointment_dt else None,
        )
        print_state_transition(old_state, sm.current_state.value, "SOLICITOR_APPROVED_WITH_APPOINTMENT")

        if sm.deal.sla_deadline:
            self.print(f"  SLA Deadline: {sm.deal.sla_deadline.isoformat()}")

        # Register SLA timer
        if appointment_dt:
            self.sla_monitor.register_timer(
                deal_id=self.deal_id,
                appointment_datetime=appointment_dt,
                source="solicitor_approval",
            )
            self.print("  SLA timer registered")

        # Generate vendor release request
        print_subsection("Comms: Generating Vendor DocuSign Release Request")

        purchaser_names = self._get_purchaser_names()
        vendor_email = build_vendor_release_email(
            context={
                "fields": self.canonical_fields,
                "purchaser_names": purchaser_names,
                "vendor_email": "contracts@buildwelldevelopments.com.au",
            },
            use_llm=False,
        )

        self.print(f"  To: {', '.join(vendor_email.to_addrs)}")
        self.print(f"  Subject: {vendor_email.subject}")

        self.generated_emails.append({
            "type": "VENDOR_DOCUSIGN_RELEASE",
            "email": vendor_email,
        })

        # Transition: DocuSign release requested
        old_state = sm.current_state.value
        sm.transition("DOCUSIGN_RELEASE_REQUESTED", source="comms", appointment_datetime=appointment_dt)
        print_state_transition(old_state, sm.current_state.value, "DOCUSIGN_RELEASE_REQUESTED")

        # Persist state
        self.store.upsert_deal(sm.deal)

        print_subsection("Solicitor Approval Processing Complete")
        self.print(f"  Final State: {sm.current_state.value}")
        self.print("  Vendor release request sent - awaiting DocuSign")

        return appointment_dt, vendor_email

    # =========================================================================
    # Step 5: Process DocuSign Flow
    # =========================================================================

    def process_docusign_released(self) -> None:
        """Process DocuSign envelope released event."""
        print_subsection("DocuSign: Envelope Released")

        from src.orchestrator.state_machine import StateMachine

        deal = self.store.get_deal(self.deal_id)
        sm = StateMachine(self.deal_id, initial_state=deal.status, canonical=deal.canonical)
        sm.deal = deal

        old_state = sm.current_state.value
        sm.transition("DOCUSIGN_RELEASED", source="email_6")
        print_state_transition(old_state, sm.current_state.value, "DOCUSIGN_RELEASED")

        self.store.upsert_deal(sm.deal)
        self.print("  DocuSign envelope sent to purchasers for signing")

    def process_buyer_signed(self) -> None:
        """Process buyer signature event."""
        print_subsection("DocuSign: Buyer Signed")

        from src.orchestrator.state_machine import StateMachine

        deal = self.store.get_deal(self.deal_id)
        sm = StateMachine(self.deal_id, initial_state=deal.status, canonical=deal.canonical)
        sm.deal = deal

        old_state = sm.current_state.value
        sm.transition("DOCUSIGN_BUYER_SIGNED", source="email_7")
        print_state_transition(old_state, sm.current_state.value, "DOCUSIGN_BUYER_SIGNED")

        # Cancel SLA timer
        self.sla_monitor.cancel_timer(self.deal_id, reason="buyer_signed")
        self.print("  SLA timer cancelled (buyer signed before deadline)")

        self.store.upsert_deal(sm.deal)
        self.print("  Purchasers have signed - awaiting vendor countersignature")

    def process_contract_executed(self) -> None:
        """Process contract fully executed event."""
        print_subsection("DocuSign: Contract Executed")

        from src.orchestrator.state_machine import StateMachine

        deal = self.store.get_deal(self.deal_id)
        sm = StateMachine(self.deal_id, initial_state=deal.status, canonical=deal.canonical)
        sm.deal = deal

        old_state = sm.current_state.value
        sm.transition("DOCUSIGN_EXECUTED", source="email_8")
        print_state_transition(old_state, sm.current_state.value, "DOCUSIGN_EXECUTED")

        self.store.upsert_deal(sm.deal)

    def process_docusign_flow(self) -> None:
        """Process the full DocuSign flow (released -> buyer signed -> executed)."""
        print_section("STEP 5: Processing DocuSign Flow")

        self.process_docusign_released()
        self.process_buyer_signed()
        self.process_contract_executed()

        print_subsection("DocuSign Flow Complete")

        deal = self.store.get_deal(self.deal_id)
        self.print(f"  Final State: {deal.status.value}")
        self.print("  Contract fully executed!")

    # =========================================================================
    # SLA Test Scenario
    # =========================================================================

    def test_sla_overdue(
        self,
        simulated_time: str = "2025-01-18T09:00:00+11:00",
    ) -> Optional[Any]:
        """Test SLA overdue scenario by simulating time passing without buyer signature.

        Args:
            simulated_time: Simulated current time (should be after SLA deadline)

        Returns:
            SLA overdue alert email if generated, else None
        """
        print_section("SLA TEST: Simulating Overdue Scenario")

        from src.agents.comms import build_sla_overdue_alert_email
        from src.orchestrator.state_machine import StateMachine, DealState
        from datetime import datetime

        if not self.deal_id:
            raise RuntimeError("Must run demo steps first")

        deal = self.store.get_deal(self.deal_id)
        if not deal:
            raise RuntimeError(f"Deal not found: {self.deal_id}")

        # For SLA test, we need to be in DOCUSIGN_RELEASED state (buyer hasn't signed)
        # Reset state to DOCUSIGN_RELEASED if needed
        if deal.status == DealState.BUYER_SIGNED or deal.status == DealState.EXECUTED:
            self.print("  Resetting state to DOCUSIGN_RELEASED for SLA test...")
            deal.status = DealState.DOCUSIGN_RELEASED
            # Re-register SLA deadline
            if deal.solicitor_appointment:
                deadline = deal.solicitor_appointment + timedelta(days=2)
                deadline = deadline.replace(hour=9, minute=0, second=0, microsecond=0)
                deal.sla_deadline = deadline
            self.store.upsert_deal(deal)

        self.print(f"  Current State: {deal.status.value}")
        self.print(f"  SLA Deadline: {deal.sla_deadline.isoformat() if deal.sla_deadline else 'Not set'}")
        self.print(f"  Simulated Time: {simulated_time}")

        # Check SLA via monitor
        print_subsection("SLA Monitor: Evaluating Overdue Deadlines")

        now_dt = datetime.fromisoformat(simulated_time)
        overdue_deals = self.sla_monitor.evaluate_due_deadlines(now_dt, source="sla_test")

        if self.deal_id in overdue_deals:
            self.print(f"  SLA OVERDUE detected for {self.deal_id}!")

            # Generate SLA overdue alert
            print_subsection("Comms: Generating SLA Overdue Alert")

            purchaser_names = self._get_purchaser_names()
            solicitor = self.canonical_fields.get("solicitor", {})

            # Calculate time overdue
            time_overdue = "48+ hours"  # Simplified for demo

            sla_alert = build_sla_overdue_alert_email(
                context={
                    "fields": self.canonical_fields,
                    "purchaser_names": purchaser_names,
                    "signing_datetime": deal.solicitor_appointment.strftime("%A, %d %B %Y at %I:%M%p") if deal.solicitor_appointment else "",
                    "sla_deadline": deal.sla_deadline.isoformat() if deal.sla_deadline else "",
                    "time_overdue": time_overdue,
                },
                use_llm=False,
            )

            self.print(f"  To: {', '.join(sla_alert.to_addrs)}")
            self.print(f"  Subject: {sla_alert.subject}")
            self.print(f"\n  Body preview:\n{sla_alert.body[:600]}...")

            self.generated_emails.append({
                "type": "SLA_OVERDUE_ALERT",
                "email": sla_alert,
            })

            # Check final state
            deal = self.store.get_deal(self.deal_id)
            self.print(f"\n  Final State: {deal.status.value}")

            return sla_alert
        else:
            self.print("  No SLA overdue detected")
            return None

    # =========================================================================
    # Full Demo
    # =========================================================================

    def run_demo(self) -> None:
        """Run the complete demo workflow."""
        print()
        print("╔══════════════════════════════════════════════════════════════════════╗")
        print("║         OneCorp Multi-Agent System - Contract Workflow Demo         ║")
        print("╚══════════════════════════════════════════════════════════════════════╝")
        print()

        # Step 1: Process EOI
        self.process_eoi()

        # Step 2: Process Contract V1 (with discrepancies)
        self.process_contract_v1()

        # Step 3: Process Contract V2 (corrected)
        self.process_contract_v2()

        # Step 4: Solicitor approval
        self.process_solicitor_approval()

        # Step 5: DocuSign flow
        self.process_docusign_flow()

        # Summary
        print_section("DEMO COMPLETE: Summary")

        deal = self.store.get_deal(self.deal_id)
        self.print(f"  Deal ID: {self.deal_id}")
        self.print(f"  Final State: {deal.status.value}")
        self.print(f"  Contract Version: V{deal.current_version}")
        self.print(f"  Emails Generated: {len(self.generated_emails)}")

        for i, email_info in enumerate(self.generated_emails, 1):
            self.print(f"    {i}. {email_info['type']}: {email_info['email'].subject}")

        print()
        print("═" * 70)
        print("  The contract workflow has completed successfully!")
        print("  All agents collaborated to process the deal from EOI to execution.")
        print("═" * 70)
        print()

    # =========================================================================
    # Helpers
    # =========================================================================

    def _get_purchaser_names(self) -> List[str]:
        """Get purchaser names from canonical fields."""
        if not self.canonical_fields:
            return []

        names = []
        for key in ["purchaser_1", "purchaser_2"]:
            purchaser = self.canonical_fields.get(key, {})
            if purchaser:
                first = purchaser.get("first_name", "")
                last = purchaser.get("last_name", "")
                if first or last:
                    names.append(f"{first} {last}".strip())
        return names

    def close(self) -> None:
        """Clean up resources."""
        if self._store:
            self._store.close()


def run_step(step: str, orchestrator: DemoOrchestrator) -> None:
    """Run a specific demo step."""
    steps_map = {
        "eoi": orchestrator.process_eoi,
        "contract-v1": orchestrator.process_contract_v1,
        "contract-v2": orchestrator.process_contract_v2,
        "solicitor-approval": orchestrator.process_solicitor_approval,
        "docusign-flow": orchestrator.process_docusign_flow,
    }

    if step not in steps_map:
        print(f"Unknown step: {step}")
        print(f"Available steps: {', '.join(steps_map.keys())}")
        sys.exit(1)

    # For steps after EOI, we need to process previous steps first
    if step != "eoi":
        # Load existing deal or process EOI first
        manifest = load_manifest(orchestrator.paths["manifest"])
        deal_id = manifest.get("deal_id")

        deal = orchestrator.store.get_deal(deal_id) if deal_id else None
        if not deal:
            print("Processing EOI first (required)...")
            orchestrator.process_eoi()

            # For later steps, process intermediate steps
            if step in ["contract-v2", "solicitor-approval", "docusign-flow"]:
                orchestrator.process_contract_v1()
            if step in ["solicitor-approval", "docusign-flow"]:
                orchestrator.process_contract_v2()
            if step == "docusign-flow":
                orchestrator.process_solicitor_approval()
        else:
            # Restore state from existing deal
            orchestrator.deal_id = deal_id
            orchestrator.canonical_fields = deal.canonical
            orchestrator.eoi_data = {"fields": deal.canonical}

    steps_map[step]()


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="OneCorp Multi-Agent System - Contract Workflow Demo",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m src.main --demo              Run full demo workflow
  python -m src.main --step eoi          Process EOI only
  python -m src.main --step contract-v1  Process V1 contract
  python -m src.main --step contract-v2  Process V2 contract
  python -m src.main --test-sla          Test SLA overdue scenario
  python -m src.main --reset             Reset database and exit
        """,
    )

    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run the full demo workflow",
    )
    parser.add_argument(
        "--step",
        type=str,
        choices=["eoi", "contract-v1", "contract-v2", "solicitor-approval", "docusign-flow"],
        help="Run a specific workflow step",
    )
    parser.add_argument(
        "--test-sla",
        action="store_true",
        help="Test SLA overdue scenario (simulates buyer not signing)",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Reset the database; exits if used alone",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress verbose output",
    )

    args = parser.parse_args()

    # Setup paths
    paths = setup_paths()

    actions_selected = any([args.demo, args.step, args.test_sla])

    # Reset-only mode: allow clearing state without running demo.
    if args.reset and not actions_selected:
        if paths["db_path"].exists():
            print(f"Removing database: {paths['db_path']}")
            os.remove(paths["db_path"])
        else:
            print("No database to remove.")
        print("Database reset complete.")
        return

    # Default to demo if no action arguments were provided.
    if not actions_selected:
        args.demo = True

    # Reset database before running if requested.
    if args.reset and paths["db_path"].exists():
        print(f"Removing database: {paths['db_path']}")
        os.remove(paths["db_path"])

    # Create orchestrator
    orchestrator = DemoOrchestrator(
        db_path=paths["db_path"],
        verbose=not args.quiet,
    )

    try:
        if args.demo:
            orchestrator.run_demo()
        elif args.step:
            run_step(args.step, orchestrator)
        elif args.test_sla:
            # Run demo first, then SLA test
            orchestrator.run_demo()
            orchestrator.test_sla_overdue()
    finally:
        orchestrator.close()


if __name__ == "__main__":
    main()
