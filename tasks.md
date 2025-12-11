# OneCorp MAS Implementation Tasks

This document contains all tasks needed to build the Multi-Agent System that solves the post-EOI contract workflow automation challenge.

**Purpose**: These tasks guide the implementation of agents that will autonomously process property deals. The tasks themselves are not the final solution - the agents they create are.

**Structure**: Tasks are organized in 9 phases (0-8), from foundation setup through final polish. Each task includes context, objectives, constraints, acceptance criteria, and test commands.

---

## Phase 0 – Foundation Setup

### Task: 0.1 – Define Python Dependencies (`requirements.txt`)

### Context

* Read:

  * `spec/MAS_Brief.md`
  * `spec/judging-criteria.md`
  * `docs/architecture.md`
  * `docs/project_plan.md`
* Reference:

  * `agent_docs/testing.md` (for pytest usage patterns)

### Objective

Create a `requirements.txt` that lists all runtime and dev dependencies needed to run the multi-agent system, parse PDFs/emails, and run tests.

### Constraints

* Must use pattern-based logic (no hardcoded demo values)
* Must include docstrings and type hints where applicable (e.g. helper scripts, if any)
* Must follow existing code conventions in `src/`
* Use broadly compatible version specifiers (e.g. `^` or `>=, <`) to avoid over‑pinning
* Include both runtime deps (PDF parsing, dates, SQLite, HTTP/LLM client if used) and dev deps (`pytest`, `mypy`/`ruff` if desired)

### Acceptance Criteria

* [ ] `requirements.txt` includes libraries to cover: PDF parsing, email/date handling, SQLite, and testing (pytest)
* [ ] `pip install -r requirements.txt` succeeds in a clean Python 3.11 environment with no resolution errors

### Output

* Create: `requirements.txt`
* Test with:
  `pip install -r requirements.txt`

---

### Task: 0.2 – Initialise `src/` Package Structure

### Context

* Read:

  * `folder-structure.txt` (or `spec/` + `docs/architecture.md`) 
* Reference:

  * `src/` layout described in `folder-structure.txt`

### Objective

Create `__init__.py` files and any missing package folders so that `src/`, `src/agents/`, `src/agents/prompts/`, `src/utils/`, and `src/orchestrator/` are valid Python packages.

### Constraints

* Must use pattern-based logic (no hardcoded demo values)
* Must include docstrings and type hints in any non‑empty modules
* Must follow existing code conventions in `src/`
* `__init__.py` files should be minimal, only exporting top‑level symbols if clearly needed later

### Acceptance Criteria

* [ ] The following packages import without errors: `src`, `src.agents`, `src.agents.prompts`, `src.utils`, `src.orchestrator`
* [ ] Running `python -c "import src, src.agents, src.utils, src.orchestrator"` from project root exits with status code 0

### Output

* Create:

  * `src/__init__.py`
  * `src/agents/__init__.py`
  * `src/agents/prompts/__init__.py`
  * `src/utils/__init__.py`
  * `src/orchestrator/__init__.py`
* Test with:
  `python -c "import src, src.agents, src.utils, src.orchestrator"`

---

### Task: 0.3 – Shared Test Fixtures in `tests/conftest.py`

### Context

* Read:

  * `ground-truth/eoi_extracted.json`
  * `ground-truth/v1_extracted.json`
  * `ground-truth/v2_extracted.json`
  * `ground-truth/v1_mismatches.json`
  * `ground-truth/expected_outputs.json`
  * `emails_manifest.json`
* Reference:

  * `agent_docs/testing.md`

### Objective

Create `tests/conftest.py` providing reusable pytest fixtures for EOI data, contract data (V1/V2), mismatches, email manifest, and expected outputs.

### Constraints

* Must use pattern-based logic (no hardcoded demo values)
* Must include docstrings and type hints for all fixtures
* Must follow existing code conventions in `tests/`
* Fixtures should read JSON from disk at runtime, not embed JSON inline
* Paths must be robust (e.g. use `Path(__file__).parent.parent` or similar)

### Acceptance Criteria

* [ ] Pytest discovers fixtures without raising `ImportError` or `FileNotFoundError`
* [ ] Running `pytest --maxfail=1 --disable-warnings -q` in an otherwise empty tests suite completes without error (even if zero tests are collected)

### Output

* Create: `tests/conftest.py`
* Test with:
  `pytest --maxfail=1 --disable-warnings -q`

---

## Phase 1 – Utilities First

### Task: 1.1 – Implement `pdf_parser` Utilities

### Context

* Read:

  * `agent_docs/extraction.md`
  * `data/source-of-truth/EOI_John_JaneSmith.pdf`
  * `data/contracts/CONTRACT_V1.pdf`
  * `data/contracts/CONTRACT_V2.pdf`
* Reference:

  * `ground-truth/eoi_extracted.json`
  * `ground-truth/v1_extracted.json`
  * `ground-truth/v2_extracted.json`

### Objective

Create `src/utils/pdf_parser.py` with reusable functions to extract text (and optionally simple tables) from EOI and contract PDFs for downstream extraction logic.

### Constraints

