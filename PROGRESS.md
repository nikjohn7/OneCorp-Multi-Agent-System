# OneCorp MAS - Implementation Progress

**Last Updated:** 2025-12-12T02:10:00Z
**Current Phase:** 6 (Orchestrator)
**Current Task:** 6.1

---

## Task Checklist

### Phase 0 – Foundation Setup
- [x] 0.1 – Define Python Dependencies (`requirements.txt`)
- [x] 0.2 – Initialise `src/` Package Structure
- [x] 0.3 – Shared Test Fixtures in `tests/conftest.py`

### Phase 1 – Utilities First
- [x] 1.1 – Implement `pdf_parser` Utilities
- [x] 1.2 – Implement `email_parser` Utilities
- [x] 1.3 – Implement `date_resolver` for Appointment Phrases
- [x] 1.4 – Write Utility Tests (`tests/test_utils.py`)

### Phase 2 – Extractor Agent
- [x] 2.1 – Design `extractor_prompt.md`
- [x] 2.2 – Implement `extract_eoi()` in `extractor.py`
- [x] 2.3 – Implement `extract_contract()` in `extractor.py`
- [x] 2.4 – Extraction Tests (`tests/test_extraction.py`)

### Phase 3 – Router Agent
- [x] 3.1 – Design `router_prompt.md`
- [x] 3.2 – Implement `classify_email()` in `router.py`
- [x] 3.3 – Email Classification Tests (`tests/test_email_classification.py`)

### Phase 4 – Auditor Agent
 - [x] 4.1 – Design `auditor_prompt.md`
 - [x] 4.2 – Implement `compare_contract_to_eoi()` in `auditor.py`
- [x] 4.3 – Comparison Tests (`tests/test_comparison.py`)

### Phase 5 – Comms Agent
- [x] 5.1 – Design `comms_prompt.md`
- [x] 5.2 – Implement `comms.py` Email Builders
- [x] 5.3 – Comms Tests (`tests/test_comms.py`)

### Phase 6 – Orchestrator
- [ ] 6.1 – Implement Workflow `state_machine.py`
- [ ] 6.2 – Implement `deal_store.py` (SQLite Persistence)
- [ ] 6.3 – Implement `sla_monitor.py`
- [ ] 6.4 – State Transition Tests (`tests/test_state_transitions.py`)

### Phase 7 – Integration
- [ ] 7.1 – CLI Entry Point in `src/main.py`
- [ ] 7.2 – End-to-End Test (`tests/test_end_to_end.py`)
- [ ] 7.3 – Demo Script Doc (`docs/demo-script.md`)

### Phase 8 – Polish
- [ ] 8.1 – Architecture Diagram Asset
- [ ] 8.2 – Finalise `README.md`
- [ ] 8.3 – Optional Demo Recording Instructions

---

## Progress Notes

### Completed Tasks

