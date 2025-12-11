# Extraction Guide

## Overview

The Extractor agent parses PDF documents (EOIs and contracts) and outputs structured field data with confidence scores. The logic is document-type aware but **not hardcoded to specific values**—it extracts whatever values are present in the document.

---

## Part 1: Implementation Logic (Generalizable)

### Field Detection Patterns

The Extractor identifies fields by looking for **label patterns** in the document, not by expecting specific values.

#### Purchaser Fields

| Field | Label Patterns to Match |
|-------|------------------------|
| `purchaser_first_name_N` | "FIRST NAME/S", "First Name", "Given Name" |
| `purchaser_last_name_N` | "LAST NAME", "Surname", "Family Name" |
| `purchaser_email_N` | "EMAIL", "Email Address", or pattern `*@*.*` near purchaser section |
| `purchaser_mobile_N` | "MOBILE", "Phone", "Contact", or pattern `+61 4XX XXX XXX` |

#### Property Fields

| Field | Label Patterns to Match |
|-------|------------------------|
| `lot_number` | "LOT #", "Lot Number:", "Lot No." |
| `property_address` | "ADDRESS", "Property Address", "Street Address" |
| `project_name` | "PROJECT NAME", "Estate", "Development" |

#### Financial Fields

| Field | Label Patterns to Match | Normalization |
|-------|------------------------|---------------|
| `total_price` | "TOTAL PRICE", "Purchase Price", "Total Purchase Price" | Remove `$`, `AU$`, commas → integer |
| `land_price` | "LAND PRICE", "Land Component" | Remove `$`, `AU$`, commas → integer |
| `build_price` | "BUILD PRICE", "Build Component", "Construction" | Remove `$`, `AU$`, commas → integer |
| `eoi_deposit` | "EOI Deposit", "Expression of Interest Deposit" | Remove `$`, commas → integer |
| `build_deposit` | "Build Deposit Amount" | Remove `$`, commas → integer |
| `balance_deposit` | "Balance Deposit Amount" | Remove `$`, commas → integer |

#### Finance Terms (Critical - Requires Semantic Parsing)

| Field | Label Patterns | Normalization Logic |
|-------|----------------|---------------------|
| `finance_terms` | "FINANCE TERMS", "Finance", "Subject to Finance" | See below |

**Finance Terms Normalization:**

```python
def normalize_finance_terms(raw_text: str) -> bool:
    """
    Returns True if contract IS subject to finance.
    Returns False if contract is NOT subject to finance.
    """
    text_lower = raw_text.lower().strip()
    
    # Negative patterns (NOT subject to finance) → False
    negative_patterns = [
        "not subject to finance",
        "is not subject to finance",
        "unconditional",
        "no finance condition",
        "finance not required"
    ]
    
    for pattern in negative_patterns:
        if pattern in text_lower:
            return False
    
    # Positive patterns (IS subject to finance) → True
    positive_patterns = [
        "subject to finance",
        "is subject to finance",
        "conditional on finance",
        "finance required"
    ]
    
    for pattern in positive_patterns:
        if pattern in text_lower:
            return True
    
    # Ambiguous - return None and flag for human review
    return None
```

**Why this is critical:** The phrase "IS SUBJECT TO FINANCE" vs "NOT subject to finance" represents a boolean inversion with significant legal implications. The extractor must handle negation correctly.

#### Solicitor Fields

| Field | Label Patterns to Match |
|-------|------------------------|
| `solicitor_name` | "SOLICITOR", "Legal Representative", "Lawyer" → then "NAME" or "CONTACT" |
| `solicitor_email` | "EMAIL" within solicitor section |
| `solicitor_phone` | "PHONE" within solicitor section |

### Document Type Detection

```python
def detect_document_type(text: str) -> str:
    """Determine if document is EOI or Contract."""
    text_lower = text.lower()
    
    if "expression of interest" in text_lower:
        return "EOI"
    elif "contract of sale" in text_lower:
        return "CONTRACT"
    else:
        return "UNKNOWN"

def detect_contract_version(text: str, filename: str) -> str:
    """Extract version from contract."""
    # Check filename first
    if "v1" in filename.lower() or "version 1" in filename.lower():
        return "V1"
    if "v2" in filename.lower() or "version 2" in filename.lower():
        return "V2"
    
    # Check document text
    if "version 1" in text.lower():
        return "V1"
    if "version 2" in text.lower():
        return "V2"
    
    # Default to V1 if no version indicator
    return "V1"
```

### Output Schema

```python
@dataclass
class ExtractionResult:
    document_type: str  # "EOI" | "CONTRACT"
    version: Optional[str]  # "V1", "V2", etc. (contracts only)
    extraction_timestamp: str  # ISO format
    fields: List[ExtractedField]
    
@dataclass
class ExtractedField:
    field_name: str
    raw_text: str  # Original text as found in document
    normalized_value: Any  # Processed value (string, int, bool)
    confidence: float  # 0.0 to 1.0
    source_location: Optional[str]  # e.g., "Page 1, Section 1.3"
```

