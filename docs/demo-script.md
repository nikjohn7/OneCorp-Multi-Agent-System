# Demo Script — OneCorp Multi-Agent Contract Workflow

**Target duration (spoken):** ~3 minutes  
**Audience:** Judges evaluating multi-agent system design  
**Goal:** Show end-to-end workflow + real agent collaboration + safety + generalizability

---

## Spoken Track (3 minutes)

### 0:00–0:20 — Problem + Architecture

> “OneCorp currently processes post‑EOI contracts through a shared inbox, and the workflow is slow and error‑prone.  
> This system automates it end‑to‑end using four LLM agents plus a deterministic orchestrator.”

> “Router classifies incoming emails into events. Extractor parses PDFs into structured fields with confidence. Auditor compares contract vs EOI and scores risk. Comms generates outbound emails from templates. The orchestrator enforces state transitions and SLAs.”

**[Show `assets/architecture.svg` briefly.]**

> “For demo speed we’ll step through events directly; in inbox mode Router would drive these steps automatically.”

---

### 0:20–1:05 — V1 Discrepancy Detection (critical path)

```bash
python -m src.main --step eoi
```

> “We ingest the signed EOI first. Extractor establishes the source of truth — lot details, purchasers, price, and finance terms — and the orchestrator creates a deal.”

```bash
python -m src.main --step contract-v1
```

> “Now Contract V1 arrives. Auditor compares every critical field to the EOI.  
> You’ll see multiple mismatches, including HIGH‑severity issues like lot/price/finance terms.  
> Comms then generates a discrepancy alert email with field‑by‑field diffs, and the orchestrator blocks the workflow from going to solicitor.”

**[Point to mismatch list + alert email preview.]**

---

### 1:05–2:05 — V2 Happy Path to Execution

```bash
python -m src.main --step contract-v2
```

> “Vendor sends an amended contract. The orchestrator automatically supersedes V1.  
> Auditor re‑compares; V2 validates with no critical mismatches and we generate the solicitor email.”

```bash
python -m src.main --step solicitor-approval
```

> “Solicitor approves and provides a relative signing appointment like ‘Thursday at 11:30am’. Router/date resolver turns that into a concrete datetime and the SLA timer starts.”

```bash
python -m src.main --step docusign-flow
```

> “DocuSign release → buyer signs → vendor countersigns. We reach EXECUTED state.”

**[Point to final state line.]**

---

### 2:05–2:35 — SLA Alerting (reliability)

```bash
python -m src.main --test-sla
```

> “If the buyer doesn’t sign within 48 hours of the appointment, SLA monitor fires and Comms generates an overdue alert. Humans stay in the loop for intervention.”

**[Point to SLA alert preview.]**

---

### 2:35–3:00 — Wrap‑up (tie to judging criteria)

> “This shows clear system design and collaboration: Router → Extractor → Auditor → Comms, coordinated by a deterministic state machine.  
> Safety guardrails include confidence thresholds for critical fields, version superseding, and SLA monitoring.  
> And it’s generalizable — agents use label/pattern reasoning, not demo‑specific hardcoding.”

> “Happy to take questions.”

---

## Appendix A — Off‑Camera Setup (not read aloud)

```bash
source .venv/bin/activate
python -m src.main --reset   # Clear prior state
```

- Ensure `.env` has `DEEPINFRA_API_KEY=...`.
- Do a dry run once before recording: `python -m src.main --demo --quiet`.
- Have `assets/architecture.svg` open in a tab.

---

## Appendix B — Backup Commands

```bash
python -m src.main --demo --reset     # Full demo from clean state
python -m src.main --step eoi
python -m src.main --step contract-v1
python -m src.main --step contract-v2
pytest tests/ -v --tb=short
```

---

## Appendix C — Quick Q&A Reminders

- **How agents communicate:** Structured JSON through orchestrator, not free‑text chaining.  
- **Low confidence:** Critical fields <0.8 → re‑extract → then human review.  
- **Why deterministic in demo:** Reproducible judging; LLM paths exist for production.  
- **Generalization:** Patterns/labels drive extraction + comparison; fixtures are tests only.

