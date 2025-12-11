# Documentation Index

This folder contains technical documentation for the OneCorp Multi-Agent System.

## Reading Order

### 1. Understand the Problem

Start with the problem specification:

- `../spec/MAS_Brief.md` — Full requirements and success criteria
- `../spec/transcript.md` — Stakeholder explanation of the workflow
- `../spec/judging-criteria.md` — What judges look for

### 2. Understand the Architecture

System design and workflow:

- `architecture.md` — Agent design, responsibilities, message flows, collaboration patterns, **generalizability principles**

### 3. Implement the Agents

Technical implementation guides (in `../agent_docs/`):

| Guide | Use When |
|-------|----------|
| `../agent_docs/extraction.md` | Building the Extractor agent, parsing PDFs |
| `../agent_docs/comparison.md` | Building the Auditor agent, detecting mismatches |
| `../agent_docs/emails.md` | Building Router (classification) or Comms (generation) agents |
| `../agent_docs/state-machine.md` | Building the Orchestrator, managing state |
| `../agent_docs/testing.md` | Writing or running tests |

### 4. Prepare the Demo

- `demo-script.md` — 3-minute demo walkthrough with exact steps

## Quick Reference

### Data Files

| Location | Contents |
|----------|----------|
| `../data/source-of-truth/` | The canonical EOI PDF |
| `../data/contracts/` | V1 (incorrect) and V2 (corrected) contracts |
| `../data/emails/incoming/` | Emails to process |
| `../data/emails/templates/` | Reference formats for generated emails |
| `../data/emails_manifest.json` | Timestamps and metadata for all emails |

### Ground Truth (Test Fixtures Only)

**These files validate the demo dataset. Agents must NOT read them at runtime.**

| File | Purpose |
|------|---------|
| `../ground-truth/eoi_extracted.json` | Expected Extractor output for demo EOI |
| `../ground-truth/v1_extracted.json` | Expected Extractor output for demo V1 |
| `../ground-truth/v2_extracted.json` | Expected Extractor output for demo V2 |
| `../ground-truth/v1_mismatches.json` | Expected Auditor output for V1 vs EOI |
| `../ground-truth/expected_outputs.json` | Expected workflow outputs |

The system must be **generalizable**—working for any property deal using pattern-based logic, not just matching these fixture values.

### Visual Reference

- `../assets/workflow_diagram.jpeg` — OneCorp's current human workflow

## Document Purposes

| Document | Audience | Purpose |
|----------|----------|---------|
| `architecture.md` | Judges, developers | High-level system understanding, generalizability |
| `demo-script.md` | Presenters | Exact demo steps and timing |
| `../agent_docs/*.md` | Claude Code / developers | Implementation specifics (pattern-based logic) |
| `../spec/*.md` | Everyone | Requirements and context |
| `../ground-truth/*.json` | Tests only | Validation fixtures (NOT runtime data) |