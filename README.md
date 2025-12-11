# OneCorp Multi-Agent Contract Workflow System

A multi-agent system that shepherds property deals from Expression of Interest (EOI) to executed contract, automating contract validation, email workflows, and SLA monitoring.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run the demo
python -m src.main

# Run tests
pytest tests/ -v
```

## Project Structure

```
onecorp-mas/
├── CLAUDE.md          # Instructions for Claude Code
├── agent_docs/        # Implementation guides for each agent
│   ├── extraction.md  # Extractor agent (PDF parsing, field extraction)
│   ├── comparison.md  # Auditor agent (mismatch detection, risk scoring)
│   ├── emails.md      # Router + Comms agents (classification, generation)
│   ├── state-machine.md # Orchestrator (states, transitions, SLA)
│   └── testing.md     # Test patterns and fixtures
├── docs/              # Architecture, demo script, project plan
├── spec/              # Problem specification & judging criteria
├── data/              # Input files (EOI, contracts, emails)
├── ground-truth/      # Expected outputs for validation
├── src/               # Implementation
│   ├── agents/        # Router, Extractor, Auditor, Comms
│   ├── orchestrator/  # State machine, deal store, SLA monitor
│   └── utils/         # PDF parsing, date resolution
├── tests/             # Unit and integration tests
└── n8n/               # Workflow export (if using n8n)
```

## Understanding the System

**Start here:**

1. `spec/MAS_Brief.md` — Full problem specification
2. `spec/transcript.md` — Stakeholder context  
3. `docs/architecture.md` — Agent design, interactions, and generalizability

**For implementation:**

- `agent_docs/` — Technical guides for building each agent (pattern-based, not hardcoded)

## The Challenge

OneCorp processes property contracts through a complex workflow:

**EOI signed → Contract received → Validated → Solicitor approved → DocuSign → Executed**

Current pain points:
- Single shared inbox for all communications
- Manual contract checking (slow, error-prone)
- Version control across amendments
- SLA tracking based on appointment dates

## Agent Architecture

| Agent | Responsibility | Model |
|-------|----------------|-------|
| Router | Email classification, deal mapping | TBD |
| Extractor | PDF field extraction from EOI/contracts | TBD |
| Auditor | Contract vs EOI comparison, risk scoring | TBD |
| Comms | Email generation (solicitor, vendor, alerts) | TBD |

The **Orchestrator** (non-LLM) manages state transitions and SLA timers.

## Demo Scenario

The dataset includes:
- 1 EOI (source of truth)
- 2 contracts (V1 with 5 errors, V2 corrected)
- 8 emails covering the full workflow

**Demo flow:**

1. V1 contract → 5 mismatches detected → Discrepancy alert
2. V2 contract → Validated → Sent to solicitor
3. Solicitor approves → Vendor release email
4. DocuSign flow → Contract executed
5. SLA test → Remove buyer-signed email → Alert fires

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run specific test
pytest tests/test_comparison.py -v

# With coverage
pytest tests/ --cov=src --cov-report=html
```

### Ground Truth Files (Test Fixtures)

Files in `ground-truth/` are **test fixtures for the demo dataset**, not runtime data:

| File | Purpose |
|------|---------|
| `eoi_extracted.json` | Expected Extractor output for demo EOI |
| `v1_extracted.json` | Expected Extractor output for demo V1 contract |
| `v2_extracted.json` | Expected Extractor output for demo V2 contract |
| `v1_mismatches.json` | Expected Auditor output when comparing V1 to EOI |
| `expected_outputs.json` | Expected emails/states at each workflow step |

**Important:** Agents should use pattern-based logic, not read these files at runtime. The system must work for ANY property deal, not just the demo.

## Judging Criteria

See `spec/judging-criteria.md` for full details:

1. **System Design** — Clear agent roles, communication patterns
2. **Agent Collaboration** — Meaningful multi-agent behavior
3. **Task Performance** — End-to-end workflow completion
4. **Safety & Reliability** — Guardrails, human-in-loop design
5. **Presentation** — Clear demo in under 3 minutes

## Key Files for Claude Code

If using Claude Code for implementation, start with:
- `CLAUDE.md` — Master instructions and critical rules
- `agent_docs/` — Detailed implementation guides per agent

## License

MIT