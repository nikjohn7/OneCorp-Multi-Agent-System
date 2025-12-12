"""Optional integration test for the Auditor LLM path.

This test calls the real DeepInfra API with the Qwen3 model. It is skipped by
default to avoid network usage, costs, and flakiness in CI. To run:

    AUDITOR_DISABLE_LLM=0 RUN_LLM_TESTS=1 pytest tests/test_auditor_llm_integration.py -q

Requires DEEPINFRA_API_KEY to be set in the environment.
"""

from __future__ import annotations

import os
from typing import Any, Dict

import pytest

from src.agents.auditor import compare_contract_to_eoi


@pytest.mark.integration
def test_qwen_llm_comparison_executes(
    eoi_extracted: Dict[str, Any],
    v2_extracted: Dict[str, Any],
) -> None:
    """Calls Qwen3 Auditor via DeepInfra and returns a valid shape."""
    if os.getenv("RUN_LLM_TESTS", "").lower() not in {"1", "true", "yes"}:
        pytest.skip("Set RUN_LLM_TESTS=1 to enable real API call.")

    if not os.getenv("DEEPINFRA_API_KEY"):
        pytest.skip("DEEPINFRA_API_KEY not set.")

    # Ensure LLM is enabled for this test.
    os.environ.pop("AUDITOR_DISABLE_LLM", None)

    result = compare_contract_to_eoi(eoi_extracted, v2_extracted, use_llm="llm")

    assert isinstance(result, dict)
    # Basic schema checks.
    assert "mismatches" in result and isinstance(result["mismatches"], list)
    assert "is_valid" in result and isinstance(result["is_valid"], bool)
    assert "risk_score" in result and result["risk_score"] in {"NONE", "LOW", "MEDIUM", "HIGH"}


@pytest.mark.integration
def test_qwen_llm_comparison_flags_v1_discrepancies(
    eoi_extracted: Dict[str, Any],
    v1_extracted: Dict[str, Any],
) -> None:
    """Calls Qwen3 Auditor on V1 and expects discrepancies in a stable way."""
    if os.getenv("RUN_LLM_TESTS", "").lower() not in {"1", "true", "yes"}:
        pytest.skip("Set RUN_LLM_TESTS=1 to enable real API call.")

    if not os.getenv("DEEPINFRA_API_KEY"):
        pytest.skip("DEEPINFRA_API_KEY not set.")

    os.environ.pop("AUDITOR_DISABLE_LLM", None)

    result = compare_contract_to_eoi(eoi_extracted, v1_extracted, use_llm="llm")

    assert isinstance(result, dict)
    assert result.get("is_valid") is False
    assert "mismatches" in result and isinstance(result["mismatches"], list)
    assert 1 <= result.get("mismatch_count", len(result["mismatches"])) <= 10

    # Should include at least one high-severity critical mismatch.
    high_fields = {
        m.get("field")
        for m in result["mismatches"]
        if m.get("severity") == "HIGH"
    }
    assert any(
        f in high_fields
        for f in {"property.lot_number", "pricing.total_price", "finance.is_subject_to_finance"}
    )
