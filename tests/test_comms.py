"""Tests for Comms email builders."""

from __future__ import annotations

from typing import Any, Dict

import pytest

from src.agents.comms import (
    build_contract_to_solicitor_email,
    build_vendor_release_email,
    build_discrepancy_alert_email,
    build_sla_overdue_alert_email,
)
from src.agents.auditor import compare_contract_to_eoi


def _basic_context(eoi_extracted: Dict[str, Any], contract_extracted: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "fields": eoi_extracted["fields"],
        "purchaser_names": [
            f"{eoi_extracted['fields']['purchaser_1']['first_name']} {eoi_extracted['fields']['purchaser_1']['last_name']}",
            f"{eoi_extracted['fields']['purchaser_2']['first_name']} {eoi_extracted['fields']['purchaser_2']['last_name']}",
        ],
        "solicitor_email": eoi_extracted["fields"].get("solicitor", {}).get("email"),
        "solicitor_name": eoi_extracted["fields"].get("solicitor", {}).get("contact_name"),
        "vendor_email": "contracts@example.com",
        "contract_filename": contract_extracted.get("source_file", "contract.pdf"),
    }


def test_contract_to_solicitor_matches_template_fields(eoi_extracted, v2_extracted):
    ctx = _basic_context(eoi_extracted, v2_extracted)
    email = build_contract_to_solicitor_email(ctx, use_llm=False)
    text = email.to_text()
    assert "From: support@onecorpaustralia.com.au" in text
    assert "To:" in text
    assert "Contract for Review" in text
    assert "Please find attached the contract" in text
    assert str(eoi_extracted["fields"]["property"]["lot_number"]) in text
    assert eoi_extracted["fields"]["property"]["address"] in text


def test_vendor_release_email_contains_required_phrases(eoi_extracted, v2_extracted):
    ctx = _basic_context(eoi_extracted, v2_extracted)
    email = build_vendor_release_email(ctx, use_llm=False)
    text = email.to_text()
    assert "From: support@onecorpaustralia.com.au" in text
    assert "RE: Contract Request" in text
    assert "solicitor has approved" in text.lower()
    assert "DocuSign" in text
    assert str(eoi_extracted["fields"]["property"]["lot_number"]) in text


def test_discrepancy_alert_lists_mismatches(eoi_extracted, v1_extracted):
    comparison = compare_contract_to_eoi(eoi_extracted, v1_extracted)
    ctx = _basic_context(eoi_extracted, v1_extracted)
    email = build_discrepancy_alert_email(ctx, comparison, use_llm=False)
    text = email.to_text()
    assert "Discrepancy detected" in text
    source_file = comparison["source_file"] if isinstance(comparison, dict) else comparison.source_file
    mismatches = comparison["mismatches"] if isinstance(comparison, dict) else comparison.mismatches
    assert source_file in text
    for mismatch in mismatches:
        if isinstance(mismatch, dict):
            field_display = mismatch.get("field_display") or mismatch.get("field")
            eoi_val = mismatch.get("eoi_value_formatted") or mismatch.get("eoi_value")
            contract_val = mismatch.get("contract_value_formatted") or mismatch.get("contract_value")
        else:
            field_display = mismatch.field_display
            eoi_val = mismatch.eoi_value_formatted or mismatch.eoi_value
            contract_val = mismatch.contract_value_formatted or mismatch.contract_value
        assert field_display in text
        assert str(eoi_val) in text
        assert str(contract_val) in text


def test_sla_overdue_alert_includes_required_sections(eoi_extracted, v2_extracted):
    ctx = _basic_context(eoi_extracted, v2_extracted)
    ctx.update(
        {
            "appointment_phrase": "Thursday at 11:30am",
            "sla_deadline": "2025-01-18 09:00",
            "time_overdue": "2 days",
        }
    )
    email = build_sla_overdue_alert_email(ctx, use_llm=False)
    text = email.to_text()
    assert "SLA overdue" in text
    assert "Signing appointment" in text
    assert "SLA deadline" in text
    assert "Time overdue" in text
    assert "Recommended action" in text
