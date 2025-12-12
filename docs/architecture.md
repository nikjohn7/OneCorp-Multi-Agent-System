# System Architecture

## Overview

The OneCorp Multi-Agent System (MAS) automates the post-EOI contract workflow using four LLM-based agents coordinated by a deterministic orchestrator.

**Visual Architecture Diagram:** [`../assets/architecture.svg`](../assets/architecture.svg)

The diagram shows all agents, data flows (blue solid arrows), control flows (red dashed arrows), and the complete workflow from EOI to executed contract.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           SHARED INBOX                                       │
│                    (support@onecorpaustralia.com.au)                        │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                   ROUTER AGENT (Claude Haiku 4.5)                            │
│  • Classifies incoming emails by event type                                  │
│  • Extracts key identifiers (lot, purchasers, property)                     │
│  • Resolves relative dates ("Thursday at 11:30am")                          │
│  • Maps emails to existing deals                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    ▼                               ▼
        ┌───────────────────┐           ┌───────────────────┐
        │   EOI Attachment  │           │ Contract Attachment│
        └─────────┬─────────┘           └─────────┬─────────┘
                  │                               │
                  ▼                               ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                   EXTRACTOR AGENT (Claude Haiku 4.5)                         │
│  • Parses PDFs (EOI, contracts)                                              │
│  • Extracts structured fields with confidence scores                         │
│  • Supports targeted re-extraction on request                                │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    AUDITOR AGENT (Qwen3-235B)                                │
│  • Compares contract fields against EOI (source of truth)                   │
│  • Detects mismatches with severity classification                          │
│  • Generates amendment recommendations                                       │
│  • Assigns risk scores                                                       │
│  • Can request re-extraction for low-confidence fields                      │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      ORCHESTRATOR (Deterministic)                            │
│  • Manages deal state machine                                                │
│  • Enforces workflow rules and guardrails                                   │
│  • Tracks contract versions (superseding logic)                             │
│  • Schedules and evaluates SLA timers                                       │
│  • Triggers appropriate email generation                                     │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     COMMS AGENT (Qwen3-235B)                                 │
│  • Generates outbound emails from templates                                  │
│  • Contract to Solicitor                                                     │
│  • Vendor DocuSign Release Request                                          │
│  • Discrepancy Alert (internal)                                             │
│  • SLA Overdue Alert (internal)                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Design for Generalizability

### Core Principle

This system is designed to process **any property deal**, not just the demo dataset. The demo (Lot 95, Fake Rise) provides concrete test cases, but the agents use pattern-based logic that works for any input.

### What Generalizes

| Component | Demo Example | Generalized Approach |
|-----------|--------------|---------------------|
| **Lot extraction** | "95" | Pattern: `Lot\s*#?\s*(\d+)` matches any lot number |
| **Price extraction** | "$550,000" | Pattern: currency format after "Total Price" label |
| **Finance terms** | "NOT subject to finance" | Semantic parsing of negation patterns |
| **Email classification** | 8 specific emails | Sender domain + subject patterns match any similar email |
| **State transitions** | Lot 95 workflow | Same state machine applies to any deal ID |

### What's Demo-Specific (Test Fixtures)

The `ground-truth/` files contain expected values for the demo dataset:

```
ground-truth/
├── eoi_extracted.json      # Expected: {"lot_number": "95", ...}
├── v1_extracted.json       # Expected: {"lot_number": "59", ...}  (has errors)
├── v1_mismatches.json      # Expected: 5 specific mismatches
└── expected_outputs.json   # Expected emails and states
```

**These are test fixtures for validation, not runtime data.** Agents should never read these files during normal operation.

### Generalization Test

A well-implemented system could process a hypothetical "Lot 42, Example Estate NSW 2000" with:
- Different purchaser names
- Different prices
- Different solicitor
- Different vendor email

...using the **exact same code**, because the logic is pattern-based.

### Anti-Patterns to Avoid