- **0.1** (2025-12-11T02:25:00Z) - Created requirements.txt with all runtime and dev dependencies (PDF parsing, LLM API, testing, code quality tools)
- **0.2** (2025-12-11T11:50:00Z) - Initialized src/ package structure; all __init__.py files already exist and all packages (src, src.agents, src.agents.prompts, src.utils, src.orchestrator) import successfully
- **0.3** (2025-12-11T12:00:00Z) - Created tests/conftest.py with pytest fixtures for all ground truth files (eoi_extracted, v1_extracted, v2_extracted, v1_mismatches, expected_outputs, emails_manifest) and path fixtures for PDFs and email directories
- **1.1** (2025-12-11T12:15:00Z) - Implemented pdf_parser.py with read_pdf_text(), read_pdf_pages(), extract_tables_from_pdf(), and get_pdf_metadata() functions using pdfplumber. All functions include proper error handling, type hints, and docstrings. Verified successful extraction from all demo PDFs (EOI, V1, V2)
- **1.2** (2025-12-11T12:30:00Z) - Implemented email_parser.py with parse_email_file(), parse_emails_from_directory(), and ParsedEmail dataclass. Parser handles both comma and semicolon-separated email lists, extracts headers (From/To/Cc/Subject), body, and attachments. Validated against all 7 incoming emails in manifest with 100% match rate
- **1.3** (2025-12-11T14:00:00Z) - Implemented date_resolver.py with resolve_appointment_phrase() and parse_time_string() functions. Resolves relative date phrases like "Thursday at 11:30am" to timezone-aware datetimes. Validated against manifest example (2025-01-14T09:12:00+11:00 + "Thursday at 11:30am" = 2025-01-16T11:30:00+11:00). Supports various time formats (11:30am, 2pm, 9:00 AM), case-insensitive weekday names, and returns None for invalid phrases
- **1.4** (2025-12-11T14:30:00Z) - Created comprehensive tests/test_utils.py with 29 tests covering all utility modules (pdf_parser, email_parser, date_resolver). Tests validate PDF text extraction from all demo PDFs, email parsing against manifest data, and appointment datetime resolution. All tests pass (29/29). Fixed conftest.py fixtures to use correct contract PDF filenames (CONTRACT_V1.pdf and CONTRACT_V2.pdf). Tests ensure utilities work with pattern-based logic without hardcoded values
- **2.1** (2025-12-11T16:45:00Z) - Created comprehensive extractor_prompt.md with detailed instructions for DeepSeek V3.2 LLM. Prompt includes complete JSON schemas for both EOI and CONTRACT documents, field detection patterns using label matching (not hardcoded values), finance term semantic parsing (handles negation correctly), confidence scoring guidelines (0.0-1.0), and extraction quality standards. Prompt emphasizes accuracy over guessing, supports both document types with version detection, and includes comprehensive examples for all field types (purchasers, property, pricing, finance, solicitor, deposits, vendor, introducer). Validated schemas match ground-truth JSON structures exactly
- **2.2** (2025-12-11T22:30:00Z) - Implemented extract_eoi() function in src/agents/extractor.py using DeepSeek V3.2 via DeepInfra API. Function extracts text from PDF using pdfplumber, sends to LLM with extractor_prompt.md system prompt, and returns structured JSON matching ground-truth schema. Added openai>=1.0.0 package to requirements.txt for OpenAI-compatible API client. Implemented call_extraction_llm() helper with proper error handling, JSON parsing (handles markdown code blocks), and low temperature (0.1) for deterministic extraction. Also implemented extract_contract() function (for Task 2.3) with same architecture. Tested with demo EOI PDF - achieved 100% field match (30/30 fields) with ground truth after refining prompt for deposit calculation and address formatting edge cases. All critical fields extracted with confidence ≥0.8. Created test_extractor_manual.py for validation
- **2.3** (2025-12-11T22:45:00Z) - Validated extract_contract() function against both V1 and V2 contract PDFs. Function successfully extracts all fields including version detection (V1/V2 from filename and document header), vendor information (name, ACN, address), and all purchaser/property/pricing/finance/solicitor/deposit fields. Refined extractor_prompt.md to normalize finance terms field - extracts concise key phrase ("IS SUBJECT TO FINANCE" or "NOT subject to finance") by removing explanatory clauses, trailing punctuation, and annotations. Tested with both contracts: V1 achieved 100% match (27/27 fields) correctly extracting incorrect values (lot 59 instead of 95, jane.smith@outlook.com instead of janesmith@gmail.com, IS SUBJECT TO FINANCE instead of NOT), V2 achieved 100% match (27/27 fields) with all correct values. Both contracts extracted with average confidence 1.0. Created test_contract_extraction.py for validation
- **2.4** (2025-12-11T23:30:00Z) - Created comprehensive tests/test_extraction.py with 22 tests validating all extraction functionality. Tests organized into 3 classes: TestEOIExtraction (10 tests), TestContractExtraction (10 tests), TestExtractionErrorHandling (2 tests). Tests verify: all required fields extracted, document types and versions detected, field values match ground truth exactly (using recursive nested comparison), critical fields present with high confidence (≥0.8), finance terms semantic parsing correct (handles negation), numeric fields are numbers (not strings), boolean fields are booleans, V1 extracts incorrect values accurately, V2 extracts correct values, vendor field present in contracts, error handling for missing/invalid PDFs. Set up DEEPINFRA_API_KEY in .env file and updated extractor.py to load it using python-dotenv. All 22 tests pass successfully (100% pass rate) after 25 minutes of LLM API calls. Tests validate pattern-based extraction logic works correctly without hardcoded demo values
- **3.1** (2025-12-11T23:45:00Z) - Created comprehensive router_prompt.md (596 lines) for LLM fallback path in hybrid router architecture. Prompt provides detailed instructions for classifying ambiguous emails when deterministic pattern matching confidence < 0.8. Covers all 6 event types (EOI_SIGNED, CONTRACT_FROM_VENDOR, SOLICITOR_APPROVED_WITH_APPOINTMENT, DOCUSIGN_RELEASED, DOCUSIGN_BUYER_SIGNED, DOCUSIGN_EXECUTED) with detailed pattern descriptions and example scenarios. Includes critical appointment phrase extraction instructions (preserve raw phrase like "Thursday at 11:30am"), metadata extraction patterns (lot number, property address, purchaser names, contract version), confidence scoring guidelines (≥0.8 for auto-processing), edge case handling (7 ambiguity scenarios), and complete JSON output schema. Prompt emphasizes pattern-based logic that generalizes to any property deal, not hardcoded to demo values. Includes 4 detailed classification examples and decision tree for systematic classification approach
- **3.2** (2025-12-12T00:15:00Z) - Implemented hybrid email classifier in src/agents/router.py with deterministic pattern matching + LLM fallback. Created ClassificationResult dataclass with event_type, confidence (0.0-1.0), method ("deterministic" or "llm"), and metadata fields. Implemented classify_deterministic() using sender domain patterns, subject line patterns, body content patterns, and attachment patterns (no hardcoded values). Implemented calculate_confidence() scoring algorithm considering sender match (0.35), subject matches (0.25 each, capped 0.40), body matches (0.15 each, capped 0.30), attachment match (0.20), and exclusivity bonus (0.15). Confidence threshold set to 0.8 for deterministic classification. Implemented metadata extraction functions: extract_lot_number(), extract_property_address(), extract_purchaser_names() (handles "John & Jane Smith" shared last name), extract_appointment_phrase() (preserves raw format), extract_contract_version() (handles VERSION_1, VERSION 1, V1 formats). Implemented classify_with_llm() fallback using router_prompt.md and DeepSeek V3.2. Main classify_email() function orchestrates hybrid approach: tries deterministic first, uses LLM if confidence < 0.8. All 6 event types correctly classified. Fixed purchaser name extraction to handle shared last names, fixed version extraction to handle underscores.
- **3.3** (2025-12-12T00:30:00Z) - Created comprehensive tests/test_email_classification.py with 19 tests organized into 5 test classes validating all router functionality. Tests verify: all 7 incoming demo emails classified correctly (TestRouterClassifiesAllEmails - 7 tests), hybrid classification method works (high confidence uses deterministic, returns valid ClassificationResult - 3 tests), metadata extraction functions work correctly (lot number, property address, purchaser names with shared last name, appointment phrase, contract version - 5 tests), confidence scoring is in valid range [0.0-1.0] and clear emails score ≥0.8 (TestConfidenceScoring - 3 tests), all emails from manifest classified to correct event_type (TestRouterClassifiesAllEmailsFromManifest - 1 test). All critical metadata extracted: appointment phrase for SOLICITOR_APPROVED, contract version for CONTRACT_FROM_VENDOR, lot numbers and property addresses for all. All 19 tests pass (100% pass rate) in 1.84 seconds. Tests validate pattern-based classification without hardcoded demo values. Added emails_dir fixture to conftest.py for test access to email files.
- **4.1** (2025-12-12T01:12:00Z) - Designed src/agents/prompts/auditor_prompt.md with role, JSON output schema, comparable fields, type-specific comparison rules, severity/risk scoring guidance, amendment recommendation format, and next-action rules aligned to v1_mismatches fixture.
- **4.2** (2025-12-12T01:25:00Z) - Implemented deterministic compare_contract_to_eoi in src/agents/auditor.py with mismatch detection, severity/risk scoring, formatted values, and amendment recommendations. Added optional Qwen3 Auditor LLM helper using DeepInfra DEEPINFRA_API_KEY.
- **4.3** (2025-12-12T01:33:00Z) - Added tests/test_comparison.py validating deterministic Auditor comparison vs fixtures; tests disable LLM auto-trigger to keep results stable.

