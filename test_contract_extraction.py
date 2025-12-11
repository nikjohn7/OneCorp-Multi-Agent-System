"""Test contract extraction for V1 and V2 contracts.

This script validates extract_contract() against ground truth for both versions.

Usage:
    export DEEPINFRA_API_KEY="your-api-key-here"
    python test_contract_extraction.py
"""

import json
import os
from pathlib import Path

from src.agents.extractor import extract_contract

# Check API key
if not os.getenv("DEEPINFRA_API_KEY"):
    print("ERROR: DEEPINFRA_API_KEY environment variable not set!")
    print("Please run: export DEEPINFRA_API_KEY='your-api-key-here'")
    exit(1)


def compare_field(path, actual_val, expected_val, mismatches):
    """Recursively compare nested fields and track mismatches."""
    if isinstance(expected_val, dict):
        if not isinstance(actual_val, dict):
            mismatch = f"  ❌ {path}: Expected dict, got {type(actual_val).__name__}"
            print(mismatch)
            mismatches.append(mismatch)
            return False
        all_match = True
        for key, exp_val in expected_val.items():
            act_val = actual_val.get(key)
            if not compare_field(f"{path}.{key}", act_val, exp_val, mismatches):
                all_match = False
        return all_match
    else:
        if actual_val == expected_val:
            print(f"  ✅ {path}: {actual_val}")
            return True
        else:
            mismatch = f"  ❌ {path}: Expected {expected_val}, got {actual_val}"
            print(mismatch)
            mismatches.append(mismatch)
            return False


def test_contract(contract_path, ground_truth_path, version_name):
    """Test contract extraction against ground truth."""
    print("=" * 80)
    print(f"Testing {version_name} Contract Extraction")
    print("=" * 80)
    print(f"\nExtracting from: {contract_path}")

    try:
        result = extract_contract(contract_path)
        print(f"\n✅ Extraction successful!")
        print(f"\nDocument Type: {result['document_type']}")
        print(f"Version: {result.get('version', 'N/A')}")
        print(f"Source File: {result['source_file']}")
        print(f"Extracted At: {result['extracted_at']}")

        print("\n" + "=" * 80)
        print("Extracted Fields:")
        print("=" * 80)
        print(json.dumps(result["fields"], indent=2))

        if "confidence_scores" in result:
            print("\n" + "=" * 80)
            print("Confidence Scores:")
            print("=" * 80)
            # Show only low confidence scores (< 0.8) and a summary
            low_confidence = {k: v for k, v in result["confidence_scores"].items() if v < 0.8}
            if low_confidence:
                print("Low confidence fields (< 0.8):")
                print(json.dumps(low_confidence, indent=2))
            else:
                print("✅ All fields have confidence ≥ 0.8")

            avg_confidence = sum(result["confidence_scores"].values()) / len(result["confidence_scores"])
            print(f"\nAverage confidence: {avg_confidence:.2f}")

        if "extraction_notes" in result and result["extraction_notes"]:
            print("\n" + "=" * 80)
            print("Extraction Notes:")
            print("=" * 80)
            for note in result["extraction_notes"]:
                print(f"  - {note}")

        # Load ground truth for comparison
        with open(ground_truth_path) as f:
            expected = json.load(f)

        print("\n" + "=" * 80)
        print(f"Comparison with {version_name} Ground Truth:")
        print("=" * 80)

        mismatches = []
        all_match = True
        for key, expected_val in expected["fields"].items():
            actual_val = result["fields"].get(key)
            if not compare_field(key, actual_val, expected_val, mismatches):
                all_match = False

        print("\n" + "=" * 80)
        print(f"{version_name} Results Summary:")
        print("=" * 80)

        total_fields = sum(1 for _ in json.dumps(expected["fields"]).split(":") if ":" in _) - 1
        matched_fields = total_fields - len(mismatches)

        print(f"Matched fields: {matched_fields}/{total_fields}")

        if all_match:
            print(f"✅ {version_name}: All fields match ground truth!")
            return True
        else:
            print(f"⚠️  {version_name}: {len(mismatches)} field(s) don't match")
            return False

    except Exception as e:
        print(f"\n❌ {version_name} extraction failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


# Test V1 Contract
v1_success = test_contract(
    contract_path="data/contracts/CONTRACT_V1.pdf",
    ground_truth_path="ground-truth/v1_extracted.json",
    version_name="V1"
)

print("\n\n")

# Test V2 Contract
v2_success = test_contract(
    contract_path="data/contracts/CONTRACT_V2.pdf",
    ground_truth_path="ground-truth/v2_extracted.json",
    version_name="V2"
)

# Final summary
print("\n" + "=" * 80)
print("FINAL SUMMARY")
print("=" * 80)
print(f"V1 Contract: {'✅ PASS' if v1_success else '❌ FAIL'}")
print(f"V2 Contract: {'✅ PASS' if v2_success else '❌ FAIL'}")

if v1_success and v2_success:
    print("\n🎉 All contract extractions passed!")
    exit(0)
else:
    print("\n⚠️  Some contract extractions failed")
    exit(1)