```python
# ❌ WRONG: Hardcoded value
if lot_number == "95":
    return True

# ❌ WRONG: Demo-specific check
if "Fake Rise" in address:
    return valid

# ❌ WRONG: Reading ground truth as source
expected = load_json('ground-truth/eoi_extracted.json')
return extracted_data == expected

# ✅ CORRECT: Pattern-based extraction
lot_match = re.search(r"Lot\s*#?\s*(\d+)", text)
return lot_match.group(1) if lot_match else None

# ✅ CORRECT: Field-by-field comparison
for field in COMPARABLE_FIELDS:
    if eoi[field] != contract[field]:
        mismatches.append(field)
```

---

## Agent Specifications

### Router Agent

| Attribute | Value |
|-----------|-------|
| **Model** | Claude Haiku 4.5 via Anthropic |
| **Input** | Raw email (subject, body, sender, recipients, timestamp) |
| **Output** | Event classification, deal mapping, extracted identifiers |
| **Key Capability** | Relative date resolution (e.g., "Thursday at 11:30am" → concrete datetime) |

**Event Types Detected:**
- `EOI_SIGNED` — New deal initiation
- `CONTRACT_FROM_VENDOR` — Contract PDF received
- `SOLICITOR_APPROVED_WITH_APPOINTMENT` — Legal approval + signing time
- `DOCUSIGN_RELEASED` — "Please sign" notification
- `DOCUSIGN_BUYER_SIGNED` — Buyer completed signing
- `DOCUSIGN_EXECUTED` — All parties signed

### Extractor Agent

| Attribute | Value |
|-----------|-------|
| **Model** | Claude Haiku 4.5 via Anthropic (standard and re-extraction) |
| **Input** | PDF document, document type indicator |
| **Output** | Structured fields with confidence scores |
| **Key Capability** | Semantic parsing of finance terms, table extraction |

**Critical Fields Extracted:**
- Purchaser details (names, emails, mobiles)
- Property details (lot number, address, project)
- Financial terms (total price, land/build split, deposits)
- Finance terms (subject to finance: yes/no)
- Solicitor details

### Auditor Agent

| Attribute | Value |
|-----------|-------|
| **Model** | Deterministic core + Qwen3-235B via DeepInfra (LLM mode) |
| **Input** | EOI fields, Contract fields |
| **Output** | Validation result, mismatches, risk score, amendment recommendation |
| **Key Capability** | Semantic comparison (boolean finance terms), severity classification |

**Severity Levels:**
- **HIGH** — lot_number, total_price, finance_terms (blocks workflow)
- **MEDIUM** — build_price, land_price (financial discrepancy)
- **LOW** — email typos, mobile numbers (minor corrections)

### Comms Agent

| Attribute | Value |
|-----------|-------|
| **Model** | Deterministic templates + Qwen3-235B via DeepInfra (LLM mode) |
| **Input** | Email type, deal context, comparison results |
| **Output** | Formatted email (from, to, subject, body, attachments) |
| **Key Capability** | Template-based generation with context injection |

### Orchestrator (Non-LLM)

| Attribute | Value |
|-----------|-------|
| **Implementation** | Python / n8n workflow |
| **Storage** | SQLite |
| **Key Capability** | State machine enforcement, SLA timer management |

## Multi-Agent Collaboration Patterns

### Pattern 1: Deal ID Resolution (Router ↔ Orchestrator)

When an email arrives without a clear lot number:

```
[Router] → QUERY_DEAL_MAPPING
            purchaser_names: ["John Smith", "Jane Smith"]
            project_hint: "Fake Rise"
            
[Orchestrator] → DEAL_MAPPING_RESPONSE  
                  candidates: [{deal_id: "LOT95_FAKE_RISE", confidence: 0.95}]
                  
[Router] → Accepts mapping, continues processing
```

### Pattern 2: Verification Loop (Auditor ↔ Extractor)

When a critical field has low confidence or semantic ambiguity:

