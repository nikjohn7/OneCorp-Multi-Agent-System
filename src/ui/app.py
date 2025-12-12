#!/usr/bin/env python3
"""Flask web application for visualizing the OneCorp MAS workflow.

This module provides a real-time visual dashboard showing:
- Workflow state progression
- Agent activities
- Email generation
- Mismatch detection
"""

from __future__ import annotations

import json
import os
import queue
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional

from flask import Flask, Response, jsonify, render_template, request

# Project root
PROJECT_ROOT = Path(__file__).parent.parent.parent

app = Flask(__name__, template_folder=str(PROJECT_ROOT / "src" / "ui" / "templates"))

# Global event queue for SSE
event_queue: queue.Queue = queue.Queue()

# Global state for demo tracking
demo_state = {
    "current_step": 0,
    "current_phase": "idle",
    "deal_id": None,
    "state": None,
    "events": [],
    "emails": [],
    "mismatches": [],
    "agents_active": [],
    "is_running": False,
    "error": None,
}


def emit_event(event_type: str, data: Dict[str, Any]) -> None:
    """Emit an event to all connected SSE clients."""
    event_data = {
        "type": event_type,
        "data": data,
        "timestamp": datetime.now().isoformat(),
    }
    event_queue.put(event_data)


def reset_demo_state() -> None:
    """Reset demo state for a fresh run."""
    global demo_state
    demo_state = {
        "current_step": 0,
        "current_phase": "idle",
        "deal_id": None,
        "state": None,
        "events": [],
        "emails": [],
        "mismatches": [],
        "agents_active": [],
        "is_running": False,
        "error": None,
    }


