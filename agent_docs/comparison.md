# Comparison Guide

## Overview

The Auditor agent compares extracted contract fields against EOI fields (source of truth), detects mismatches, assigns severity levels, calculates risk scores, and generates amendment recommendations. The logic is **field-driven and generalizable**—it compares any contract against any EOI using consistent rules.

---

## Part 1: Implementation Logic (Generalizable)

### Comparison Algorithm

```python
def compare_contract_to_eoi(
    eoi_data: Dict[str, Any], 
    contract_data: Dict[str, Any]
) -> ComparisonResult:
    """
    Compare all fields between EOI (source of truth) and contract.
    Returns mismatches with severity classification.
    """
    mismatches = []
    
    for field_name in COMPARABLE_FIELDS:
        eoi_value = eoi_data.get(field_name)
        contract_value = contract_data.get(field_name)
        
        if not values_match(field_name, eoi_value, contract_value):
            mismatches.append(Mismatch(
                field=field_name,
                eoi_value=eoi_value,
                contract_value=contract_value,
                severity=get_severity(field_name)
            ))
    
    return ComparisonResult(
        is_valid=len(mismatches) == 0,
        mismatches=mismatches,
        risk_score=calculate_risk_score(mismatches),
        amendment_recommendation=generate_recommendation(mismatches) if mismatches else None
    )
```

### Field Comparison Rules

Different field types require different comparison logic:

#### Numeric Fields (Exact Match)

```python
def compare_numeric(eoi_value: int, contract_value: int) -> bool:
    """Numeric fields must match exactly."""
    return eoi_value == contract_value

# Applies to: total_price, land_price, build_price, deposits
```

#### String Fields (Normalized Match)

```python
def compare_string(eoi_value: str, contract_value: str, strict: bool = False) -> bool:
    """
    String comparison with normalization.
    
    strict=True: Exact match after normalization (for emails)
    strict=False: Case-insensitive, whitespace-normalized (for names)
    """
    eoi_normalized = eoi_value.strip()
    contract_normalized = contract_value.strip()
    
    if strict:
        return eoi_normalized == contract_normalized
    else:
        return eoi_normalized.lower() == contract_normalized.lower()

# strict=True: purchaser_email_N, solicitor_email
# strict=False: purchaser_first_name_N, purchaser_last_name_N, solicitor_name
```

#### Boolean Fields (Semantic Match)

```python
def compare_boolean(eoi_value: bool, contract_value: bool) -> bool:
    """Boolean fields must match exactly."""
    return eoi_value == contract_value

# Applies to: finance_terms
```

#### Lot Number (String, Strict)

```python
def compare_lot_number(eoi_value: str, contract_value: str) -> bool:
    """
    Lot numbers compared as strings after normalization.
    "95" != "59" (transposition error)
    "95" == " 95" (whitespace)
    """
    return str(eoi_value).strip() == str(contract_value).strip()
```

### Severity Classification

Severity is determined by **field type**, not by the specific values:

| Severity | Fields | Rationale |
|----------|--------|-----------|
| **HIGH** | `lot_number` | Wrong lot = wrong property = catastrophic |
| **HIGH** | `total_price` | Financial misrepresentation |
| **HIGH** | `finance_terms` | Legal liability if buyer defaults |
| **MEDIUM** | `build_price` | Financial discrepancy (if total is correct, may be split issue) |
| **MEDIUM** | `land_price` | Financial discrepancy (if total is correct, may be split issue) |
| **LOW** | `purchaser_email_N` | Communication issue, easily corrected |
| **LOW** | `purchaser_mobile_N` | Communication issue, easily corrected |
| **LOW** | `solicitor_email` | Communication issue |

```python
SEVERITY_MAP = {
    'lot_number': 'HIGH',
    'property_address': 'HIGH',
    'total_price': 'HIGH',
    'finance_terms': 'HIGH',
    'purchaser_first_name_1': 'HIGH',
    'purchaser_last_name_1': 'HIGH',
    'purchaser_first_name_2': 'HIGH',
    'purchaser_last_name_2': 'HIGH',
    'build_price': 'MEDIUM',
    'land_price': 'MEDIUM',
    'purchaser_email_1': 'LOW',
    'purchaser_email_2': 'LOW',
    'purchaser_mobile_1': 'LOW',
    'purchaser_mobile_2': 'LOW',
    'solicitor_email': 'LOW',
}

def get_severity(field_name: str) -> str:
    return SEVERITY_MAP.get(field_name, 'LOW')
```

