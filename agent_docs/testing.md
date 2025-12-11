# Testing Guide

## Overview

Tests validate that agents produce correct outputs by comparing against **ground truth fixtures**. The test logic is reusable; only the fixtures are demo-specific.

---

## Part 1: Test Architecture

### Test Files

| File | What It Tests | Key Fixtures |
|------|---------------|--------------|
| `test_extraction.py` | Extractor agent outputs | `eoi_extracted.json`, `v1_extracted.json`, `v2_extracted.json` |
| `test_comparison.py` | Auditor mismatch detection | `v1_mismatches.json` |
| `test_email_classification.py` | Router event classification | `emails_manifest.json` |
| `test_state_transitions.py` | Orchestrator state machine | N/A (logic-based) |
| `test_end_to_end.py` | Full workflow integration | `expected_outputs.json` |

### Ground Truth Files

Located in `ground-truth/`:

```
ground-truth/
├── eoi_extracted.json      # Expected extraction from EOI
├── v1_extracted.json       # Expected extraction from Contract V1
├── v2_extracted.json       # Expected extraction from Contract V2
├── v1_mismatches.json      # Expected mismatches: EOI vs V1
└── expected_outputs.json   # Expected emails/states at each step
```

**Critical principle:** Ground truth files are **test fixtures**, not implementation references. Agents should not read these files at runtime—they exist only for validation.

---

## Part 2: Test Patterns

### Pattern: Extraction Validation

```python
# tests/test_extraction.py

import json
import pytest
from pathlib import Path
from src.agents.extractor import extract_eoi, extract_contract

GROUND_TRUTH_DIR = Path('ground-truth')
DATA_DIR = Path('data')


@pytest.fixture
def eoi_ground_truth():
    """Load expected EOI extraction."""
    with open(GROUND_TRUTH_DIR / 'eoi_extracted.json') as f:
        return json.load(f)


@pytest.fixture
def v1_ground_truth():
    """Load expected V1 extraction."""
    with open(GROUND_TRUTH_DIR / 'v1_extracted.json') as f:
        return json.load(f)


@pytest.fixture
def v2_ground_truth():
    """Load expected V2 extraction."""
    with open(GROUND_TRUTH_DIR / 'v2_extracted.json') as f:
        return json.load(f)


class TestEOIExtraction:
    """Test extraction from EOI document."""
    
    def test_extracts_all_required_fields(self, eoi_ground_truth):
        """Extractor should extract all fields defined in ground truth."""
        result = extract_eoi(DATA_DIR / 'source-of-truth/EOI_John_JaneSmith.pdf')
        
        for field_name in eoi_ground_truth.keys():
            assert field_name in result, f"Missing field: {field_name}"
    
    def test_field_values_match_ground_truth(self, eoi_ground_truth):
        """Extracted values should match ground truth."""
        result = extract_eoi(DATA_DIR / 'source-of-truth/EOI_John_JaneSmith.pdf')
        
        for field_name, expected_value in eoi_ground_truth.items():
            actual_value = result.get(field_name)
            assert actual_value == expected_value, \
                f"Field '{field_name}': expected {expected_value!r}, got {actual_value!r}"
    
    def test_critical_fields_have_high_confidence(self, eoi_ground_truth):
        """Critical fields should have confidence >= 0.8."""
        result = extract_eoi(DATA_DIR / 'source-of-truth/EOI_John_JaneSmith.pdf')
        
        critical_fields = ['lot_number', 'total_price', 'finance_terms', 
                          'purchaser_first_name_1', 'purchaser_last_name_1']
        
        for field in critical_fields:
            confidence = result.get_confidence(field)
            assert confidence >= 0.8, \
                f"Critical field '{field}' has low confidence: {confidence}"


class TestContractExtraction:
    """Test extraction from contract documents."""
    
    def test_v1_extraction_matches_ground_truth(self, v1_ground_truth):
        """V1 extraction should match ground truth (including errors)."""
        result = extract_contract(DATA_DIR / 'contracts/CONTRACT_V1.pdf')
        
        for field_name, expected_value in v1_ground_truth.items():
            actual_value = result.get(field_name)
            assert actual_value == expected_value, \
                f"V1 field '{field_name}': expected {expected_value!r}, got {actual_value!r}"
    
    def test_v2_extraction_matches_ground_truth(self, v2_ground_truth):
        """V2 extraction should match ground truth."""
        result = extract_contract(DATA_DIR / 'contracts/CONTRACT_V2.pdf')
        
        for field_name, expected_value in v2_ground_truth.items():
            actual_value = result.get(field_name)
            assert actual_value == expected_value, \
                f"V2 field '{field_name}': expected {expected_value!r}, got {actual_value!r}"
    
    def test_detects_document_version(self):
        """Extractor should correctly identify contract version."""
        v1_result = extract_contract(DATA_DIR / 'contracts/CONTRACT_V1.pdf')
        v2_result = extract_contract(DATA_DIR / 'contracts/CONTRACT_V2.pdf')
        
        assert v1_result.version == 'V1'
        assert v2_result.version == 'V2'
```