* Must use pattern-based logic (no hardcoded demo values)
* Must include docstrings and type hints
* Must follow existing code conventions in `src/`
* Should provide at least:

  * `read_pdf_text(path: Path | str) -> str`
  * `read_pdf_pages(path: Path | str) -> list[str]`
* Must not embed any OneCorp‑specific values; logic must work for other similar PDFs

### Acceptance Criteria

* [ ] Calling `read_pdf_text` on the EOI and contract PDFs returns non‑empty strings containing obvious anchors (e.g. “Expression of Interest”, “CONTRACT OF SALE OF REAL ESTATE”)
* [ ] Utility functions are pure (no global state) and handle missing files by raising clear exceptions

### Output

* Create: `src/utils/pdf_parser.py`
* Test with:
  `pytest tests/test_utils.py::test_pdf_parser_basic` (to be added in Task 1.4)

---

### Task: 1.2 – Implement `email_parser` Utilities

### Context

* Read:

  * `agent_docs/emails.md`
  * `data/emails/incoming/*.txt`
  * `data/emails/templates/*.txt`
  * `emails_manifest.json`
* Reference:

  * MAS brief email requirements in `spec/MAS_Brief.md`

### Objective

Create `src/utils/email_parser.py` that parses raw `.txt` email files into a structured Python object (e.g. dataclass or typed dict) capturing headers, body, and attachments.

### Constraints

* Must use pattern-based logic (no hardcoded demo values)
* Must include docstrings and type hints
* Must follow existing code conventions in `src/`
* Parsed model must at minimum expose: `subject`, `from_addr`, `to_addrs`, `cc_addrs`, `body`, `attachment_filenames`, and original file path
* Parser must be robust to minor formatting differences and extra whitespace

### Acceptance Criteria

* [ ] Parsing each `data/emails/incoming/*.txt` file yields a structured object that matches `emails_manifest.json` for key fields (subject, from, to, attachments)
* [ ] No parsing function assumes a particular email ID; behaviour is driven by patterns (e.g. header prefixes, blank line separating body)

### Output

* Create: `src/utils/email_parser.py`
* Test with:
  `pytest tests/test_utils.py::test_email_parser_against_manifest` (to be added in Task 1.4)

---

### Task: 1.3 – Implement `date_resolver` for Appointment Phrases

### Context

* Read:

  * `agent_docs/emails.md` (appointment date rules)
  * `data/emails/incoming/04_solicitor_approved.txt`
  * `emails_manifest.json` (note `extracted_data.appointment_datetime`)
* Reference:

  * `agent_docs/state-machine.md` (SLA timer rules)
  * `expected_outputs.json` SLA sections 

### Objective

Create `src/utils/date_resolver.py` to convert human phrases like “Thursday at 11:30am” into concrete timezone‑aware datetimes, given a reference date and timezone.

### Constraints

* Must use pattern-based logic (no hardcoded demo values)
* Must include docstrings and type hints
* Must follow existing code conventions in `src/`
* Should expose a function like:
  `def resolve_appointment_phrase(base_dt: datetime, phrase: str, tz: tzinfo | str) -> datetime: ...`
* Must support at least weekday names + time (“Thursday at 11:30am”), and be easy to extend

### Acceptance Criteria

* [ ] Resolving the phrase from `04_solicitor_approved.txt` relative to its email timestamp produces `2025-01-16T11:30:00+11:00` as per `emails_manifest.json`
* [ ] Function raises a clear error or returns `None` when it cannot confidently resolve the phrase (no silent incorrect guesses)

### Output

* Create: `src/utils/date_resolver.py`
* Test with:
  `pytest tests/test_utils.py::test_date_resolver_appointment_phrase` (to be added in Task 1.4)

---

### Task: 1.4 – Write Utility Tests (`tests/test_utils.py`)

### Context

* Read:

  * `tests/conftest.py`
  * `src/utils/pdf_parser.py`
  * `src/utils/email_parser.py`
  * `src/utils/date_resolver.py`
* Reference:

  * `agent_docs/testing.md`
  * `emails_manifest.json`

### Objective

Create `tests/test_utils.py` covering core behaviours of `pdf_parser`, `email_parser`, and `date_resolver` using the supplied dataset.

### Constraints

* Must use pattern-based logic (no hardcoded demo values)
* Must include docstrings and type hints for helper functions
* Must follow existing code conventions in `tests/`
* Tests should rely on fixtures from `conftest.py` wherever possible
* Tests should assert general properties (contains anchors, correct structure, correct datetime), not exact entire file contents

### Acceptance Criteria

* [ ] Tests validate that PDF utilities return non‑empty, reasonably long text for EOI and contracts
* [ ] Tests validate that `email_parser` output aligns with `emails_manifest.json` for all incoming emails
* [ ] Tests validate that `date_resolver` correctly resolves the solicitor appointment phrase to the expected datetime
* [ ] `pytest tests/test_utils.py -q` passes

### Output

* Create: `tests/test_utils.py`
* Test with:
  `pytest tests/test_utils.py -q`

---

## Phase 2 – Extractor Agent

### Task: 2.1 – Design `extractor_prompt.md`