### Risk Score Calculation

```python
def calculate_risk_score(mismatches: List[Mismatch]) -> str:
    """
    Overall risk score based on highest severity mismatch.
    """
    if not mismatches:
        return 'NONE'
    
    severities = [m.severity for m in mismatches]
    
    if 'HIGH' in severities:
        return 'HIGH'
    elif 'MEDIUM' in severities:
        return 'MEDIUM'
    else:
        return 'LOW'

def generate_risk_rationale(mismatches: List[Mismatch]) -> str:
    """Generate human-readable explanation of risk."""
    high_fields = [m.field for m in mismatches if m.severity == 'HIGH']
    
    rationale_parts = []
    
    if 'lot_number' in high_fields:
        rationale_parts.append("lot number mismatch affects title registration")
    if 'total_price' in high_fields:
        rationale_parts.append("price discrepancy has financial implications")
    if 'finance_terms' in high_fields:
        rationale_parts.append("finance term error creates legal liability")
    
    return "; ".join(rationale_parts) if rationale_parts else "Minor discrepancies only"
```

### Amendment Recommendation Generation

```python
def generate_recommendation(mismatches: List[Mismatch]) -> str:
    """
    Generate human-readable amendment instructions.
    Orders by severity (HIGH first).
    """
    # Sort by severity
    severity_order = {'HIGH': 0, 'MEDIUM': 1, 'LOW': 2}
    sorted_mismatches = sorted(mismatches, key=lambda m: severity_order[m.severity])
    
    items = []
    for i, m in enumerate(sorted_mismatches, 1):
        items.append(format_mismatch_instruction(i, m))
    
    return "Request vendor to correct: " + "; ".join(items) + "."

def format_mismatch_instruction(index: int, m: Mismatch) -> str:
    """Format a single mismatch as an instruction."""
    
    if m.field == 'lot_number':
        return f"({index}) lot number from {m.contract_value} to {m.eoi_value}"
    
    elif m.field == 'total_price':
        return f"({index}) total price from ${m.contract_value:,} to ${m.eoi_value:,}"
    
    elif m.field == 'build_price':
        return f"({index}) build price from ${m.contract_value:,} to ${m.eoi_value:,}"
    
    elif m.field == 'land_price':
        return f"({index}) land price from ${m.contract_value:,} to ${m.eoi_value:,}"
    
    elif m.field == 'finance_terms':
        from_text = "Subject to Finance" if m.contract_value else "Not Subject to Finance"
        to_text = "Not Subject to Finance" if not m.eoi_value else "Subject to Finance"
        return f"({index}) finance terms from '{from_text}' to '{to_text}'"
    
    elif 'email' in m.field:
        person = "purchaser" if "purchaser" in m.field else "solicitor"
        return f"({index}) {person} email from {m.contract_value} to {m.eoi_value}"
    
    else:
        return f"({index}) {m.field} from {m.contract_value} to {m.eoi_value}"
```

### Output Schema

```python
@dataclass
class Mismatch:
    field: str
    eoi_value: Any
    contract_value: Any
    severity: str  # "HIGH" | "MEDIUM" | "LOW"

@dataclass
class ComparisonResult:
    contract_version: str
    is_valid: bool
    needs_human_review: bool
    mismatches: List[Mismatch]
    risk_score: str  # "NONE" | "LOW" | "MEDIUM" | "HIGH"
    risk_score_rationale: str
    amendment_recommendation: Optional[str]
```

### Verification Loop (Agent Collaboration)

When a critical field has low extraction confidence or semantic ambiguity:

