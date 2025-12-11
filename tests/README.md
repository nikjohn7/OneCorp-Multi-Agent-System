# Tests

Unit and integration tests for the OneCorp Multi-Agent System.

## Running Tests

```bash
# All tests
pytest tests/ -v

# Specific test file
pytest tests/test_extraction.py -v

# With coverage
pytest tests/ --cov=src --cov-report=html

# Stop on first failure
pytest tests/ -x
```

## Test Files

| File | Purpose |
|------|---------|
| `test_extraction.py` | Verify PDF field extraction against ground truth |
| `test_comparison.py` | Verify V1 mismatches and V2 validation |
| `test_email_classification.py` | Verify email event type detection |
| `test_state_transitions.py` | Verify workflow state machine |
| `test_end_to_end.py` | Full workflow integration test |

## Fixtures

Tests consume JSON fixtures from `../ground-truth/`:

- `eoi_extracted.json` — Expected EOI extraction
- `v1_extracted.json` — Expected V1 extraction  
- `v2_extracted.json` — Expected V2 extraction
- `v1_mismatches.json` — Expected comparison result for V1
- `expected_outputs.json` — Expected emails at each workflow stage

Shared fixtures are defined in `conftest.py`.

## Test Data

Input files are in `../data/`:

- `source-of-truth/EOI_John_JaneSmith.pdf`
- `contracts/CONTRACT_V1.pdf`
- `contracts/CONTRACT_V2.pdf`
- `emails/incoming/*.txt`
- `emails_manifest.json`

## Key Test Scenarios

### Contract Comparison (Critical)

```python
def test_v1_detects_all_mismatches():
    """V1 must detect exactly 5 mismatches with correct severities"""
    # Expected: lot_number (HIGH), total_price (HIGH), 
    # build_price (MEDIUM), purchaser_email_2 (LOW), finance_terms (HIGH)

def test_v2_has_no_mismatches():
    """V2 must validate with zero mismatches"""
```

### Email Classification

```python
def test_classify_eoi_signed():
    """Email 1 → EOI_SIGNED event"""

def test_classify_solicitor_approval():
    """Email 4 → SOLICITOR_APPROVED_WITH_APPOINTMENT event"""
    # Must also extract appointment datetime
```

### SLA Logic

```python
def test_sla_alert_fires_when_buyer_not_signed():
    """Alert fires at appointment + 2 days if no buyer signature"""

def test_sla_alert_does_not_fire_when_signed():
    """No alert if buyer signed before deadline"""
```

## Implementation Guide

For detailed test patterns and examples, see `../agent_docs/testing.md`.