### Pattern: Comparison Validation

```python
# tests/test_comparison.py

import json
import pytest
from pathlib import Path
from src.agents.auditor import compare_contract_to_eoi

GROUND_TRUTH_DIR = Path('ground-truth')


@pytest.fixture
def eoi_data():
    with open(GROUND_TRUTH_DIR / 'eoi_extracted.json') as f:
        return json.load(f)


@pytest.fixture
def v1_data():
    with open(GROUND_TRUTH_DIR / 'v1_extracted.json') as f:
        return json.load(f)


@pytest.fixture
def v2_data():
    with open(GROUND_TRUTH_DIR / 'v2_extracted.json') as f:
        return json.load(f)


@pytest.fixture
def expected_v1_mismatches():
    with open(GROUND_TRUTH_DIR / 'v1_mismatches.json') as f:
        return json.load(f)


class TestV1Comparison:
    """Test comparison of V1 contract (has errors) against EOI."""
    
    def test_detects_correct_number_of_mismatches(self, eoi_data, v1_data, expected_v1_mismatches):
        """Should detect exactly the number of mismatches in ground truth."""
        result = compare_contract_to_eoi(eoi_data, v1_data)
        
        expected_count = len(expected_v1_mismatches)
        actual_count = len(result.mismatches)
        
        assert actual_count == expected_count, \
            f"Expected {expected_count} mismatches, found {actual_count}"
    
    def test_detects_all_expected_fields(self, eoi_data, v1_data, expected_v1_mismatches):
        """Should detect mismatches in all expected fields."""
        result = compare_contract_to_eoi(eoi_data, v1_data)
        
        expected_fields = {m['field'] for m in expected_v1_mismatches}
        actual_fields = {m.field for m in result.mismatches}
        
        missing = expected_fields - actual_fields
        extra = actual_fields - expected_fields
        
        assert not missing, f"Missing expected mismatches: {missing}"
        assert not extra, f"Unexpected mismatches: {extra}"
    
    def test_mismatch_values_are_correct(self, eoi_data, v1_data, expected_v1_mismatches):
        """Mismatch EOI/contract values should match ground truth."""
        result = compare_contract_to_eoi(eoi_data, v1_data)
        
        for expected in expected_v1_mismatches:
            actual = next(
                (m for m in result.mismatches if m.field == expected['field']),
                None
            )
            assert actual is not None, f"Mismatch not found for {expected['field']}"
            
            assert actual.eoi_value == expected['eoi_value'], \
                f"Field {expected['field']}: wrong EOI value"
            assert actual.contract_value == expected['contract_value'], \
                f"Field {expected['field']}: wrong contract value"
    
    def test_severities_are_correct(self, eoi_data, v1_data, expected_v1_mismatches):
        """Severity classifications should match ground truth."""
        result = compare_contract_to_eoi(eoi_data, v1_data)
        
        for expected in expected_v1_mismatches:
            actual = next(m for m in result.mismatches if m.field == expected['field'])
            assert actual.severity == expected['severity'], \
                f"Field {expected['field']}: expected severity {expected['severity']}, got {actual.severity}"
    
    def test_is_valid_false(self, eoi_data, v1_data):
        """V1 should not validate."""
        result = compare_contract_to_eoi(eoi_data, v1_data)
        assert result.is_valid == False
    
    def test_risk_score_is_high(self, eoi_data, v1_data):
        """V1 should have HIGH risk score (has HIGH severity mismatches)."""
        result = compare_contract_to_eoi(eoi_data, v1_data)
        assert result.risk_score == 'HIGH'
    
    def test_generates_amendment_recommendation(self, eoi_data, v1_data):
        """Should generate non-empty amendment recommendation."""
        result = compare_contract_to_eoi(eoi_data, v1_data)
        
        assert result.amendment_recommendation is not None
        assert len(result.amendment_recommendation) > 0


class TestV2Comparison:
    """Test comparison of V2 contract (corrected) against EOI."""
    
    def test_no_mismatches(self, eoi_data, v2_data):
        """V2 should have zero mismatches."""
        result = compare_contract_to_eoi(eoi_data, v2_data)
        assert len(result.mismatches) == 0
    
    def test_is_valid_true(self, eoi_data, v2_data):
        """V2 should validate successfully."""
        result = compare_contract_to_eoi(eoi_data, v2_data)
        assert result.is_valid == True
    
    def test_risk_score_none(self, eoi_data, v2_data):
        """V2 should have no risk."""
        result = compare_contract_to_eoi(eoi_data, v2_data)
        assert result.risk_score in ['NONE', None]
```