### Context

* Read:

  * `agent_docs/extraction.md`
  * `spec/MAS_Brief.md`
  * `ground-truth/eoi_extracted.json`
  * `ground-truth/v1_extracted.json`
  * `ground-truth/v2_extracted.json`
* Reference:

  * `docs/architecture.md` (Extractor agent role)

### Objective

Create a robust LLM prompt in `src/agents/prompts/extractor_prompt.md` that describes how to extract EOI and contract fields into a standard JSON schema.

### Constraints

* Must use pattern-based logic (no hardcoded demo values)
* Must include clear instructions and JSON schema examples
* Must follow existing markdown style in `src/agents/prompts/`
* Prompt must cover both EOI and CONTRACT document types and specify required fields (names, emails, prices, finance, deposits, solicitor, vendor, lot, address)
* Must emphasise: no guessing, preserve numeric formats, mark missing/uncertain fields explicitly

### Acceptance Criteria

* [ ] Prompt includes a single canonical JSON schema compatible with `ground-truth/*.json`
* [ ] Prompt instructs the model to normalise finance terms (e.g. `is_subject_to_finance` boolean + `terms` string)
* [ ] Prompt makes no reference to specific OneCorp client names or file names; it remains reusable

### Output

* Create: `src/agents/prompts/extractor_prompt.md`
* Test with:
  (Manual / later integration) `pytest tests/test_extraction.py -q` after Tasks 2.2–2.4

---

### Task: 2.2 – Implement `extract_eoi()` in `extractor.py`

### Context

* Read:

  * `src/utils/pdf_parser.py`
  * `ground-truth/eoi_extracted.json`
  * `data/source-of-truth/EOI_John_JaneSmith.pdf`
* Reference:

  * `agent_docs/extraction.md`
  * `src/agents/prompts/extractor_prompt.md`

### Objective

Implement `extract_eoi(pdf_path)` in `src/agents/extractor.py` to parse the EOI PDF into a structured dict matching the EOI ground‑truth schema.

### Constraints

* Must use pattern-based logic (no hardcoded demo values)
* Must include docstrings and type hints
* Must follow existing code conventions in `src/agents/`
* Implementation may use direct parsing (regex/string rules) or LLM, but the public interface must be deterministic and testable
* Return structure must align with `ground-truth/eoi_extracted.json` (fields, nesting, data types)

### Acceptance Criteria

* [ ] `extract_eoi("data/source-of-truth/EOI_John_JaneSmith.pdf")` returns a dict whose keys and types match `eoi_extracted.json`
* [ ] All required fields (purchasers, property, pricing, finance, solicitor, deposits, introducer) are present
* [ ] `tests/test_extraction.py::test_eoi_extraction_matches_ground_truth` passes

### Output

* Create / Update: `src/agents/extractor.py` (add `extract_eoi`)
* Test with:
  `pytest tests/test_extraction.py::test_eoi_extraction_matches_ground_truth -q`

---

### Task: 2.3 – Implement `extract_contract()` in `extractor.py`

### Context

* Read:

  * `src/utils/pdf_parser.py`
  * `ground-truth/v1_extracted.json`
  * `ground-truth/v2_extracted.json`
  * `data/contracts/CONTRACT_V1.pdf`
  * `data/contracts/CONTRACT_V2.pdf`
* Reference:

  * `agent_docs/extraction.md`
  * `src/agents/prompts/extractor_prompt.md`

### Objective

Implement `extract_contract(pdf_path)` in `src/agents/extractor.py` that extracts contract data from both V1 and V2 into the shared contract schema.

### Constraints

* Must use pattern-based logic (no hardcoded demo values)
* Must include docstrings and type hints
* Must follow existing code conventions in `src/agents/`
* Must correctly parse: purchasers, property, pricing, finance terms, solicitor, deposits, vendor
* Implementation must not rely on knowing whether it’s V1 or V2 up front; it should infer from content or simply parse generically

### Acceptance Criteria

* [ ] `extract_contract` applied to V1 and V2 returns dicts whose structure matches `v1_extracted.json` and `v2_extracted.json`
* [ ] Numeric fields (prices, deposits) are parsed as numbers, not strings
* [ ] `tests/test_extraction.py::test_contract_extraction_v1_v2_match_ground_truth` passes

### Output

* Update: `src/agents/extractor.py` (add `extract_contract`)
* Test with:
  `pytest tests/test_extraction.py::test_contract_extraction_v1_v2_match_ground_truth -q`

---

### Task: 2.4 – Extraction Tests (`tests/test_extraction.py`)

### Context

* Read:

  * `tests/conftest.py`
  * `src/agents/extractor.py`
  * `ground-truth/eoi_extracted.json`
  * `ground-truth/v1_extracted.json`
  * `ground-truth/v2_extracted.json`
* Reference:

  * `agent_docs/testing.md`

### Objective

Create `tests/test_extraction.py` to validate that `extract_eoi` and `extract_contract` reproduce the ground‑truth JSON structures for EOI and both contracts.

### Constraints

