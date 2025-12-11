# Demo Script — OneCorp Multi-Agent Contract Workflow

**Duration:** 3 minutes  
**Audience:** Judges evaluating multi-agent system design  
**Goal:** Demonstrate end-to-end workflow automation with meaningful agent collaboration

---

## Pre-Demo Setup

```bash
# Ensure clean state
cd onecorp-mas
rm -f data/deals.db  # Reset database

# Verify dependencies
pip install -r requirements.txt

# Optional: Split terminal to show logs alongside output
```

---

## Demo Flow Overview

| Time | Phase | What Judges See |
|------|-------|-----------------|
| 0:00–0:30 | Introduction | Problem statement, agent architecture |
| 0:30–1:15 | Discrepancy Detection | V1 contract fails validation, alert generated |
| 1:15–2:00 | Happy Path | V2 validates, solicitor flow, DocuSign |
| 2:00–2:30 | SLA Alerting | Demonstrate deadline monitoring |
| 2:30–3:00 | Wrap-up | Architecture recap, Q&A setup |

---

## Script

### 0:00–0:30 — Introduction

**[Show: Architecture diagram or slide]**

> "OneCorp processes property contracts through a shared email inbox. Today I'll demonstrate a multi-agent system that automates this workflow—from contract validation to execution."

> "The system has four LLM-based agents coordinated by a deterministic orchestrator:"
> - **Router** — classifies incoming emails, extracts deal identifiers
> - **Extractor** — parses PDFs, extracts structured fields with confidence scores
> - **Auditor** — compares contracts against the EOI, detects mismatches
> - **Comms** — generates all outbound emails from templates

> "Let's see it in action with a real deal: Lot 95, Fake Rise, for purchasers John and Jane Smith."

---

### 0:30–1:15 — Discrepancy Detection (The Critical Test)

**[Run: Process EOI and V1 Contract]**

```bash
python -m src.main --step eoi
```

**Narrate while running:**
> "First, the EOI email arrives. The Router classifies it as `EOI_SIGNED` and the Extractor parses the PDF to establish our source of truth."

**[Point to log output showing extracted fields]**
> "We've extracted: Lot 95, total price $550,000, NOT subject to finance."

```bash
python -m src.main --step contract-v1
```

**Narrate:**
> "Now the vendor sends Contract V1. Watch what happens when the Auditor compares it to the EOI..."

**[Point to comparison output]**
> "The Auditor detected **5 mismatches**:"
> - Lot number: 59 instead of 95 — **HIGH severity**
> - Total price: $565,000 instead of $550,000 — **HIGH severity**
> - Build price: $315,000 instead of $300,000 — **MEDIUM severity**
> - Jane's email: outlook instead of gmail — **LOW severity**
> - Finance terms: 'Subject to' instead of 'NOT subject to' — **HIGH severity**

> "The system automatically generates a discrepancy alert email..."

**[Show generated alert email]**
> "This goes to the internal support team with exact field-by-field comparison and amendment recommendations. The contract is **blocked** from proceeding to solicitor."

**Key point for judges:**
> "Notice the agents collaborated here: Router identified the email, Extractor parsed both documents, Auditor compared them, and Comms generated the alert. Each agent has a single responsibility."

---

### 1:15–2:00 — Happy Path (V2 to Execution)

**[Run: Process corrected V2 Contract]**

```bash
python -m src.main --step contract-v2
```

**Narrate:**
> "The vendor sends an amended contract. V1 is automatically marked as **superseded**. Let's validate V2..."

**[Point to output]**
> "Zero mismatches. The Auditor approves, and the system automatically generates the solicitor email."

**[Show generated solicitor email]**
> "Contract sent to Michael Ken at Big Legal Firm with V2 attached."

```bash
python -m src.main --step solicitor-approval
```

**Narrate:**
> "The solicitor replies with approval and a signing appointment: 'Thursday at 11:30am'. The Router extracts this relative date and resolves it to January 16th, 2025."

**[Point to state transition]**
> "State transitions to `SOLICITOR_APPROVED`. The system generates the vendor release request..."

**[Show generated vendor email]**
> "Asking BuildWell to release via DocuSign."

```bash
python -m src.main --step docusign-flow
```

**Narrate:**
> "DocuSign sends the envelope... buyer signs... vendor countersigns... and we reach `EXECUTED` state."

