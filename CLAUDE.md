# CLAUDE.md - OneCorp Multi-Agent System

> **Note**: This document guides AI agents in building the Multi-Agent System. It is NOT part of the final deliverable. The agents you build using these instructions are the solution that will be evaluated.

## Project Overview

You are building a **multi-agent system** for OneCorp, a property investment firm. The system automates the post-EOI (Expression of Interest) contract workflow—from receiving contracts to full execution.

**Design Principle:** The system must be **generalizable**—it processes ANY property deal through pattern-based logic, not hardcoded values. The demo dataset provides concrete test cases, but the agents should work for any EOI, any contract, any property.

---

## Agent Architecture

| Agent | Role | Model | Key Principle |
|-------|------|-------|---------------|
| Router | Email classification, deal ID resolution | TBD | Pattern-based sender/subject matching |
| Extractor | PDF field extraction from EOI/contracts | TBD | Label-pattern detection, not value matching |
| Auditor | Compare contract vs EOI, risk scoring | TBD | Field-by-field comparison with severity rules |
| Comms | Generate all outbound emails | TBD | Template-based with placeholder injection |
| Orchestrator | State management, SLA timers | Python (non-LLM) | Event-driven state machine |

---

## Critical Implementation Rules

### 1. Separation of Logic and Data

**Agent logic should NEVER contain hardcoded values from the demo dataset.**

```python
# ❌ WRONG - Hardcoded value
def extract_lot_number(text):
    if "95" in text:
        return "95"

# ✅ CORRECT - Pattern-based or use LLM reasoning
# Example
def extract_lot_number(text):
    match = re.search(r"Lot\s*#?\s*(\d+)", text, re.IGNORECASE)
    return match.group(1) if match else None
```

### 2. Ground Truth Files Are Test Fixtures Only

Files in `ground-truth/` define **expected outputs for the demo dataset**. They are used for validation testing, NOT as implementation references.

```python
# ❌ WRONG - Reading ground truth at runtime
def compare_contract(contract_data):
    expected = load_json('ground-truth/v1_mismatches.json')
    return contract_data == expected

# ✅ CORRECT - Logic-based comparison
def compare_contract(eoi_data, contract_data):
    mismatches = []
    for field in COMPARABLE_FIELDS:
        if eoi_data.get(field) != contract_data.get(field):
            mismatches.append(create_mismatch(field, eoi_data, contract_data))
    return mismatches
```

### 3. Confidence-Based Progression

- Critical fields require extraction confidence ≥ 0.8
- Below 0.8 → trigger re-extraction request to Extractor
- Still below 0.8 after re-extraction → flag for human review
- Never auto-approve when uncertain about: `lot_number`, `total_price`, `finance_terms`

### 4. State Machine Discipline

- Respect defined state transitions (see `agent_docs/state-machine.md`)
- New contract version automatically supersedes older versions
- Only the highest validated version can trigger "send to solicitor"
- SLA timer starts when solicitor appointment is confirmed

---

## Ground Truth Files (Test Fixtures)

These files in `ground-truth/` contain **expected outputs for the demo dataset only**. They validate that your implementation is correct—agents should NOT read these at runtime.

| File | Purpose | Created By |
|------|---------|------------|
| `eoi_extracted.json` | Expected field values when Extractor processes the demo EOI | Manual analysis of EOI PDF |
| `v1_extracted.json` | Expected field values when Extractor processes demo V1 contract | Manual analysis of V1 PDF |
| `v2_extracted.json` | Expected field values when Extractor processes demo V2 contract | Manual analysis of V2 PDF |
| `v1_mismatches.json` | Expected mismatches when Auditor compares V1 to EOI | Manual comparison |
| `expected_outputs.json` | Expected emails/states at each workflow step | Manual workflow trace |

### How to Use Ground Truth

```python
# In tests (correct usage)
def test_extractor_accuracy():
    expected = load_json('ground-truth/eoi_extracted.json')
    actual = extractor.extract_eoi('data/source-of-truth/EOI_*.pdf')
    assert actual == expected

# In agent code (NEVER do this)
def extract_eoi(pdf_path):
    return load_json('ground-truth/eoi_extracted.json')  # ❌ CHEATING
```

---

## Demo Dataset

The demo uses a single property deal for validation. These values appear in the test fixtures:

| Item | Demo Value | Note |
|------|------------|------|
| Property | Lot 95, Fake Rise VIC 3336 | Extracted by pattern `Lot\s*\d+` |
| Purchasers | John Smith & Jane Smith | Extracted from purchaser section |
| Total Price | $550,000 | Extracted by pattern `Total.*Price.*\$[\d,]+` |
| Finance Terms | NOT subject to finance | Parsed as boolean `false` |

**Important:** These values validate the demo. The agents must work for ANY values by using pattern-based extraction.

---

## File Structure