* Must use pattern-based logic (no hardcoded demo values)
* Must include docstrings and type hints for helper functions
* Must follow existing code conventions in `tests/`
* Tests should allow for benign differences (e.g. whitespace) but enforce exact values for key fields (names, emails, lot, price, finance)

### Acceptance Criteria

* [ ] Tests verify that EOI extraction exactly matches canonical values for critical fields (e.g. purchaser names, emails, lot, total price, finance terms)
* [ ] Tests verify that V1 and V2 extractions match their ground‑truth JSONs
* [ ] `pytest tests/test_extraction.py -q` passes

### Output

* Create: `tests/test_extraction.py`
* Test with:
  `pytest tests/test_extraction.py -q`

---

## Phase 3 – Router Agent

### Task: 3.1 – Design `router_prompt.md`

### Context

* Read:

  * `agent_docs/emails.md`
  * `spec/MAS_Brief.md`
  * `emails_manifest.json`
* Reference:

  * `docs/architecture.md` (Router role)

### Objective

Create `src/agents/prompts/router_prompt.md` that explains how to classify emails into event types (EOI_SIGNED, CONTRACT_FROM_VENDOR, SOLICITOR_APPROVED_WITH_APPOINTMENT, DOCUSIGN_RELEASED, DOCUSIGN_BUYER_SIGNED, DOCUSIGN_EXECUTED, etc.).

### Constraints

* Must use pattern-based logic (no hardcoded demo values)
* Must include clear instructions and event type definitions
* Must follow existing markdown style in `src/agents/prompts/`
* Prompt must describe how to use sender, subject line, body, and attachments as features
* Must instruct the model to output a small JSON object with `event_type` and any extracted metadata (e.g. appointment phrase)

### Acceptance Criteria

* [ ] Prompt lists all event types present in `emails_manifest.json`
* [ ] Prompt describes at least one example for each event type based on the dataset (without copying raw email text)
* [ ] Prompt instructs extraction of appointment phrases when present

### Output

* Create: `src/agents/prompts/router_prompt.md`
* Test with:
  (Manual / later integration) `pytest tests/test_email_classification.py -q` after Tasks 3.2–3.3

---

### Task: 3.2 – Implement `classify_email()` in `router.py`

### Context

* Read:

  * `src/utils/email_parser.py`
  * `emails_manifest.json`
  * `data/emails/incoming/*.txt`
* Reference:

  * `agent_docs/emails.md`
  * `src/agents/prompts/router_prompt.md`

### Objective

Implement `classify_email(parsed_email)` in `src/agents/router.py` that maps a parsed email object to a structured event with `event_type` and any relevant metadata.

### Constraints

* Must use pattern-based logic (no hardcoded demo values)
* Must include docstrings and type hints
* Must follow existing code conventions in `src/agents/`
* Logic should rely on patterns (sender domains, subject contains, body keywords, attachments) derived from `emails_manifest.json` and templates
* Must be deterministic (no LLM calls inside this function for now)

### Acceptance Criteria

* [ ] All incoming emails in the dataset are classified into the correct `event_type` as specified in `emails_manifest.json`
* [ ] For solicitor approval emails, the returned event includes the appointment phrase (e.g. “Thursday at 11:30am”) for later resolution
* [ ] `pytest tests/test_email_classification.py::test_router_classifies_all_emails` passes

### Output

* Create / Update: `src/agents/router.py`
* Test with:
  `pytest tests/test_email_classification.py::test_router_classifies_all_emails -q`

---

### Task: 3.3 – Email Classification Tests (`tests/test_email_classification.py`)

### Context

* Read:

  * `tests/conftest.py`
  * `src/utils/email_parser.py`
  * `src/agents/router.py`
  * `emails_manifest.json`
* Reference:

  * `agent_docs/testing.md`

### Objective

Create `tests/test_email_classification.py` to validate that each email in the dataset is classified to the correct event type and that required metadata is extracted.

### Constraints

* Must use pattern-based logic (no hardcoded demo values)
* Must include docstrings and type hints for helper functions
* Must follow existing code conventions in `tests/`
* Tests should iterate over all INPUT emails from `emails_manifest.json`

### Acceptance Criteria

* [ ] Tests confirm that each email’s `event_type` from `classify_email` matches the manifest
* [ ] Tests confirm that solicitor approval events contain the appointment phrase
* [ ] `pytest tests/test_email_classification.py -q` passes

### Output

* Create: `tests/test_email_classification.py`
* Test with:
  `pytest tests/test_email_classification.py -q`

---

## Phase 4 – Auditor Agent

### Task: 4.1 – Design `auditor_prompt.md`

### Context

* Read:

  * `agent_docs/comparison.md`
  * `spec/MAS_Brief.md`
  * `ground-truth/v1_mismatches.json`
* Reference:

  * `docs/architecture.md` (Auditor role)

### Objective

Create `src/agents/prompts/auditor_prompt.md` that explains how to compare EOI vs contract data, identify mismatches, and classify severity/risk.

### Constraints

* Must use pattern-based logic (no hardcoded demo values)
* Must include clear mismatch schema (field, display name, eoi_value, contract_value, severity, rationale)
* Must follow existing markdown style in `src/agents/prompts/`
* Prompt must describe how to compute `is_valid`, `mismatch_count`, and `risk_score`
* Must emphasise not to mark documents as valid when any HIGH mismatches exist