### Pattern: Email Classification Validation

```python
# tests/test_email_classification.py

import json
import pytest
from pathlib import Path
from src.agents.router import classify_email
from src.utils.email_parser import parse_email

DATA_DIR = Path('data')


@pytest.fixture
def emails_manifest():
    with open(DATA_DIR / 'emails_manifest.json') as f:
        return json.load(f)


def load_email(filepath: str):
    """Load and parse an email file."""
    with open(DATA_DIR / 'emails' / filepath) as f:
        return parse_email(f.read())


class TestEmailClassification:
    """Test Router agent email classification."""
    
    def test_all_input_emails_classified_correctly(self, emails_manifest):
        """All INPUT emails should be classified to expected event type."""
        for email_entry in emails_manifest['emails']:
            # Skip output templates
            if email_entry.get('type') != 'INPUT':
                continue
            
            email = load_email(email_entry['file'])
            result = classify_email(email)
            
            expected = email_entry['expected_event']
            actual = result.event_type
            
            assert actual == expected, \
                f"Email {email_entry['email_id']}: expected {expected}, got {actual}"
    
    def test_classification_confidence_above_threshold(self, emails_manifest):
        """Classifications should have confidence >= 0.7."""
        for email_entry in emails_manifest['emails']:
            if email_entry.get('type') != 'INPUT':
                continue
            
            email = load_email(email_entry['file'])
            result = classify_email(email)
            
            assert result.confidence >= 0.7, \
                f"Email {email_entry['email_id']}: low confidence {result.confidence}"


class TestDataExtraction:
    """Test Router agent data extraction from emails."""
    
    def test_extracts_lot_number(self):
        """Should extract lot number from EOI email."""
        email = load_email('incoming/01_eoi_signed.txt')
        result = classify_email(email)
        
        assert result.extracted_data.lot_number is not None
    
    def test_extracts_appointment_datetime(self):
        """Should extract and resolve appointment datetime from solicitor email."""
        email = load_email('incoming/04_solicitor_approved.txt')
        result = classify_email(email)
        
        assert result.extracted_data.appointment_phrase is not None
        assert result.extracted_data.appointment_datetime is not None
```

### Pattern: State Machine Validation