```
onecorp-mas/
├── CLAUDE.md                 # This file - master instructions
├── agent_docs/               # Implementation guides (pattern-based logic)
│   ├── extraction.md         # How to extract fields from ANY document
│   ├── comparison.md         # How to compare ANY contract to ANY EOI
│   ├── emails.md             # How to classify ANY email, generate ANY outbound
│   ├── state-machine.md      # State transitions for ANY deal
│   └── testing.md            # How to validate against fixtures
├── data/
│   ├── source-of-truth/      # Demo EOI PDF
│   ├── contracts/            # Demo contract PDFs (V1, V2)
│   ├── emails/incoming/      # Demo emails to process
│   ├── emails/templates/     # Reference format for generated emails
│   └── emails_manifest.json  # Demo email metadata
├── ground-truth/             # TEST FIXTURES (not runtime data)
│   ├── eoi_extracted.json    # Expected EOI extraction
│   ├── v1_extracted.json     # Expected V1 extraction
│   ├── v2_extracted.json     # Expected V2 extraction
│   ├── v1_mismatches.json    # Expected V1 mismatches
│   └── expected_outputs.json # Expected workflow outputs
└── src/                      # Implementation
```

---

## Task Execution Workflow

### Progress Tracking

All implementation tasks are tracked in [`PROGRESS.md`](PROGRESS.md), which contains:
- **Task Checklist:** All 31 tasks organized by phase (0-8)
- **Current Status:** Which phase and task is currently being worked on
- **Progress Notes:** Completion timestamps and notes for each finished task

### How to Execute Tasks

1. **Check Progress:**
   - Read [`PROGRESS.md`](PROGRESS.md) to find the next unchecked task `[ ]`
   - Confirm the current phase and task number

2. **Read Task Specification:**
   - Open [`tasks.md`](tasks.md) and locate the task section
   - Read all files listed in the "Context" section
   - Review files in the "Reference" section for additional context
   - Understand the Objective, Constraints, and Acceptance Criteria

3. **Implement the Task:**
   - Follow pattern-based logic (no hardcoded demo values)
   - Include docstrings and type hints
   - Follow existing code conventions
   - Create/modify files as specified in "Output" section

4. **Test the Implementation:**
   - Run the test command specified in the "Output" section
   - Verify all acceptance criteria are met
   - Fix any issues before marking complete

5. **Update Progress:**
   - Mark task as complete in [`PROGRESS.md`](PROGRESS.md): change `[ ]` to `[x]`
   - Update "Current Phase" and "Current Task" in the header
   - Add completion timestamp and notes to "Progress Notes" section
   - Identify the next task (first unchecked `[ ]`)

6. **Confirm Before Proceeding:**
   - Before starting the next task, confirm which task number you're about to execute
   - This prevents skipping tasks or working out of order

### Agent Implementation Task-Specific Guides

Read the relevant guide in `agent_docs/` before implementing:

| Task | Guide | Key Sections |
|------|-------|--------------|
| Building Extractor | `agent_docs/extraction.md` | Field Detection Patterns, Confidence Scoring |
| Building Auditor | `agent_docs/comparison.md` | Comparison Algorithm, Severity Classification |
| Building Router | `agent_docs/emails.md` | Classification Rules, Data Extraction |
| Building Comms | `agent_docs/emails.md` | Template Structure, Email Generation |
| Building Orchestrator | `agent_docs/state-machine.md` | State Definitions, Transition Rules |
| Writing Tests | `agent_docs/testing.md` | Test Patterns, Fixtures |

---

## Commands

**IMPORTANT:** Always activate the virtual environment before running any commands:

```bash
# Activate virtual environment (if not already activated)
source .venv/bin/activate  # On Linux/macOS
# or
.venv\Scripts\activate     # On Windows

# Run the full demo
python -m src.main

# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_comparison.py -v

# Run with coverage
pytest tests/ --cov=src --cov-report=html
```

---

## Success Criteria

The demo must show:

| Criterion | Validation Method |
|-----------|-------------------|
| Extractor produces correct field values | Compare output to `ground-truth/eoi_extracted.json` |
| Auditor detects all V1 mismatches | Compare output to `ground-truth/v1_mismatches.json` |
| Auditor validates V2 with zero mismatches | Output has empty mismatch list |
| Router classifies all emails correctly | Compare to `expected_event` in `emails_manifest.json` |
| State machine reaches EXECUTED state | Final state after processing all emails |
| SLA alert fires when appropriate | Remove buyer-signed email, verify alert generated |
| System is generalizable | Logic uses patterns, not hardcoded values |

---

## Common Pitfalls

1. **Hardcoding demo values** — Agents must use pattern matching, not value matching

2. **Reading ground truth at runtime** — Ground truth is for tests only

3. **Finance term comparison** — Must handle semantic negation ("NOT subject" vs "IS subject")

4. **Appointment date parsing** — Resolve relative dates ("Thursday at 11:30am") against email timestamp

5. **Email type confusion** — Emails 03 and 05 are OUTPUT TEMPLATES, not inputs

6. **Skipping confidence checks** — Critical fields need ≥ 0.8 confidence

---

## Reference Documents

| Document | Purpose |
|----------|---------|
| `spec/MAS_Brief.md` | Full requirements and success criteria |
| `spec/transcript.md` | Stakeholder explanation of the workflow |
| `spec/judging-criteria.md` | How judges evaluate submissions |
| `docs/architecture.md` | System design and agent interactions |