### Acceptance Criteria

* [ ] Prompt includes mismatch fields aligned with `v1_mismatches.json`
* [ ] Prompt defines severity levels (LOW/MEDIUM/HIGH) and guidance
* [ ] Prompt describes how to generate `amendment_recommendation` and `next_action`

### Output

* Create: `src/agents/prompts/auditor_prompt.md`
* Test with:
  (Manual / later integration) `pytest tests/test_comparison.py -q` after Tasks 4.2–4.3

---

### Task: 4.2 – Implement `compare_contract_to_eoi()` in `auditor.py`

### Context

* Read:

  * `ground-truth/eoi_extracted.json`
  * `ground-truth/v1_extracted.json`
  * `ground-truth/v2_extracted.json`
  * `ground-truth/v1_mismatches.json`
* Reference:

  * `agent_docs/comparison.md`
  * `src/agents/prompts/auditor_prompt.md`

### Objective

Implement `compare_contract_to_eoi(eoi_data, contract_data)` in `src/agents/auditor.py` that returns a structured comparison result including mismatches, severity, and overall validity.

### Constraints

* Must use pattern-based logic (no hardcoded demo values)
* Must include docstrings and type hints (consider a `@dataclass` for `ComparisonResult`)
* Must follow existing code conventions in `src/agents/`
* Logic must be driven by field mappings (e.g. `pricing.total_price`, `finance.is_subject_to_finance`) rather than inline constants

### Acceptance Criteria

* [ ] Comparing EOI vs V1 returns exactly 5 mismatches with fields and values matching `v1_mismatches.json`
* [ ] Comparing EOI vs V2 returns zero mismatches and `is_valid = True`
* [ ] `risk_score` and `next_action` fields are populated consistently for both cases
* [ ] `pytest tests/test_comparison.py::test_v1_and_v2_comparison` passes

### Output

* Create / Update: `src/agents/auditor.py`
* Test with:
  `pytest tests/test_comparison.py::test_v1_and_v2_comparison -q`

---

### Task: 4.3 – Comparison Tests (`tests/test_comparison.py`)

### Context

* Read:

  * `tests/conftest.py`
  * `src/agents/auditor.py`
  * `ground-truth/v1_mismatches.json`
* Reference:

  * `agent_docs/testing.md`

### Objective

Create `tests/test_comparison.py` to validate contract vs EOI comparison, including mismatches, severity, risk score, and validity.

### Constraints

* Must use pattern-based logic (no hardcoded demo values)
* Must include docstrings and type hints
* Must follow existing code conventions in `tests/`
* Tests should check fields and counts, not just booleans

### Acceptance Criteria

* [ ] Tests assert that V1 produces 5 mismatches matching ground truth (field names and formatted values)
* [ ] Tests assert that V2 produces no mismatches and `is_valid` is True
* [ ] Tests assert that V1 yields a HIGH `risk_score` and `next_action` indicates a discrepancy alert
* [ ] `pytest tests/test_comparison.py -q` passes

### Output

* Create: `tests/test_comparison.py`
* Test with:
  `pytest tests/test_comparison.py -q`

---

## Phase 5 – Comms Agent

### Task: 5.1 – Design `comms_prompt.md`

### Context

* Read:

  * `agent_docs/emails.md` (templates + triggers)
  * `spec/MAS_Brief.md` (section C & D: required outbound emails and alerts)
* Reference:

  * `data/emails/templates/03_contract_to_solicitor.txt`
  * `data/emails/templates/05_vendor_release_request.txt`
  * `ground-truth/expected_outputs.json` (for alert emails) 

### Objective

Create `src/agents/prompts/comms_prompt.md` that instructs the LLM on how to generate the four required email types given structured context.

### Constraints

* Must use pattern-based logic (no hardcoded demo values)
* Must include clear templates and placeholder fields (e.g. `{lot_number}`, `{purchaser_names}`)
* Must follow existing markdown style in `src/agents/prompts/`
* Prompt must cover:

  * Contract to solicitor
  * Vendor DocuSign release request
  * Internal discrepancy alert
  * SLA overdue alert

### Acceptance Criteria

* [ ] Prompt documents required headers (From/To/Subject) and body structure for all 4 emails
* [ ] Prompt describes how to include mismatch details and recommendations in discrepancy alerts
* [ ] Prompt describes SLA alert content (property, appointment, time elapsed, recommended action)

### Output

* Create: `src/agents/prompts/comms_prompt.md`
* Test with:
  (Manual / later integration) `pytest tests/test_comms.py -q` after Tasks 5.2–5.3

---

### Task: 5.2 – Implement `comms.py` Email Builders

### Context

* Read:

  * `spec/MAS_Brief.md` (email requirements)
  * `data/emails/templates/*.txt`
  * `ground-truth/expected_outputs.json`
* Reference:

  * `agent_docs/emails.md`
  * `src/agents/prompts/comms_prompt.md`

### Objective

Implement all four email builder functions in `src/agents/comms.py` to generate structured email objects from context dicts.