```python
# tests/test_state_transitions.py

import pytest
from src.orchestrator.state_machine import StateMachine, DealState


class TestValidTransitions:
    """Test that valid transitions are allowed."""
    
    def test_eoi_to_contract_received(self):
        sm = StateMachine(deal_id="TEST_DEAL")
        sm.current_state = DealState.EOI_RECEIVED
        
        success = sm.transition("CONTRACT_FROM_VENDOR")
        
        assert success == True
        assert sm.current_state == DealState.CONTRACT_RECEIVED
    
    def test_contract_validation_branches(self):
        """Validation can lead to OK or DISCREPANCIES."""
        # Test OK path
        sm1 = StateMachine(deal_id="TEST_DEAL_1")
        sm1.current_state = DealState.CONTRACT_RECEIVED
        sm1.transition("VALIDATION_PASSED")
        assert sm1.current_state == DealState.CONTRACT_VALIDATED_OK
        
        # Test DISCREPANCIES path
        sm2 = StateMachine(deal_id="TEST_DEAL_2")
        sm2.current_state = DealState.CONTRACT_RECEIVED
        sm2.transition("VALIDATION_FAILED")
        assert sm2.current_state == DealState.CONTRACT_HAS_DISCREPANCIES
    
    def test_full_happy_path(self):
        """Complete workflow executes successfully."""
        sm = StateMachine(deal_id="TEST_DEAL")
        
        transitions = [
            ("CONTRACT_FROM_VENDOR", DealState.CONTRACT_RECEIVED),
            ("VALIDATION_PASSED", DealState.CONTRACT_VALIDATED_OK),
            ("SOLICITOR_EMAIL_SENT", DealState.SENT_TO_SOLICITOR),
            ("SOLICITOR_APPROVED_WITH_APPOINTMENT", DealState.SOLICITOR_APPROVED),
            ("VENDOR_RELEASE_EMAIL_SENT", DealState.DOCUSIGN_RELEASE_REQUESTED),
            ("DOCUSIGN_RELEASED", DealState.DOCUSIGN_RELEASED),
            ("DOCUSIGN_BUYER_SIGNED", DealState.BUYER_SIGNED),
            ("DOCUSIGN_EXECUTED", DealState.EXECUTED),
        ]
        
        for event, expected_state in transitions:
            success = sm.transition(event)
            assert success, f"Transition '{event}' failed"
            assert sm.current_state == expected_state


class TestInvalidTransitions:
    """Test that invalid transitions are rejected."""
    
    def test_cannot_skip_states(self):
        """Cannot jump from EOI_RECEIVED to EXECUTED."""
        sm = StateMachine(deal_id="TEST_DEAL")
        sm.current_state = DealState.EOI_RECEIVED
        
        success = sm.transition("DOCUSIGN_EXECUTED")
        
        assert success == False
        assert sm.current_state == DealState.EOI_RECEIVED  # Unchanged


class TestVersionSuperseding:
    """Test contract version management."""
    
    def test_new_version_supersedes_old(self):
        """New contract version marks old as superseded."""
        sm = StateMachine(deal_id="TEST_DEAL")
        
        # Receive V1
        sm.transition("CONTRACT_FROM_VENDOR")
        sm.contracts[1] = {'status': 'RECEIVED'}
        
        # V1 has discrepancies
        sm.transition("VALIDATION_FAILED")
        sm.contracts[1]['status'] = 'HAS_DISCREPANCIES'
        
        # Amendment cycle
        sm.transition("DISCREPANCY_ALERT_SENT")
        
        # Receive V2
        sm.current_state = DealState.AWAITING_AMENDED_CONTRACT
        sm.transition("CONTRACT_FROM_VENDOR")
        
        # V1 should be superseded
        assert sm.contracts[1]['status'] == 'SUPERSEDED'


class TestSLALogic:
    """Test SLA timer and alerting."""
    
    def test_sla_alert_fires_when_overdue(self):
        """SLA alert fires when deadline passed without buyer signature."""
        from datetime import datetime, timedelta
        
        sm = StateMachine(deal_id="TEST_DEAL")
        sm.current_state = DealState.DOCUSIGN_RELEASED
        sm.sla_deadline = datetime.now() - timedelta(hours=1)  # Past
        
        should_alert = sm.check_sla()
        
        assert should_alert == True
        assert sm.current_state == DealState.SLA_OVERDUE_ALERT_SENT
    
    def test_sla_alert_does_not_fire_if_signed(self):
        """No alert if buyer already signed."""
        from datetime import datetime, timedelta
        
        sm = StateMachine(deal_id="TEST_DEAL")
        sm.current_state = DealState.BUYER_SIGNED
        sm.sla_deadline = datetime.now() - timedelta(hours=1)  # Past
        
        should_alert = sm.check_sla()
        
        assert should_alert == False
        assert sm.current_state == DealState.BUYER_SIGNED  # Unchanged
```

