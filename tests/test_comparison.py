"""Tests for the Auditor comparison logic.

These tests validate that the deterministic comparison between EOI and contract
data produces the expected mismatches, severities, risk scores, and actions.
"""

from __future__ import annotations

import copy
from typing import Any, Dict, List

import pytest

from src.agents.auditor import compare_contract_to_eoi


def _index_mismatches(mismatches: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Index mismatch list by field path."""
    return {m["field"]: m for m in mismatches}


def _normalize_for_contains(text: str) -> str:
    """Normalize text for loose containment checks."""
    text = text.lower()
    text = text.replace("'", "")
    text = "".join(ch if ch.isalnum() or ch.isspace() else " " for ch in text)
    return " ".join(text.split())


_STOPWORDS = {"is", "to", "the", "a", "an", "of", "as", "per"}


def test_v1_comparison_matches_ground_truth(
    monkeypatch: pytest.MonkeyPatch,
    eoi_extracted: Dict[str, Any],
    v1_extracted: Dict[str, Any],
    v1_mismatches: Dict[str, Any],
) -> None:
    """Comparing EOI vs V1 yields expected 5 mismatches and metadata."""
    monkeypatch.setenv("AUDITOR_DISABLE_LLM", "1")

    result = compare_contract_to_eoi(eoi_extracted, v1_extracted, use_llm="deterministic")

    assert result["contract_version"] == "V1"
    assert result["is_valid"] is False
    assert result["risk_score"] == "HIGH"
    assert result["mismatch_count"] == 5
    assert result["next_action"] == "SEND_DISCREPANCY_ALERT"
    assert result["should_send_to_solicitor"] is False

    expected_by_field = _index_mismatches(v1_mismatches["mismatches"])
    actual_by_field = _index_mismatches(result["mismatches"])

    assert set(actual_by_field.keys()) == set(expected_by_field.keys())

    for field_path, expected in expected_by_field.items():
        actual = actual_by_field[field_path]
        assert actual["severity"] == expected["severity"]
        assert actual["eoi_value"] == expected["eoi_value"]
        assert actual["contract_value"] == expected["contract_value"]
        if "eoi_value_formatted" in expected:
            assert actual.get("eoi_value_formatted") == expected["eoi_value_formatted"]
        if "contract_value_formatted" in expected:
            assert actual.get("contract_value_formatted") == expected["contract_value_formatted"]
        assert isinstance(actual.get("rationale"), str) and actual["rationale"]

    # Recommendation should mention all mismatched fields/values.
    recommendation = result.get("amendment_recommendation")
    assert isinstance(recommendation, str) and recommendation.startswith("Request vendor to correct:")
    recommendation_norm = _normalize_for_contains(recommendation)
    for expected in v1_mismatches["mismatches"]:
        expected_norm = _normalize_for_contains(expected["field_display"])
        for word in expected_norm.split():
            assert word in recommendation_norm
        eoi_token = expected.get("eoi_value_formatted") or str(expected["eoi_value"])
        contract_token = expected.get("contract_value_formatted") or str(expected["contract_value"])

        if isinstance(eoi_token, str) and " " in eoi_token:
            for word in _normalize_for_contains(eoi_token).split():
                if word in _STOPWORDS or len(word) <= 2:
                    continue
                assert word in recommendation_norm
        else:
            assert str(eoi_token) in recommendation

        if isinstance(contract_token, str) and " " in contract_token:
            for word in _normalize_for_contains(contract_token).split():
                if word in _STOPWORDS or len(word) <= 2:
                    continue
                assert word in recommendation_norm
        else:
            assert str(contract_token) in recommendation


def test_v2_comparison_has_no_mismatches(
    monkeypatch: pytest.MonkeyPatch,
    eoi_extracted: Dict[str, Any],
    v2_extracted: Dict[str, Any],
) -> None:
    """Comparing EOI vs V2 yields zero mismatches and valid contract."""
    monkeypatch.setenv("AUDITOR_DISABLE_LLM", "1")

    result = compare_contract_to_eoi(eoi_extracted, v2_extracted, use_llm="deterministic")

    assert result["contract_version"] == "V2"
    assert result["is_valid"] is True
    assert result["risk_score"] == "NONE"
    assert result["mismatch_count"] == 0
    assert result["mismatches"] == []
    assert result["next_action"] == "PROCEED_TO_SOLICITOR"
    assert result["should_send_to_solicitor"] is True


def test_auto_mode_no_doubt_behaves_like_deterministic(
    monkeypatch: pytest.MonkeyPatch,
    eoi_extracted: Dict[str, Any],
    v2_extracted: Dict[str, Any],
) -> None:
    """Auto mode should not request review when fields are clear."""
    monkeypatch.setenv("AUDITOR_DISABLE_LLM", "1")

    result = compare_contract_to_eoi(eoi_extracted, v2_extracted, use_llm="auto")

    assert result["is_valid"] is True
    assert result["next_action"] == "PROCEED_TO_SOLICITOR"
    assert result["mismatch_count"] == 0


def test_auto_mode_triggers_llm_on_missing_critical_field(
    monkeypatch: pytest.MonkeyPatch,
    eoi_extracted: Dict[str, Any],
    v2_extracted: Dict[str, Any],
) -> None:
    """Auto mode should escalate when a critical field is missing.

    LLM is disabled in tests, so we expect deterministic fallback with
    REQUEST_HUMAN_REVIEW.
    """
    monkeypatch.setenv("AUDITOR_DISABLE_LLM", "1")

    contract_missing = copy.deepcopy(v2_extracted)
    contract_missing["fields"]["property"].pop("lot_number", None)

    result = compare_contract_to_eoi(eoi_extracted, contract_missing, use_llm="auto")

    assert result["is_valid"] is False
    assert result["next_action"] == "REQUEST_HUMAN_REVIEW"
    assert result["risk_score"] in {"HIGH", "MEDIUM", "LOW"}
    assert result["mismatch_count"] >= 1