### Constraints

* Must use pattern-based logic (no hardcoded demo values)
* Must include docstrings and type hints
* Must follow existing code conventions in `src/agents/`
* Functions to implement (names can be refined, but must be clear and typed):

  * `build_contract_to_solicitor_email(context)`
  * `build_vendor_release_email(context)`
  * `build_discrepancy_alert_email(context)`
  * `build_sla_overdue_alert_email(context)`
* Builders must take structured context (deal, comparison result, appointment, SLA status) and return an email model (e.g. dataclass) that can be rendered to text

### Acceptance Criteria

* [ ] Contract-to-solicitor builder produces an email matching the sample template for Lot 95 / Smith (subject, recipients, attachment name) when given equivalent context
* [ ] Vendor-release builder produces an email structurally matching the sample request with DocuSign language
* [ ] Discrepancy alert and SLA alert builders produce bodies containing all required fields as specified in `MAS_Brief.md` / `expected_outputs.json`
* [ ] `pytest tests/test_comms.py::test_email_builders_against_expected_outputs -q` passes

### Output

* Create / Update: `src/agents/comms.py`
* Test with:
  `pytest tests/test_comms.py::test_email_builders_against_expected_outputs -q`

---

### Task: 5.3 – Comms Tests (`tests/test_comms.py`)

### Context

* Read:

  * `tests/conftest.py`
  * `src/agents/comms.py`
  * `ground-truth/expected_outputs.json`
* Reference:

  * `agent_docs/testing.md`
  * `agent_docs/emails.md`

### Objective

Create `tests/test_comms.py` to validate all four email builders against canonical expected outputs.

### Constraints

* Must use pattern-based logic (no hardcoded demo values)
* Must include docstrings and type hints
* Must follow existing code conventions in `tests/`
* Tests may allow minor whitespace differences but must enforce headers, key phrases, and dynamic fields (names, lot, prices, dates)

### Acceptance Criteria

* [ ] Tests confirm that generated emails for the Smith / Lot 95 scenario match the structure and key content in `expected_outputs.json`
* [ ] Tests assert that discrepancy alerts list each mismatch with EOI and contract values
* [ ] Tests assert that SLA alerts include property, appointment, time elapsed, and a “Recommended Action” section
* [ ] `pytest tests/test_comms.py -q` passes

### Output

* Create: `tests/test_comms.py`
* Test with:
  `pytest tests/test_comms.py -q`

---

## Phase 6 – Orchestrator

### Task: 6.1 – Implement Workflow `state_machine.py`

### Context

* Read:

  * `agent_docs/state-machine.md`
  * `spec/MAS_Brief.md`
  * `ground-truth/expected_outputs.json` (workflow_stages & sla_test_scenario)
* Reference:

  * `docs/architecture.md`

### Objective

Implement `src/orchestrator/state_machine.py` defining a State enum, transition rules, and guard conditions for the Lot 95 workflow (and extensible for more deals).

### Constraints

* Must use pattern-based logic (no hardcoded demo values)
* Must include docstrings and type hints
* Must follow existing code conventions in `src/orchestrator/`
* State machine must support at least the states listed in `workflow_stages` (EOI_RECEIVED → CONTRACT_V1_RECEIVED → … → EXECUTED)
* Transitions must be driven by events (router events, comparison results, SLA events), not by direct function calls bypassing the model

### Acceptance Criteria

* [ ] State enum covers all states in `expected_outputs.json.workflow_stages`
* [ ] Transition logic enforces versioning (V2 supersedes V1) and prevents invalid transitions
* [ ] A simple simulation using the manifest’s events reproduces the state sequence in `workflow_stages`
* [ ] `pytest tests/test_state_transitions.py::test_happy_path_transitions -q` passes

### Output

* Create: `src/orchestrator/state_machine.py`
* Test with:
  `pytest tests/test_state_transitions.py::test_happy_path_transitions -q`

---

### Task: 6.2 – Implement `deal_store.py` (SQLite Persistence)

### Context

* Read:

  * `agent_docs/state-machine.md` (deal data model)
  * `ground-truth/expected_outputs.json` (deal_id, stages)
* Reference:

  * `docs/architecture.md` (persistence layer expectations)

### Objective

Create `src/orchestrator/deal_store.py` to persist deals, states, events, and SLA timers using SQLite.

### Constraints

* Must use pattern-based logic (no hardcoded demo values)
* Must include docstrings and type hints
* Must follow existing code conventions in `src/orchestrator/`
* Should provide a small API, e.g.:

  * `upsert_deal(deal)`
  * `record_event(deal_id, event)`
  * `update_state(deal_id, new_state)`
  * `get_deal(deal_id)`
  * `get_pending_sla_checks(now)`
* Must use standard library `sqlite3` (no heavy ORM required)

### Acceptance Criteria

* [ ] Deals and events for `LOT95_FAKE_RISE_VIC_3336` can be persisted and retrieved without data loss
* [ ] Persisted state sequence matches the state machine transitions when replaying events
* [ ] `pytest tests/test_state_transitions.py::test_persistence_of_deal_state -q` passes