### Confidence Scoring

Confidence reflects how certain the extractor is about the extracted value:

| Confidence | Criteria | Action |
|------------|----------|--------|
| 0.9 - 1.0 | Clear label match, unambiguous value, standard format | Accept |
| 0.8 - 0.89 | Good label match, minor ambiguity | Accept |
| 0.5 - 0.79 | Weak label match OR ambiguous value | Flag for re-extraction |
| < 0.5 | No clear label OR multiple conflicting values | Flag for human review |

**Factors that reduce confidence:**
- Label found but value format unexpected
- Multiple possible values found
- Value found far from expected label
- OCR artifacts or encoding issues

### Re-Extraction Protocol

When the Auditor requests re-extraction for a specific field:

```python
@dataclass
class ReExtractionRequest:
    document_id: str
    field_name: str
    location_hint: Optional[str]  # e.g., "Section 1.5"
    reason: str

@dataclass
class ReExtractionResponse:
    field_name: str
    raw_text: str
    normalized_value: Any
    confidence: float
    source_location: str
    extraction_method: str  # "focused" | "full_document"
```

On re-extraction:
1. If `location_hint` provided, focus extraction on that section
2. Apply stricter pattern matching
3. Return updated confidence score
4. If still ambiguous, explicitly state uncertainty

### PDF Parsing Implementation

```python
import pdfplumber

def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract full text from PDF."""
    with pdfplumber.open(pdf_path) as pdf:
        text = ""
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    return text

def extract_tables_from_pdf(pdf_path: str) -> List[List[List[str]]]:
    """Extract tables (useful for EOI forms)."""
    tables = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_tables = page.extract_tables()
            if page_tables:
                tables.extend(page_tables)
    return tables
```

### Critical vs Non-Critical Fields

| Critical (confidence ≥ 0.8 required) | Non-Critical |
|-------------------------------------|--------------|
| `lot_number` | `purchaser_mobile_N` |
| `total_price` | `land_price` (if total correct) |
| `finance_terms` | `build_price` (if total correct) |
| `purchaser_first_name_N` | `solicitor_phone` |
| `purchaser_last_name_N` | `project_name` |
| `purchaser_email_N` | `residential_address` |
| `property_address` | deposits |

---

## Part 2: Demo Validation

### Ground Truth Reference

For the demo dataset, expected extraction outputs are defined in:

| Document | Ground Truth File |
|----------|-------------------|
| EOI PDF | `ground-truth/eoi_extracted.json` |
| Contract V1 | `ground-truth/v1_extracted.json` |
| Contract V2 | `ground-truth/v2_extracted.json` |

**These files are test fixtures, not implementation references.** The Extractor should produce outputs matching these files when run against the demo PDFs.

### Validation Test Pattern

```python
def test_extraction_matches_ground_truth():
    """Extractor output should match ground truth for demo data."""
    
    # Load ground truth
    with open('ground-truth/eoi_extracted.json') as f:
        expected = json.load(f)
    
    # Run extractor
    actual = extract_eoi('data/source-of-truth/EOI_John_JaneSmith.pdf')
    
    # Compare each field
    for field_name, expected_value in expected.items():
        actual_value = actual.get(field_name)
        assert actual_value == expected_value, \
            f"Field {field_name}: expected {expected_value}, got {actual_value}"
```

### Demo-Specific Notes

The demo dataset has these characteristics (discovered through analysis, not hardcoded):

- **EOI format**: Table-based layout with clear labels
- **Contract format**: Section-numbered legal document (1.1, 1.2, etc.)
- **Finance terms location**: Section 1.5 in contracts, "CONTRACT DETAILS" section in EOI
- **Multiple purchasers**: Documents contain two purchasers (indexed as 1 and 2)

---

## Quick Reference

### Function Signatures

```python
def extract_eoi(pdf_path: str) -> ExtractionResult:
    """Extract all fields from an EOI document."""
    
def extract_contract(pdf_path: str) -> ExtractionResult:
    """Extract all fields from a contract document."""
    
def re_extract_field(
    pdf_path: str, 
    field_name: str, 
    location_hint: Optional[str] = None
) -> ExtractedField:
    """Targeted re-extraction of a single field."""
```

### Error Handling

```python
class ExtractionError(Exception):
    """Base class for extraction errors."""
    
class DocumentTypeUnknown(ExtractionError):
    """Could not determine if document is EOI or Contract."""
    
class FieldNotFound(ExtractionError):
    """Required field could not be located in document."""
    
class LowConfidenceExtraction(ExtractionError):
    """Field extracted but confidence below threshold."""
```
