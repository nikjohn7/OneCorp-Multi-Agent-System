"""Tests for the Extractor agent.

This module validates that extract_eoi() and extract_contract() produce
outputs that match the ground truth JSON structures for the demo dataset.
"""

import pytest
from pathlib import Path

from src.agents.extractor import extract_eoi, extract_contract, ExtractionError


# Critical fields that must have high confidence (>= 0.8)
CRITICAL_EOI_FIELDS = [
    "purchaser_1.first_name",
    "purchaser_1.last_name",
    "purchaser_1.email",
    "property.lot_number",
    "pricing.total_price",
    "finance.is_subject_to_finance",
]

CRITICAL_CONTRACT_FIELDS = [
    "purchaser_1.first_name",
    "purchaser_1.last_name",
    "property.lot_number",
    "pricing.total_price",
    "finance.is_subject_to_finance",
]


def get_nested_value(data: dict, path: str):
    """Get a value from a nested dictionary using dot notation.

    Args:
        data: Dictionary to extract from
        path: Dot-separated path (e.g., "purchaser_1.first_name")

    Returns:
        Value at the path, or None if not found
    """
    keys = path.split(".")
    value = data
    for key in keys:
        if isinstance(value, dict):
            value = value.get(key)
        else:
            return None
    return value


def compare_nested_fields(actual: dict, expected: dict, path: str = "fields"):
    """Recursively compare nested fields between actual and expected data.

    Args:
        actual: Actual extracted data
        expected: Expected ground truth data
        path: Current path in the nested structure (for error messages)

    Returns:
        List of tuples (field_path, expected_value, actual_value) for mismatches
    """
    mismatches = []

    for key, expected_value in expected.items():
        current_path = f"{path}.{key}"
        actual_value = actual.get(key)

        if isinstance(expected_value, dict) and isinstance(actual_value, dict):
            # Recursively compare nested dicts
            mismatches.extend(compare_nested_fields(actual_value, expected_value, current_path))
        elif expected_value != actual_value:
            # Values don't match
            mismatches.append((current_path, expected_value, actual_value))

    return mismatches