---

## Part 3: Running Tests

### Commands

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_comparison.py -v

# Run specific test class
pytest tests/test_comparison.py::TestV1Comparison -v

# Run specific test
pytest tests/test_comparison.py::TestV1Comparison::test_detects_correct_number_of_mismatches -v

# Stop on first failure
pytest tests/ -x

# Show print output
pytest tests/ -s

# With coverage report
pytest tests/ --cov=src --cov-report=html
```

### Debugging

```bash
# Drop into debugger on failure
pytest tests/test_extraction.py --pdb

# Run only previously failed tests
pytest tests/ --lf

# Verbose diff output
pytest tests/ -vv
```

---

## Part 4: Shared Fixtures

### conftest.py

```python
# tests/conftest.py

import json
import pytest
from pathlib import Path

GROUND_TRUTH_DIR = Path('ground-truth')
DATA_DIR = Path('data')


@pytest.fixture(scope="session")
def eoi_data():
    """EOI extracted fields (source of truth)."""
    with open(GROUND_TRUTH_DIR / 'eoi_extracted.json') as f:
        return json.load(f)


@pytest.fixture(scope="session")
def v1_data():
    """V1 contract extracted fields (has errors)."""
    with open(GROUND_TRUTH_DIR / 'v1_extracted.json') as f:
        return json.load(f)


@pytest.fixture(scope="session")
def v2_data():
    """V2 contract extracted fields (corrected)."""
    with open(GROUND_TRUTH_DIR / 'v2_extracted.json') as f:
        return json.load(f)


@pytest.fixture(scope="session")
def v1_mismatches():
    """Expected mismatches for V1 vs EOI."""
    with open(GROUND_TRUTH_DIR / 'v1_mismatches.json') as f:
        return json.load(f)


@pytest.fixture(scope="session")
def emails_manifest():
    """Email metadata and expected classifications."""
    with open(DATA_DIR / 'emails_manifest.json') as f:
        return json.load(f)


@pytest.fixture(scope="session")
def expected_outputs():
    """Expected workflow outputs (emails, states)."""
    with open(GROUND_TRUTH_DIR / 'expected_outputs.json') as f:
        return json.load(f)
```

---

## Part 5: Creating Ground Truth Files

Ground truth files should be created **manually** by analyzing the source documents:

### eoi_extracted.json

```json
{
  "purchaser_first_name_1": "...",
  "purchaser_last_name_1": "...",
  "purchaser_email_1": "...",
  "lot_number": "...",
  "total_price": 0,
  "finance_terms": false,
  ...
}
```

**Process:** Open EOI PDF, read each field, transcribe to JSON.

### v1_mismatches.json

```json
[
  {
    "field": "lot_number",
    "eoi_value": "...",
    "contract_value": "...",
    "severity": "HIGH"
  },
  ...
]
```

**Process:** Compare EOI vs V1 manually, document each difference.

### expected_outputs.json

```json
{
  "workflow_states": ["EOI_RECEIVED", "CONTRACT_V1_RECEIVED", ...],
  "generated_emails": {
    "discrepancy_alert": { "triggered_at_state": "...", "recipient": "..." },
    "contract_to_solicitor": { "triggered_at_state": "...", "recipient": "..." },
    ...
  }
}
```

**Process:** Trace through expected workflow, document each output.