**[Show final state]**
> "Contract fully executed. The deal is complete."

---

### 2:00–2:30 — SLA Alerting (Reliability Demo)

**[Run: SLA test scenario]**

```bash
python -m src.main --test-sla
```

**Narrate:**
> "What if the buyer doesn't sign? Let's simulate: appointment was Thursday 11:30am, it's now Saturday 9:00am—48 hours later."

**[Point to SLA check output]**
> "The SLA monitor fires. No buyer signature detected. An overdue alert is generated..."

**[Show SLA alert email]**
> "Internal alert with: property details, appointment time, time elapsed, and recommended actions."

**Key point for judges:**
> "This demonstrates the system's reliability—it monitors deadlines and escalates appropriately, keeping humans in the loop for intervention."

---

### 2:30–3:00 — Wrap-up

**[Show: Architecture diagram again]**

> "To summarize what we demonstrated:"

> "**System Design** — Clear separation of concerns across 4 agents plus orchestrator"

> "**Agent Collaboration** — Agents exchange structured data: Router → Extractor → Auditor → Comms, coordinated by state machine"

> "**Task Performance** — End-to-end workflow from EOI to executed contract"

> "**Safety & Reliability** — Confidence scoring, version superseding, SLA monitoring, human escalation for low-confidence fields"

> "**Real-World Value** — This directly addresses OneCorp's pain points: manual contract checking, version control, deadline tracking"

> "The system is also **generalizable**—it uses pattern-based extraction, not hardcoded values. It would work for any property deal, not just Lot 95."

> "Happy to take questions."

---

## Backup Commands (If Needed)

### Run Full Demo in One Command
```bash
python -m src.main --demo
```

### Run All Tests
```bash
pytest tests/ -v --tb=short
```

### Show Specific Test Results
```bash
# Extraction accuracy
pytest tests/test_extraction.py -v

# Mismatch detection
pytest tests/test_comparison.py -v

# State transitions
pytest tests/test_state_transitions.py -v
```

### Reset and Re-run
```bash
rm -f data/deals.db && python -m src.main --demo
```

---

## What to Highlight for Each Judging Criterion

| Criterion | What to Show | When |
|-----------|--------------|------|
| **System Design** | Architecture diagram, agent responsibilities | Introduction |
| **Agent Collaboration** | Data flow between agents during V1 comparison | Discrepancy section |
| **Creativity** | Confidence scoring, re-extraction loop, version superseding | Throughout |
| **Task Performance** | Full workflow completion | Happy path section |
| **Real-World Value** | Direct mapping to OneCorp's stated problems | Wrap-up |
| **Safety & Reliability** | SLA alerting, human escalation triggers | SLA section |
| **Presentation** | Clear narrative, visible outputs | Entire demo |

---

## Common Questions & Answers

**Q: How do agents communicate?**
> "Through the orchestrator. Each agent receives structured input and returns structured output. The orchestrator manages state and routes data between agents."

**Q: What if extraction confidence is low?**
> "Critical fields require ≥80% confidence. Below that, the Auditor can request re-extraction from a different section of the document. If still uncertain, it flags for human review."

**Q: How does version superseding work?**
> "When a new contract version arrives, the orchestrator marks all previous versions as superseded. Only the highest validated version can proceed to solicitor."

**Q: What models do you use?**
> "Haiku for Router and Comms (fast, cheap, simple tasks). Sonnet for Extractor and Auditor (reasoning-heavy tasks). The orchestrator is deterministic Python—no LLM needed for state management."

**Q: How would this scale to multiple deals?**
> "Each deal is isolated by deal_id. The orchestrator can process multiple deals concurrently. State is persisted in SQLite, so it survives restarts."

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "Module not found" | Run `pip install -r requirements.txt` |
| Database locked | Delete `data/deals.db` and re-run |
| PDF extraction fails | Check pdfplumber installed, verify PDF path |
| API rate limit | Add delay between agent calls or use cached responses |
| Wrong state | Reset with `rm -f data/deals.db` |

---

## Demo Checklist

Before presenting:

- [ ] Dependencies installed (`pip install -r requirements.txt`)
- [ ] Database reset (`rm -f data/deals.db`)
- [ ] API keys configured (if using live LLM calls)
- [ ] Terminal font size readable for screen share
- [ ] Architecture diagram ready to show
- [ ] Backup: pre-recorded demo video if live fails