class TestEOIExtraction:
    """Test extraction from EOI document."""

    def test_extracts_all_required_fields(self, eoi_pdf_path, eoi_extracted):
        """Extractor should extract all fields defined in ground truth."""
        result = extract_eoi(eoi_pdf_path)

        # Check top-level keys
        assert "document_type" in result
        assert "source_file" in result
        assert "fields" in result

        # Check all field groups exist
        expected_fields = eoi_extracted["fields"]
        actual_fields = result["fields"]

        for field_name in expected_fields.keys():
            assert field_name in actual_fields, f"Missing field group: {field_name}"

    def test_document_type_is_eoi(self, eoi_pdf_path):
        """Document type should be 'EOI'."""
        result = extract_eoi(eoi_pdf_path)
        assert result["document_type"] == "EOI"

    def test_version_is_null(self, eoi_pdf_path):
        """EOI documents should have version = null."""
        result = extract_eoi(eoi_pdf_path)
        assert result.get("version") is None

    def test_source_file_is_set(self, eoi_pdf_path):
        """Source file should be set to the PDF filename."""
        result = extract_eoi(eoi_pdf_path)
        assert result["source_file"] == eoi_pdf_path.name

    def test_field_values_match_ground_truth(self, eoi_pdf_path, eoi_extracted):
        """Extracted field values should match ground truth."""
        result = extract_eoi(eoi_pdf_path)

        expected_fields = eoi_extracted["fields"]
        actual_fields = result["fields"]

        # Compare all nested fields
        mismatches = compare_nested_fields(actual_fields, expected_fields)

        # Report all mismatches
        if mismatches:
            error_msg = "Field value mismatches:\n"
            for path, expected, actual in mismatches:
                error_msg += f"  {path}: expected {expected!r}, got {actual!r}\n"
            pytest.fail(error_msg)

    def test_critical_fields_extracted(self, eoi_pdf_path):
        """Critical fields should be present in extraction."""
        result = extract_eoi(eoi_pdf_path)

        for field_path in CRITICAL_EOI_FIELDS:
            value = get_nested_value(result["fields"], field_path)
            assert value is not None, f"Critical field '{field_path}' is missing or None"

    def test_critical_fields_have_high_confidence(self, eoi_pdf_path):
        """Critical fields should have confidence >= 0.8."""
        result = extract_eoi(eoi_pdf_path)

        # Check if confidence_scores exists
        if "confidence_scores" not in result:
            pytest.skip("Extraction does not include confidence_scores")

        confidence_scores = result["confidence_scores"]

        for field_path in CRITICAL_EOI_FIELDS:
            # Get confidence for this field
            confidence = get_nested_value(confidence_scores, field_path)

            if confidence is not None:
                assert confidence >= 0.8, \
                    f"Critical field '{field_path}' has low confidence: {confidence}"

    def test_finance_terms_semantic_parsing(self, eoi_pdf_path, eoi_extracted):
        """Finance terms should be correctly parsed (handles negation)."""
        result = extract_eoi(eoi_pdf_path)

        expected_is_subject = eoi_extracted["fields"]["finance"]["is_subject_to_finance"]
        actual_is_subject = result["fields"]["finance"]["is_subject_to_finance"]

        assert actual_is_subject == expected_is_subject, \
            f"Finance terms misparsed: expected is_subject_to_finance={expected_is_subject}, got {actual_is_subject}"

    def test_numeric_fields_are_numbers(self, eoi_pdf_path):
        """Numeric fields should be extracted as numbers, not strings."""
        result = extract_eoi(eoi_pdf_path)

        fields = result["fields"]

        # Check pricing fields
        assert isinstance(fields["pricing"]["total_price"], (int, float))
        assert isinstance(fields["pricing"]["land_price"], (int, float))
        assert isinstance(fields["pricing"]["build_price"], (int, float))

        # Check deposit fields
        assert isinstance(fields["deposits"]["eoi_deposit"], (int, float))
        assert isinstance(fields["deposits"]["build_deposit"], (int, float))
        assert isinstance(fields["deposits"]["balance_deposit"], (int, float))
        assert isinstance(fields["deposits"]["total_deposit"], (int, float))

    def test_boolean_fields_are_booleans(self, eoi_pdf_path):
        """Boolean fields should be extracted as booleans, not strings."""
        result = extract_eoi(eoi_pdf_path)

        is_subject = result["fields"]["finance"]["is_subject_to_finance"]
        assert isinstance(is_subject, bool), \
            f"is_subject_to_finance should be bool, got {type(is_subject)}"