```
[Auditor] → RE_EXTRACTION_REQUEST
             document: "CONTRACT_V1"
             field: "finance_terms"
             location_hint: "Section 1.5"
             reason: "Detected potential boolean inversion"
             
[Extractor] → RE_EXTRACTION_RESPONSE
               raw_text: "This Contract IS SUBJECT TO FINANCE"
               normalized_value: true
               confidence: 0.94
               
[Auditor] → Confirms mismatch, marks severity HIGH
```

## Data Flow

### Happy Path (V2 Contract)

```
1. EOI Email arrives
   └→ Router: EOI_SIGNED event
      └→ Extractor: Parse EOI PDF → canonical deal fields
         └→ Orchestrator: Create deal, state = EOI_RECEIVED

2. V2 Contract Email arrives  
   └→ Router: CONTRACT_FROM_VENDOR event
      └→ Extractor: Parse contract PDF → contract fields
         └→ Auditor: Compare to EOI → is_valid = true
            └→ Orchestrator: state = CONTRACT_V2_VALIDATED_OK
               └→ Comms: Generate "Contract to Solicitor" email

3. Solicitor Approval Email arrives
   └→ Router: SOLICITOR_APPROVED_WITH_APPOINTMENT event
      └→ Orchestrator: state = SOLICITOR_APPROVED, schedule SLA timer
         └→ Comms: Generate "Vendor DocuSign Release" email

4. DocuSign emails arrive in sequence
   └→ Router: DOCUSIGN_RELEASED → BUYER_SIGNED → EXECUTED
      └→ Orchestrator: state transitions → EXECUTED ✓
```

### Discrepancy Path (V1 Contract)

```
1. V1 Contract Email arrives
   └→ Router: CONTRACT_FROM_VENDOR event
      └→ Extractor: Parse contract PDF → contract fields
         └→ Auditor: Compare to EOI → 5 mismatches found
            └→ Orchestrator: state = CONTRACT_V1_HAS_DISCREPANCIES
               └→ Comms: Generate "Discrepancy Alert" email (internal)
                  └→ Orchestrator: state = AMENDMENT_REQUESTED
```

### SLA Alert Path

```
1. Appointment + 2 days passes
   └→ Orchestrator: SLA timer fires
      └→ Check: Is state == BUYER_SIGNED or EXECUTED?
         └→ NO: Generate SLA Overdue Alert
            └→ Comms: "SLA Overdue Alert" email (internal)
```

## Technology Stack

| Component | Technology | Rationale |
|-----------|------------|-----------|
| Orchestration | n8n / Python | Visual workflow, easy state management |
| State Storage | SQLite | Lightweight, sufficient for demo |
| LLM Providers | Anthropic API + DeepInfra OpenAI‑compatible API | Claude Haiku 4.5 (routing/extraction), Qwen3‑235B (auditing/comms) |
| PDF Parsing | pdfplumber / PyMuPDF | Reliable text + table extraction |
| Date Parsing | python-dateutil | Relative date resolution |

## Safety & Reliability

### Guardrails

1. **Confidence Thresholds** — Critical fields require ≥0.8 confidence for auto-progression
2. **Human Review Fallback** — Low confidence triggers `needs_human_review = true`
3. **Version Superseding** — New contract versions automatically supersede older ones
4. **SLA Monitoring** — Alerts fire only when specific conditions are met

### Trust Boundaries

```
┌─────────────────────────────────────────┐
│         AUTOMATED ZONE                  │
│  • Email classification                 │
│  • Field extraction                     │
│  • Mismatch detection                   │
│  • Email generation                     │
└─────────────────────────────────────────┘
                    │
                    ▼ (review required)
┌─────────────────────────────────────────┐
│         HUMAN OVERSIGHT ZONE            │
│  • Low-confidence field values          │
│  • Ambiguous deal mappings              │
│  • Amendment approval                   │
│  • Final contract execution             │
└─────────────────────────────────────────┘
```

## Extensibility

The architecture supports:

- **Multiple simultaneous deals** — Deal ID isolation in orchestrator
- **Additional contract versions** — V3, V4... loop until valid
- **New email types** — Add templates to Comms agent
- **Different document types** — Extend Extractor with new parsers
