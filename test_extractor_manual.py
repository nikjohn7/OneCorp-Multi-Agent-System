"""Quick manual test for extractor agent.

Run this to test the extractor implementation before running full pytest suite.

Usage:
    export DEEPINFRA_API_KEY="your-api-key-here"
    python test_extractor_manual.py
"""

import json
import os
from pathlib import Path

from src.agents.extractor import extract_eoi

# Check API key
if not os.getenv("DEEPINFRA_API_KEY"):
    print("ERROR: DEEPINFRA_API_KEY environment variable not set!")
    print("Please run: export DEEPINFRA_API_KEY='your-api-key-here'")
    exit(1)

print("=" * 80)
print("Testing EOI Extraction")
print("=" * 80)

# Extract EOI
eoi_path = "data/source-of-truth/EOI_John_JaneSmith.pdf"
print(f"\nExtracting from: {eoi_path}")

try:
    result = extract_eoi(eoi_path)
    print("\n✅ Extraction successful!")
    print(f"\nDocument Type: {result['document_type']}")
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
        print(json.dumps(result["confidence_scores"], indent=2))

    if "extraction_notes" in result and result["extraction_notes"]:
        print("\n" + "=" * 80)
        print("Extraction Notes:")
        print("=" * 80)
        for note in result["extraction_notes"]:
            print(f"  - {note}")

    # Load ground truth for comparison
    ground_truth_path = Path("ground-truth/eoi_extracted.json")
    with open(ground_truth_path) as f:
        expected = json.load(f)

    print("\n" + "=" * 80)
    print("Comparison with Ground Truth:")
    print("=" * 80)

    # Compare key fields
    def compare_field(path, actual_val, expected_val):
        """Recursively compare nested fields."""
        if isinstance(expected_val, dict):
            if not isinstance(actual_val, dict):
                print(f"  ❌ {path}: Expected dict, got {type(actual_val).__name__}")
                return False
            all_match = True
            for key, exp_val in expected_val.items():
                act_val = actual_val.get(key)
                if not compare_field(f"{path}.{key}", act_val, exp_val):
                    all_match = False
            return all_match
        else:
            if actual_val == expected_val:
                print(f"  ✅ {path}: {actual_val}")
                return True
            else:
                print(f"  ❌ {path}: Expected {expected_val}, got {actual_val}")
                return False

    all_match = True
    for key, expected_val in expected["fields"].items():
        actual_val = result["fields"].get(key)
        if not compare_field(key, actual_val, expected_val):
            all_match = False

    if all_match:
        print("\n🎉 All fields match ground truth!")
    else:
        print("\n⚠️  Some fields don't match ground truth (see above)")

except Exception as e:
    print(f"\n❌ Extraction failed: {str(e)}")
    import traceback
    traceback.print_exc()
    exit(1)