class TestContractExtraction:
    """Test extraction from contract documents."""

    def test_v1_extraction_matches_ground_truth(self, contract_v1_pdf_path, v1_extracted):
        """V1 extraction should match ground truth (including errors in the contract)."""
        result = extract_contract(contract_v1_pdf_path)

        expected_fields = v1_extracted["fields"]
        actual_fields = result["fields"]

        # Compare all nested fields
        mismatches = compare_nested_fields(actual_fields, expected_fields)

        # Report all mismatches
        if mismatches:
            error_msg = "V1 field value mismatches:\n"
            for path, expected, actual in mismatches:
                error_msg += f"  {path}: expected {expected!r}, got {actual!r}\n"
            pytest.fail(error_msg)

    def test_v2_extraction_matches_ground_truth(self, contract_v2_pdf_path, v2_extracted):
        """V2 extraction should match ground truth."""
        result = extract_contract(contract_v2_pdf_path)

        expected_fields = v2_extracted["fields"]
        actual_fields = result["fields"]

        # Compare all nested fields
        mismatches = compare_nested_fields(actual_fields, expected_fields)

        # Report all mismatches
        if mismatches:
            error_msg = "V2 field value mismatches:\n"
            for path, expected, actual in mismatches:
                error_msg += f"  {path}: expected {expected!r}, got {actual!r}\n"
            pytest.fail(error_msg)

    def test_detects_document_version(self, contract_v1_pdf_path, contract_v2_pdf_path):
        """Extractor should correctly identify contract version."""
        v1_result = extract_contract(contract_v1_pdf_path)
        v2_result = extract_contract(contract_v2_pdf_path)

        assert v1_result.get("version") == "V1", \
            f"V1 contract should have version='V1', got {v1_result.get('version')}"
        assert v2_result.get("version") == "V2", \
            f"V2 contract should have version='V2', got {v2_result.get('version')}"

    def test_document_type_is_contract(self, contract_v1_pdf_path):
        """Document type should be 'CONTRACT'."""
        result = extract_contract(contract_v1_pdf_path)
        assert result["document_type"] == "CONTRACT"

    def test_source_file_is_set(self, contract_v1_pdf_path):
        """Source file should be set to the PDF filename."""
        result = extract_contract(contract_v1_pdf_path)
        assert result["source_file"] == contract_v1_pdf_path.name

    def test_v1_extracts_incorrect_values(self, contract_v1_pdf_path, v1_extracted):
        """V1 should extract the INCORRECT values that appear in the faulty contract.

        This test validates that the extractor accurately extracts what's in the
        document, even when those values are wrong. The Auditor will detect these
        discrepancies later.
        """
        result = extract_contract(contract_v1_pdf_path)

        # V1 has incorrect lot number (59 instead of 95)
        assert result["fields"]["property"]["lot_number"] == "59", \
            "Should extract incorrect lot number from V1"

        # V1 has incorrect email for purchaser_2
        assert result["fields"]["purchaser_2"]["email"] == "jane.smith@outlook.com", \
            "Should extract incorrect email from V1"

        # V1 has incorrect finance terms
        assert result["fields"]["finance"]["is_subject_to_finance"] == True, \
            "Should extract incorrect finance terms from V1"

    def test_v2_extracts_correct_values(self, contract_v2_pdf_path, eoi_extracted):
        """V2 should extract the CORRECT values that match the EOI.

        This validates that V2 is the corrected version.
        """
        result = extract_contract(contract_v2_pdf_path)

        # V2 should have correct lot number (95)
        assert result["fields"]["property"]["lot_number"] == "95", \
            "V2 should have correct lot number"

        # V2 should have correct email for purchaser_2
        assert result["fields"]["purchaser_2"]["email"] == "janesmith@gmail.com", \
            "V2 should have correct email"

        # V2 should have correct finance terms
        assert result["fields"]["finance"]["is_subject_to_finance"] == False, \
            "V2 should have correct finance terms"

    def test_vendor_field_extracted(self, contract_v1_pdf_path):
        """Contract should have vendor field (not present in EOI)."""
        result = extract_contract(contract_v1_pdf_path)

        assert "vendor" in result["fields"], "Contract missing vendor field"

        vendor = result["fields"]["vendor"]
        assert "name" in vendor
        assert "acn" in vendor
        assert "address" in vendor

    def test_critical_fields_extracted(self, contract_v1_pdf_path):
        """Critical fields should be present in extraction."""
        result = extract_contract(contract_v1_pdf_path)

        for field_path in CRITICAL_CONTRACT_FIELDS:
            value = get_nested_value(result["fields"], field_path)
            assert value is not None, f"Critical field '{field_path}' is missing or None"

    def test_critical_fields_have_high_confidence(self, contract_v1_pdf_path):
        """Critical fields should have confidence >= 0.8."""
        result = extract_contract(contract_v1_pdf_path)

        # Check if confidence_scores exists
        if "confidence_scores" not in result:
            pytest.skip("Extraction does not include confidence_scores")

        confidence_scores = result["confidence_scores"]

        for field_path in CRITICAL_CONTRACT_FIELDS:
            # Get confidence for this field
            confidence = get_nested_value(confidence_scores, field_path)

            if confidence is not None:
                assert confidence >= 0.8, \
                    f"Critical field '{field_path}' has low confidence: {confidence}"


class TestExtractionErrorHandling:
    """Test error handling for extraction failures."""

    def test_missing_pdf_raises_error(self):
        """Extracting from non-existent PDF should raise ExtractionError."""
        with pytest.raises((ExtractionError, FileNotFoundError)):
            extract_eoi("/nonexistent/path.pdf")

    def test_invalid_pdf_raises_error(self, tmp_path):
        """Extracting from invalid PDF should raise ExtractionError."""
        # Create a fake PDF file with invalid content
        fake_pdf = tmp_path / "fake.pdf"
        fake_pdf.write_text("This is not a PDF")

        with pytest.raises(ExtractionError):
            extract_eoi(fake_pdf)
