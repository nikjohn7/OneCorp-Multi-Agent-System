# OneCorp MAS - Quick Start Guide

## 🚀 Fastest Way to See the Demo

```bash
# 1. Setup (one-time)
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
echo "ANTHROPIC_API_KEY=your_key_here" > .env
echo "DEEPINFRA_API_KEY=your_deepinfra_key_here" >> .env  # Qwen3-235B for Auditor/Comms
# (Default Anthropic model id: claude-haiku-4-5)

# 2. Launch Visual Dashboard
python run_ui.py
```

**Then:** Click "Start Demo" in your browser → Watch the workflow execute in real-time!

---

## 📊 Visual Dashboard

**Best for:** Demos, presentations, non-technical audiences

```bash
python run_ui.py
# Opens http://localhost:5000 automatically
```

**Features:**
- ✅ Real-time workflow visualization
- ✅ Live agent activity indicators
- ✅ Contract mismatch display
- ✅ Email generation tracking
- ✅ SLA monitoring
- ✅ Event log with timestamps

**Controls:**
- **Start Demo** - Run the full workflow (15 seconds)
- **Test SLA** - Simulate overdue scenario (available after demo completes)
- **Reset** - Clear all data for fresh run

---

## 💻 Command Line Interface

**Best for:** Technical debugging, step-by-step analysis

```bash
# Full demo
python -m src.main --demo

# Step-by-step execution
python -m src.main --step eoi
python -m src.main --step contract-v1
python -m src.main --step contract-v2
python -m src.main --step solicitor-approval
python -m src.main --step docusign-flow

# Test SLA overdue
python -m src.main --test-sla

# Reset database
python -m src.main --reset
```

---

## 🧪 Running Tests

```bash
# All tests
pytest tests/ -v

# Specific test
pytest tests/test_comparison.py -v

# With coverage
pytest tests/ --cov=src --cov-report=html
```

---

## 📁 Project Structure

```
onecorp-mas/
├── run_ui.py          # 👈 Start here for visual demo
├── src/
│   ├── main.py        # CLI entry point
│   ├── agents/        # Router, Extractor, Auditor, Comms
│   ├── orchestrator/  # State machine, SLA monitor
│   └── ui/            # Flask dashboard
├── data/              # EOI, contracts, emails
├── docs/              # Architecture, guides
└── tests/             # Unit & integration tests
```

---

## 🎯 What the Demo Shows

**Step 1: EOI Processing**
- Extractor parses PDF
- Deal created with ID
- Source of truth established

**Step 2: Contract V1 (Errors)**
- Auditor finds 5 mismatches
- HIGH severity on lot/price/finance
- Discrepancy alert generated
- Workflow blocked

**Step 3: Contract V2 (Corrected)**
- V2 supersedes V1
- Zero mismatches detected
- Sent to solicitor

**Step 4: Solicitor Approval**
- Appointment date extracted
- SLA timer registered (48 hours)
- Vendor release request sent

**Step 5: DocuSign Flow**
- Envelope released
- Buyer signs → SLA cancelled
- Vendor signs → EXECUTED

**SLA Test:**
- Simulate buyer delay
- SLA overdue alert fires

---

## 🔑 Environment Setup

Create `.env` file:

```bash
ANTHROPIC_API_KEY=your_anthropic_api_key_here
DEEPINFRA_API_KEY=your_deepinfra_api_key_here  # Qwen3-235B for Auditor/Comms
```

Get Anthropic API key from: https://console.anthropic.com/
Get DeepInfra API key from: https://deepinfra.com/ (required for Qwen3‑235B Auditor/Comms).

---

## 🆘 Troubleshooting

**Dashboard won't start**
```bash
pip install flask
python run_ui.py --port 8080  # Try different port
```

**API errors**
```bash
# Check API key
cat .env
```

**Database locked**
```bash
python -m src.main --reset
```

**Import errors**
```bash
source .venv/bin/activate  # Ensure venv active
pip install -r requirements.txt
```

---

## 📚 More Documentation

- **Architecture:** `docs/architecture.md`
- **Demo Script:** `docs/demo-script.md`
- **Visual UI Guide:** `docs/visual-ui-guide.md`
- **Full Spec:** `spec/MAS_Brief.md`
- **Complete README:** `README.md`

---

## ⏱️ Time Estimates

- **Setup:** 5 minutes (first time only)
- **Visual Demo:** 15 seconds
- **CLI Demo:** 2-3 minutes
- **SLA Test:** 5 seconds
- **Full Test Suite:** 1-2 minutes

---

## 🎬 Demo Tips

**For Presentations:**
1. Pre-run once to warm cache
2. Have `assets/architecture.svg` open
3. Use visual dashboard for non-technical audiences
4. Point out agent cards lighting up
5. Highlight mismatch detection on V1

**For Technical Review:**
1. Use CLI with `--demo` flag
2. Show database after each step
3. Demonstrate state machine transitions
4. Review generated emails
5. Explain pattern-based extraction

---

## 🔗 Quick Links

| Task | Command |
|------|---------|
| Visual Demo | `python run_ui.py` |
| CLI Demo | `python -m src.main --demo` |
| Run Tests | `pytest tests/ -v` |
| Reset DB | `python -m src.main --reset` |
| View Docs | `open docs/architecture.md` |

---

**Ready to start?**

```bash
python run_ui.py
```

Then click **"Start Demo"** and enjoy! 🎉