class UIOrchestrator:
    """Orchestrator that emits events for UI visualization."""

    def __init__(self):
        self.demo = None
        self._lock = threading.Lock()

    def emit_step_start(self, step: int, name: str, description: str) -> None:
        """Emit step start event."""
        demo_state["current_step"] = step
        demo_state["current_phase"] = name
        emit_event("step_start", {
            "step": step,
            "name": name,
            "description": description,
        })

    def emit_step_complete(self, step: int, name: str) -> None:
        """Emit step complete event."""
        emit_event("step_complete", {
            "step": step,
            "name": name,
        })

    def emit_agent_active(self, agent: str, task: str) -> None:
        """Emit agent activation event."""
        if agent not in demo_state["agents_active"]:
            demo_state["agents_active"].append(agent)
        emit_event("agent_active", {
            "agent": agent,
            "task": task,
        })

    def emit_agent_complete(self, agent: str, result: Optional[str] = None) -> None:
        """Emit agent completion event."""
        if agent in demo_state["agents_active"]:
            demo_state["agents_active"].remove(agent)
        emit_event("agent_complete", {
            "agent": agent,
            "result": result,
        })

    def emit_state_change(self, old_state: str, new_state: str, event: str) -> None:
        """Emit state transition event."""
        demo_state["state"] = new_state
        event_data = {
            "old_state": old_state,
            "new_state": new_state,
            "event": event,
            "timestamp": datetime.now().isoformat(),
        }
        demo_state["events"].append(event_data)
        emit_event("state_change", event_data)

    def emit_mismatch(self, mismatch: Dict[str, Any]) -> None:
        """Emit mismatch detection event."""
        demo_state["mismatches"].append(mismatch)
        emit_event("mismatch", mismatch)

    def emit_email_generated(self, email_type: str, subject: str, recipients: List[str]) -> None:
        """Emit email generation event."""
        email_data = {
            "type": email_type,
            "subject": subject,
            "recipients": recipients,
            "timestamp": datetime.now().isoformat(),
        }
        demo_state["emails"].append(email_data)
        emit_event("email_generated", email_data)

    def emit_deal_created(self, deal_id: str, property_info: str) -> None:
        """Emit deal creation event."""
        demo_state["deal_id"] = deal_id
        emit_event("deal_created", {
            "deal_id": deal_id,
            "property": property_info,
        })

    def emit_sla_registered(self, deadline: str, appointment: str) -> None:
        """Emit SLA timer registration event."""
        emit_event("sla_registered", {
            "deadline": deadline,
            "appointment": appointment,
        })

    def emit_sla_alert(self, deal_id: str, deadline: str) -> None:
        """Emit SLA overdue alert event."""
        emit_event("sla_alert", {
            "deal_id": deal_id,
            "deadline": deadline,
        })

    def emit_demo_complete(self) -> None:
        """Emit demo completion event."""
        demo_state["is_running"] = False
        demo_state["current_phase"] = "complete"
        emit_event("demo_complete", {
            "deal_id": demo_state["deal_id"],
            "final_state": demo_state["state"],
            "emails_generated": len(demo_state["emails"]),
        })

    def emit_error(self, error: str) -> None:
        """Emit error event."""
        demo_state["error"] = error
        demo_state["is_running"] = False
        emit_event("error", {"message": error})

    def run_demo(self) -> None:
        """Run the full demo with UI events."""
        from src.main import DemoOrchestrator, setup_paths

        reset_demo_state()
        demo_state["is_running"] = True
        emit_event("demo_start", {})

        try:
            paths = setup_paths()
            db_path = paths["db_path"]

            # Remove existing database for fresh run
            if db_path.exists():
                os.remove(db_path)

            self.demo = DemoOrchestrator(db_path=db_path, verbose=False)

            # Step 1: Process EOI
            self._run_step_1()

            # Step 2: Process Contract V1
            self._run_step_2()

            # Step 3: Process Contract V2
            self._run_step_3()

            # Step 4: Solicitor Approval
            self._run_step_4()

            # Step 5: DocuSign Flow
            self._run_step_5()

            # Complete
            self.emit_demo_complete()

        except Exception as e:
            self.emit_error(str(e))
            raise
        finally:
            if self.demo:
                self.demo.close()

    def run_sla_test(self) -> None:
        """Run SLA overdue test."""
        if not self.demo or not demo_state["deal_id"]:
            self.emit_error("Must run demo first before SLA test")
            return

        emit_event("sla_test_start", {})

        try:
            # Re-initialize demo to run SLA test
            from src.main import DemoOrchestrator, setup_paths

            paths = setup_paths()
            demo = DemoOrchestrator(db_path=paths["db_path"], verbose=False)

            # Restore state
            demo.deal_id = demo_state["deal_id"]
            deal = demo.store.get_deal(demo.deal_id)
            if deal:
                demo.canonical_fields = deal.canonical
                demo.eoi_data = {"fields": deal.canonical}

            self.emit_step_start(6, "sla_test", "Testing SLA Overdue Scenario")
            self.emit_agent_active("SLA Monitor", "Evaluating deadlines")
            time.sleep(0.5)

            result = demo.test_sla_overdue()
            self.emit_agent_complete("SLA Monitor", "SLA overdue detected")

            if result:
                self.emit_sla_alert(demo.deal_id, "2025-01-18T09:00:00+11:00")
                self.emit_email_generated(
                    "SLA_OVERDUE_ALERT",
                    result.subject,
                    result.to_addrs,
                )

            self.emit_step_complete(6, "sla_test")
            emit_event("sla_test_complete", {"alert_sent": result is not None})

            demo.close()

        except Exception as e:
            self.emit_error(str(e))

    def _run_step_1(self) -> None:
        """Step 1: Process EOI."""
        self.emit_step_start(1, "eoi", "Processing Expression of Interest")

        self.emit_agent_active("Extractor", "Parsing EOI PDF")
        # Short pause so the UI shows the agent as active before real work starts.
        time.sleep(0.2)

        eoi_data = self.demo.process_eoi()
        fields = eoi_data.get("fields", {})

        property_info = fields.get("property", {})
        lot = property_info.get("lot_number", "")
        address = property_info.get("address", "")

        self.emit_agent_complete("Extractor", f"Extracted {len(fields)} field groups")
        self.emit_deal_created(self.demo.deal_id, f"Lot {lot}, {address}")
        self.emit_state_change("None", "EOI_RECEIVED", "EOI_SIGNED")

        self.emit_step_complete(1, "eoi")

    def _run_step_2(self) -> None:
        """Step 2: Process Contract V1."""
        self.emit_step_start(2, "contract_v1", "Processing Contract V1 (with errors)")

        self.emit_agent_active("Extractor", "Parsing Contract V1 PDF")
        time.sleep(0.3)

        self.emit_agent_complete("Extractor", "Extracted contract fields")

        self.emit_agent_active("Auditor", "Comparing Contract V1 to EOI")
        time.sleep(0.4)

        contract_data, comparison = self.demo.process_contract_v1()

        # Emit state changes
        self.emit_state_change("EOI_RECEIVED", "CONTRACT_V1_RECEIVED", "CONTRACT_FROM_VENDOR")

        # Emit mismatches
        mismatches = comparison.get("mismatches", [])
        self.emit_agent_complete("Auditor", f"Found {len(mismatches)} mismatches")

        for m in mismatches:
            self.emit_mismatch({
                "field": m.get("field_display", m.get("field")),
                "eoi_value": m.get("eoi_value_formatted") or m.get("eoi_value"),
                "contract_value": m.get("contract_value_formatted") or m.get("contract_value"),
                "severity": m.get("severity", "UNKNOWN"),
            })
            time.sleep(0.2)

        self.emit_state_change("CONTRACT_V1_RECEIVED", "CONTRACT_V1_HAS_DISCREPANCIES", "VALIDATION_FAILED")

        self.emit_agent_active("Comms", "Generating discrepancy alert")
        time.sleep(0.5)

        # Find the generated email
        for email_info in self.demo.generated_emails:
            if email_info["type"] == "DISCREPANCY_ALERT":
                email = email_info["email"]
                self.emit_email_generated("DISCREPANCY_ALERT", email.subject, email.to_addrs)
                break

        self.emit_agent_complete("Comms", "Discrepancy alert sent")
        self.emit_state_change("CONTRACT_V1_HAS_DISCREPANCIES", "AMENDMENT_REQUESTED", "DISCREPANCY_ALERT_SENT")

        self.emit_step_complete(2, "contract_v1")

    def _run_step_3(self) -> None:
        """Step 3: Process Contract V2."""
        self.emit_step_start(3, "contract_v2", "Processing Contract V2 (corrected)")

        self.emit_agent_active("Extractor", "Parsing Contract V2 PDF")
        time.sleep(0.3)
        self.emit_agent_complete("Extractor", "Extracted contract fields")

        self.emit_agent_active("Auditor", "Comparing Contract V2 to EOI")
        time.sleep(0.4)

        contract_data, comparison, solicitor_email = self.demo.process_contract_v2()

        self.emit_state_change("AMENDMENT_REQUESTED", "CONTRACT_V2_RECEIVED", "CONTRACT_FROM_VENDOR")
        self.emit_agent_complete("Auditor", "V2 validated successfully - no mismatches")

        self.emit_state_change("CONTRACT_V2_RECEIVED", "CONTRACT_V2_VALIDATED_OK", "VALIDATION_PASSED")

        self.emit_agent_active("Comms", "Generating solicitor email")
        time.sleep(0.4)

        self.emit_email_generated("CONTRACT_TO_SOLICITOR", solicitor_email.subject, solicitor_email.to_addrs)
        self.emit_agent_complete("Comms", "Solicitor email prepared")

        self.emit_state_change("CONTRACT_V2_VALIDATED_OK", "SENT_TO_SOLICITOR", "SOLICITOR_EMAIL_SENT")

        self.emit_step_complete(3, "contract_v2")

    def _run_step_4(self) -> None:
        """Step 4: Solicitor Approval."""
        self.emit_step_start(4, "solicitor", "Processing Solicitor Approval")

        self.emit_agent_active("Router", "Extracting appointment details")
        time.sleep(0.4)

        appointment_dt, vendor_email = self.demo.process_solicitor_approval()

        self.emit_agent_complete("Router", f"Appointment: {appointment_dt.strftime('%a %d %b %Y %H:%M')}")

        self.emit_state_change("SENT_TO_SOLICITOR", "SOLICITOR_APPROVED", "SOLICITOR_APPROVED_WITH_APPOINTMENT")

        # SLA registration
        sla_deadline = "2025-01-18T09:00:00+11:00"
        self.emit_sla_registered(sla_deadline, appointment_dt.isoformat())

        self.emit_agent_active("Comms", "Generating vendor release request")
        # Give the SLA registration a moment to be seen in the UI.
        time.sleep(0.25)
        time.sleep(0.45)

        self.emit_email_generated("VENDOR_DOCUSIGN_RELEASE", vendor_email.subject, vendor_email.to_addrs)
        self.emit_agent_complete("Comms", "Vendor release request sent")

        self.emit_state_change("SOLICITOR_APPROVED", "DOCUSIGN_RELEASE_REQUESTED", "DOCUSIGN_RELEASE_REQUESTED")

        self.emit_step_complete(4, "solicitor")

    def _run_step_5(self) -> None:
        """Step 5: DocuSign Flow."""
        self.emit_step_start(5, "docusign", "Processing DocuSign Flow")

        # DocuSign Released
        self.emit_agent_active("Router", "Processing DocuSign released email")
        time.sleep(0.4)
        self.demo.process_docusign_released()
        self.emit_agent_complete("Router", "Envelope released")
        self.emit_state_change("DOCUSIGN_RELEASE_REQUESTED", "DOCUSIGN_RELEASED", "DOCUSIGN_RELEASED")

        # Buyer Signed
        time.sleep(0.4)
        self.emit_agent_active("Router", "Processing buyer signed email")
        time.sleep(0.4)
        self.demo.process_buyer_signed()
        self.emit_agent_complete("Router", "Buyers have signed")
        self.emit_state_change("DOCUSIGN_RELEASED", "BUYER_SIGNED", "DOCUSIGN_BUYER_SIGNED")
        emit_event("sla_cancelled", {"reason": "buyer_signed"})

        # Contract Executed
        time.sleep(0.4)
        self.emit_agent_active("Router", "Processing execution email")
        time.sleep(0.4)
        self.demo.process_contract_executed()
        self.emit_agent_complete("Router", "Contract fully executed")
        self.emit_state_change("BUYER_SIGNED", "EXECUTED", "DOCUSIGN_EXECUTED")

        # Brief pause so the final state is visible before completion.
        time.sleep(0.2)
        self.emit_step_complete(5, "docusign")


