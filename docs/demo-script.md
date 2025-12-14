# Demo Script — OneCorp Multi-Agent Contract Workflow

**Target duration:** ~2-3 minutes
**Structure:** Intro → Live UI Demo → Quick Code Proof → Close

---

## PART 1: Introduction (15 seconds)

> "OneCorp processes property contracts through a shared inbox — it's slow and error-prone.
>
> I've built a multi-agent system that automates this end-to-end: four AI agents plus a deterministic orchestrator working together to take a deal from EOI to fully executed contract.
>
> Let me show you."

---

## PART 2: Live UI Demo (25-30 seconds runtime + narration)

**[Dashboard already open at localhost:5000]**

**[Click "Start Demo"]**

> "Watch the agents light up as they work."

**As EOI processes (~5s):**
> "The Extractor parses the EOI PDF — that's our source of truth for this deal."

**As Contract V1 processes (~8s):**
> "Now V1 arrives. The Auditor compares every field against the EOI...
> See those mismatches appearing? High-severity errors on price, lot number, finance terms.
> The Comms agent generates a discrepancy alert. Workflow blocks until these are fixed."

**As Contract V2 processes (~5s):**
> "Vendor sends a corrected V2. Auditor re-validates — zero mismatches now.
> Contract goes to solicitor."

**As Solicitor + DocuSign flows (~7s):**
> "Solicitor approves with an appointment. SLA timer starts.
> DocuSign released... buyer signs... vendor countersigns... Executed!"

**[Point to green EXECUTED badge]**

> "That's a complete property deal workflow — handled autonomously by coordinated AI agents."

---

## PART 3: Quick Code Proof (20 seconds)

**[Switch to VS Code — have it ready with project open]**

> "This is running live from the codebase."

**[Show file tree briefly — expand src/agents/]**
> "Four agents: Router, Extractor, Auditor, Comms — each with a single responsibility."

**[Show terminal with test output already visible, or run quickly:]**
```bash
pytest tests/ -v --tb=short
```

> "Full test coverage. All passing."

**[Optionally show a quick scroll of main.py or state_machine.py]**
> "Deterministic state machine coordinates everything."

---

## PART 4: Closing (10 seconds)

> "The solution is documented in detail — both in the presentation I've prepared and in the GitHub repository.
>
> Happy to answer any questions."

---

## Pre-Demo Checklist (Off-Camera)

```bash
# Terminal 1: Start dashboard
source .venv/bin/activate
python run_ui.py

# Terminal 2: Ready for test run (VS Code integrated terminal)
source .venv/bin/activate
pytest tests/ -v --tb=short  # Run once, leave output visible
```

**Have ready:**
- Browser at `http://localhost:5000` (click Reset if needed)
- VS Code with `src/agents/` folder visible in tree
- Terminal showing passing tests
- Presentation slides open (for after demo if needed)

---

## Quick Q&A Reminders

| Question | Answer |
|----------|--------|
| How do agents communicate? | Structured JSON through orchestrator, not free-text chaining |
| What about low confidence? | Critical fields <0.8 → re-extract → human review |
| Why deterministic mode? | Reproducible for judging; LLM paths exist for production |
| Is it generalizable? | Yes — pattern-based extraction, not hardcoded values |

---

## Backup: CLI Demo (if UI fails)

```bash
python -m src.main --demo --reset
```

Same narration, just point to terminal output instead of visual dashboard.