### Output

* Create: `src/orchestrator/deal_store.py`
* Test with:
  `pytest tests/test_state_transitions.py::test_persistence_of_deal_state -q`

---

### Task: 6.3 – Implement `sla_monitor.py`

### Context

* Read:

  * `agent_docs/state-machine.md` (SLA rules)
  * `emails_manifest.json` (`sla_rules` section)
  * `data/emails/incoming/04_solicitor_approved.txt`
* Reference:

  * `src/utils/date_resolver.py`
  * `ground-truth/expected_outputs.json.sla_test_scenario` 

### Objective

Create `src/orchestrator/sla_monitor.py` to schedule and evaluate SLA deadlines (e.g. buyer signature due 2 days after appointment).

### Constraints

* Must use pattern-based logic (no hardcoded demo values)
* Must include docstrings and type hints
* Must follow existing code conventions in `src/orchestrator/`
* Must integrate with `deal_store` to:

  * Register SLA timers when solicitor appointment is set
  * Cancel SLA timers when buyer signs
  * Emit SLA overdue events when deadlines pass

### Acceptance Criteria

* [ ] For the happy path (with buyer-signed email present), SLA timer is scheduled then cancelled before firing
* [ ] For the SLA test scenario (with buyer-signed email removed), SLA monitor emits an SLA overdue event at the expected time per `sla_test_scenario`
* [ ] `pytest tests/test_state_transitions.py::test_sla_overdue_scenario -q` passes

### Output

* Create: `src/orchestrator/sla_monitor.py`
* Test with:
  `pytest tests/test_state_transitions.py::test_sla_overdue_scenario -q`

---

### Task: 6.4 – State Transition Tests (`tests/test_state_transitions.py`)

### Context

* Read:

  * `tests/conftest.py`
  * `src/agents/router.py`
  * `src/agents/auditor.py`
  * `src/orchestrator/state_machine.py`
  * `src/orchestrator/deal_store.py`
  * `src/orchestrator/sla_monitor.py`
  * `emails_manifest.json`
  * `ground-truth/expected_outputs.json`
* Reference:

  * `agent_docs/testing.md`
  * `agent_docs/state-machine.md`

### Objective

Create `tests/test_state_transitions.py` to validate the orchestrated workflow, including state sequence and SLA behaviour.

### Constraints

* Must use pattern-based logic (no hardcoded demo values)
* Must include docstrings and type hints
* Must follow existing code conventions in `tests/`
* Tests should replay the events described in `workflow_stages` and `sla_test_scenario`

### Acceptance Criteria

* [ ] Happy-path test reproduces the state sequence from `EOI_RECEIVED` through `EXECUTED` as in `workflow_stages`
* [ ] SLA test removes the buyer-signed event and asserts that an SLA overdue alert is generated at the right time
* [ ] Guards prevent invalid transitions (e.g. cannot send to solicitor before a valid contract is confirmed)
* [ ] `pytest tests/test_state_transitions.py -q` passes

### Output

* Create: `tests/test_state_transitions.py`
* Test with:
  `pytest tests/test_state_transitions.py -q`

---

## Phase 7 – Integration

### Task: 7.1 – CLI Entry Point in `src/main.py`

### Context

* Read:

  * `docs/demo-script.md`
  * `docs/architecture.md`
  * `emails_manifest.json`
  * `ground-truth/expected_outputs.json`
* Reference:

  * `spec/MAS_Brief.md` (end-to-end demo requirements)

### Objective

Implement `src/main.py` as a CLI entry point that runs the full demo workflow for the provided dataset and prints key agent interactions and state transitions.

### Constraints

* Must use pattern-based logic (no hardcoded demo values)
* Must include docstrings and type hints
* Must follow existing code conventions in `src/`
* CLI should:

  * Ingest EOI and contracts
  * Process emails in manifest order through Router, Extractor, Auditor, Orchestrator, SLA monitor, and Comms
  * Log/print clear, concise messages suitable for a 3-minute demo

### Acceptance Criteria

* [ ] Running `python -m src.main` (or `python src/main.py`) processes the Lot 95 dataset end-to-end without errors
* [ ] Console output shows: V1 discrepancies → discrepancy alert → V2 validated → solicitor approval & appointment → vendor release request → DocuSign emails → executed state → SLA test (when configured)
* [ ] `pytest tests/test_end_to_end.py::test_demo_entrypoint -q` passes

### Output

* Create / Update: `src/main.py`
* Test with:
  `pytest tests/test_end_to_end.py::test_demo_entrypoint -q`

---

### Task: 7.2 – End-to-End Test (`tests/test_end_to_end.py`)

### Context

* Read:

  * All key modules: `src/agents/*`, `src/orchestrator/*`, `src/utils/*`, `src/main.py`
  * `emails_manifest.json`
  * `ground-truth/expected_outputs.json`
* Reference:

  * `agent_docs/testing.md`

### Objective

Create `tests/test_end_to_end.py` to validate the full workflow and generated emails against `expected_outputs.json`.

### Constraints