# Global orchestrator instance
ui_orchestrator = UIOrchestrator()


@app.route("/")
def index():
    """Render main dashboard."""
    return render_template("dashboard.html")


@app.route("/api/state")
def get_state():
    """Get current demo state."""
    return jsonify(demo_state)


@app.route("/api/start", methods=["POST"])
def start_demo():
    """Start demo execution."""
    if demo_state["is_running"]:
        return jsonify({"error": "Demo already running"}), 400

    # Run demo in background thread
    thread = threading.Thread(target=ui_orchestrator.run_demo)
    thread.daemon = True
    thread.start()

    return jsonify({"status": "started"})


@app.route("/api/sla-test", methods=["POST"])
def run_sla_test():
    """Run SLA overdue test."""
    if demo_state["is_running"]:
        return jsonify({"error": "Demo still running"}), 400

    if not demo_state["deal_id"]:
        return jsonify({"error": "Run demo first"}), 400

    # Run SLA test in background thread
    thread = threading.Thread(target=ui_orchestrator.run_sla_test)
    thread.daemon = True
    thread.start()

    return jsonify({"status": "started"})


@app.route("/api/reset", methods=["POST"])
def reset():
    """Reset demo state."""
    reset_demo_state()
    return jsonify({"status": "reset"})


@app.route("/api/events")
def events():
    """Server-Sent Events endpoint for real-time updates."""
    def generate() -> Generator[str, None, None]:
        # Send initial connection event
        yield f"data: {json.dumps({'type': 'connected'})}\n\n"

        while True:
            try:
                # Wait for events with timeout
                event = event_queue.get(timeout=30)
                yield f"data: {json.dumps(event)}\n\n"
            except queue.Empty:
                # Send keepalive ping
                yield f"data: {json.dumps({'type': 'ping'})}\n\n"

    return Response(generate(), mimetype="text/event-stream")


def run_server(host: str = "0.0.0.0", port: int = 5000, debug: bool = False) -> None:
    """Run the Flask server."""
    app.run(host=host, port=port, debug=debug, threaded=True)


if __name__ == "__main__":
    run_server(debug=True)