- **5.1** (2025-12-12T02:10:00Z) - Created comms_prompt.md instructing Qwen3 to write natural outbound email bodies from required-field checklists without inventing facts.
- **5.2** (2025-12-12T02:10:00Z) - Implemented hybrid Comms agent in src/agents/comms.py: deterministic headers/fallback bodies + Qwen3 phrasing layer via DeepInfra (temperature ~0.35) with mandatory-field post-validation and safe fallback.
- **5.3** (2025-12-12T02:10:00Z) - Added tests/test_comms.py validating all four builders against required content; tests run with use_llm=False for determinism.

### Current Task Notes

_No task in progress._

### Issues / Blockers

_None._

---

## Quick Reference

**Total Tasks:** 31
**Completed:** 14
**Remaining:** 17
**Progress:** 45%

**Next Task:** 4.1 – Design `auditor_prompt.md`

---

## Task Execution Guidelines

When executing a task:

1. **Before Starting:**
   - Read full task specification in [`tasks.md`](tasks.md)
   - Read all files listed in "Context" section
   - Review "Reference" files for additional context
   - Confirm understanding of Constraints and Acceptance Criteria

2. **During Execution:**
   - Follow pattern-based logic (no hardcoded demo values)
   - Include docstrings and type hints
   - Follow existing code conventions
   - Test incrementally

3. **After Completion:**
   - Run the test command specified in "Output" section
   - Verify all acceptance criteria are met
   - Mark task as complete in this file: `[x]`
   - Update "Current Phase" and "Current Task" fields
   - Add completion timestamp to Progress Notes
   - Identify next task and confirm before proceeding

---

## How to Update This File

After completing a task, update the checklist:

```markdown
- [x] 0.1 – Define Python Dependencies (`requirements.txt`)
```

Update the header section:
```markdown
**Last Updated:** 2025-12-11T02:30:00Z
**Current Phase:** 0 (Foundation Setup)
**Current Task:** 0.2
```

Add a note to Progress Notes:
```markdown
### Completed Tasks

- **0.1** (2025-12-11T02:30:00Z) - Created requirements.txt with all dependencies