```python
def compare_with_verification(
    eoi_data: Dict, 
    contract_data: Dict,
    extractor: ExtractorAgent
) -> ComparisonResult:
    """
    Comparison with verification loop for uncertain fields.
    """
    result = compare_contract_to_eoi(eoi_data, contract_data)
    
    for mismatch in result.mismatches:
        # Check if this might be an extraction error
        if mismatch.severity == 'HIGH' and should_verify(mismatch):
            # Request re-extraction
            re_extraction = extractor.re_extract_field(
                document_id=contract_data['document_id'],
                field_name=mismatch.field,
                location_hint=get_location_hint(mismatch.field),
                reason=f"Detected {mismatch.field} mismatch, verifying extraction"
            )
            
            if re_extraction.confidence >= 0.8:
                # Update contract data with verified value
                contract_data[mismatch.field] = re_extraction.normalized_value
            else:
                # Still uncertain - flag for human review
                result.needs_human_review = True
    
    # Re-compare with updated data
    return compare_contract_to_eoi(eoi_data, contract_data)

def should_verify(mismatch: Mismatch) -> bool:
    """Determine if mismatch warrants verification."""
    # Finance terms boolean inversion is a common extraction issue
    if mismatch.field == 'finance_terms':
        return True
    # Lot number transposition (e.g., 95 vs 59) is suspicious
    if mismatch.field == 'lot_number':
        if set(str(mismatch.eoi_value)) == set(str(mismatch.contract_value)):
            return True  # Same digits, different order
    return False
```

### Human Review Triggers

```python
def should_require_human_review(result: ComparisonResult) -> bool:
    """Determine if comparison requires human review before proceeding."""
    
    # Any critical field with extraction confidence < 0.8
    if result.needs_human_review:
        return True
    
    # Multiple HIGH severity mismatches (unusual, might be wrong EOI)
    high_count = sum(1 for m in result.mismatches if m.severity == 'HIGH')
    if high_count >= 3:
        return True
    
    return False
```

---

## Part 2: Demo Validation

### Ground Truth Reference

For the demo dataset, expected comparison outputs are defined in:

| Comparison | Ground Truth File |
|------------|-------------------|
| EOI vs V1 | `ground-truth/v1_mismatches.json` |
| EOI vs V2 | Should produce empty mismatches list |

**These files are test fixtures.** The Auditor should produce matching results when comparing the demo documents.

### Expected Demo Behavior

When the Auditor processes the demo dataset:

**V1 Contract:**
- Should detect multiple mismatches (exact count in `v1_mismatches.json`)
- Should return `is_valid = false`
- Should return `risk_score = "HIGH"` (because HIGH-severity fields are affected)
- Should generate an amendment recommendation

**V2 Contract:**
- Should detect zero mismatches
- Should return `is_valid = true`
- Should return `risk_score = "NONE"`
- Should not generate an amendment recommendation

### Validation Test Pattern

```python
def test_v1_comparison_matches_ground_truth():
    """Auditor should detect expected mismatches for V1."""
    
    # Load data
    eoi = load_json('ground-truth/eoi_extracted.json')
    v1 = load_json('ground-truth/v1_extracted.json')
    expected_mismatches = load_json('ground-truth/v1_mismatches.json')
    
    # Run comparison
    result = compare_contract_to_eoi(eoi, v1)
    
    # Verify mismatch count
    assert len(result.mismatches) == len(expected_mismatches)
    
    # Verify each expected mismatch is found
    found_fields = {m.field for m in result.mismatches}
    expected_fields = {m['field'] for m in expected_mismatches}
    assert found_fields == expected_fields

def test_v2_has_no_mismatches():
    """V2 should validate cleanly against EOI."""
    
    eoi = load_json('ground-truth/eoi_extracted.json')
    v2 = load_json('ground-truth/v2_extracted.json')
    
    result = compare_contract_to_eoi(eoi, v2)
    
    assert result.is_valid == True
    assert len(result.mismatches) == 0
    assert result.risk_score == 'NONE'
```

---

## Quick Reference

### Function Signatures

```python
def compare_contract_to_eoi(
    eoi_data: Dict[str, Any], 
    contract_data: Dict[str, Any]
) -> ComparisonResult:
    """Main comparison function."""

def calculate_risk_score(mismatches: List[Mismatch]) -> str:
    """Calculate overall risk from mismatches."""

def generate_recommendation(mismatches: List[Mismatch]) -> str:
    """Generate amendment instructions."""
```

### Workflow Integration

```
Orchestrator detects: CONTRACT_RECEIVED
    │
    ▼
Auditor.compare_contract_to_eoi(eoi_data, contract_data)
    │
    ├── is_valid=True  → Orchestrator: VALIDATED_OK → trigger solicitor email
    │
    └── is_valid=False → Orchestrator: HAS_DISCREPANCIES → trigger discrepancy alert
```