* Must use pattern-based logic (no hardcoded demo values)
* Must include docstrings and type hints
* Must follow existing code conventions in `tests/`
* Test should orchestrate the same flow as `src/main.py`, but in a programmable way (no reliance on stdout parsing)

### Acceptance Criteria

* [ ] Test confirms that all expected outbound emails (solicitor, vendor release, discrepancy alert, SLA alert in the SLA scenario) are generated with correct structure and key content
* [ ] Test confirms that final deal state is `EXECUTED` for the normal run
* [ ] Test confirms that SLA overdue alert is only generated in the explicitly simulated SLA failure scenario
* [ ] `pytest tests/test_end_to_end.py -q` passes

### Output

* Create: `tests/test_end_to_end.py`
* Test with:
  `pytest tests/test_end_to_end.py -q`

---

### Task: 7.3 – Demo Script Doc (`docs/demo-script.md`)

### Context

* Read:

  * `spec/MAS_Brief.md`
  * `spec/judging-criteria.md`
  * `docs/architecture.md`
  * `src/main.py` behaviour
* Reference:

  * Existing `docs/demo-script.md` (if present) as a starting point

### Objective

Write or refine `docs/demo-script.md` into a tight 3-minute demo walkthrough aligned with how `src/main.py` runs and what the judges care about.

### Constraints

* Must use pattern-based logic (no hardcoded demo values)
* Must be clear, step-by-step, with specific CLI commands and which logs to point at
* Must emphasise multi-agent collaboration, error handling, and SLA logic per judging criteria

### Acceptance Criteria

* [ ] Script fits into ~3 minutes when read aloud and executed
* [ ] Script clearly calls out each agent’s role (Router, Extractor, Auditor, Comms, Orchestrator/SLA)
* [ ] Script explicitly maps key moments to judging criteria (architecture, collaboration, safety, real-world value)
* [ ] Document is linked from `README.md`

### Output

* Create / Update: `docs/demo-script.md`
* Test with:
  Manual dry run following the script using `python -m src.main`

---

## Phase 8 – Polish

### Task: 8.1 – Architecture Diagram Asset

### Context

* Read:

  * `docs/architecture.md`
  * `agent_docs/state-machine.md`
  * `docs/demo-script.md` 
* Reference:

  * `spec/judging-criteria.md` (System Design & Collaboration sections)

### Objective

Create an up-to-date architecture diagram (SVG or PNG) showing agents, data stores, and message flows, suitable for use in the README and demo.

### Constraints

* Must use pattern-based logic (no hardcoded demo values)
* Must clearly label agents, key tools, and state machine
* File should be reasonably small and stored under `assets/` (e.g. `assets/architecture.svg`)

### Acceptance Criteria

* [ ] Diagram reflects the actual implemented architecture (Router, Extractor, Auditor, Comms, Orchestrator, SLA monitor, Deal store)
* [ ] Diagram visually distinguishes data flow (EOI/contract, emails) and control flow (events, state transitions)
* [ ] Diagram is referenced in `docs/architecture.md` and `README.md`

### Output

* Create: `assets/architecture.svg` (or `.png`)
* Test with:
  Open file visually and confirm clarity; no automated test required

---

### Task: 8.2 – Finalise `README.md`

### Context

* Read:

  * Existing `README.md`
  * `spec/MAS_Brief.md`
  * `spec/judging-criteria.md`
  * `docs/demo-script.md`
* Reference:

  * `docs/INDEX.md` (doc index)

### Objective

Update `README.md` with clear setup instructions, how to run the demo, how to run tests, and a concise explanation of the multi-agent architecture.

### Constraints

* Must use pattern-based logic (no hardcoded demo values)
* Must include:

  * Quickstart section (install, run demo, run tests)
  * Short agent overview
  * Link to architecture diagram and demo script
  * Note on safety / guardrails and limitations
* Language should be concise and accessible to judges unfamiliar with the codebase

### Acceptance Criteria

* [ ] Someone new to the repo can clone, install, run the demo, and run tests using only the README
* [ ] README references the architecture diagram and demo script
* [ ] README mentions how the system meets the MAS brief and judging criteria at a high level

### Output

* Update: `README.md`
* Test with:
  Manual copy-paste of commands from README into a clean environment

---

### Task: 8.3 – Optional Demo Recording Instructions

### Context

* Read:

  * `docs/demo-script.md`
  * `README.md`
* Reference:

  * `spec/judging-criteria.md` (Presentation & UX)

### Objective

Provide a short guide (e.g. `docs/demo-recording.md` or README section) on how to record a terminal or screen demo of the system following the demo script.

### Constraints

* Must use pattern-based logic (no hardcoded demo values)
* Must be tool-agnostic where possible (e.g. suggest `asciinema` or common screen recorders, but not required)
* Instructions should be optional and non‑blocking for running the code

### Acceptance Criteria

* [ ] Document clearly explains how to run the demo commands while recording
* [ ] Document links back to `docs/demo-script.md`
* [ ] Judges or teammates could reproduce a similar recording by following the steps

### Output

* Create: `docs/demo-recording.md` (or new “Recording the Demo” section in `README.md`)
* Test with:
  Manual trial recording using the described steps (no automated test required)


