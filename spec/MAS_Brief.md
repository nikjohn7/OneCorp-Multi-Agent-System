# OneCorp Multi-Agent System Brief

## About OneCorp

Despite the corporate-sounding name, we do something very human and very specific. We help everyday Australians build long-term wealth through property investing — through education, guidance, and strategy, not speculation.

Most Australians were never taught how money works. Financial habits are inherited, not learned. So we work with clients from zero knowledge through buying their first investment property, through to building a portfolio that genuinely changes their financial trajectory.

Even though we're not an AI startup, we operate inside one of the **most operationally complex environments**:

- Real estate
- Finance
- Legal documentation
- Multi-party coordination
- Time-sensitive approvals

Information flows across developers, vendors, solicitors, clients, DocuSign, government processes, and our own team — with *a lot* of room for errors. And because we're dealing with legal and financial commitments, accuracy and timing matter.

So we're here because we want to use AI not as a novelty, but to remove operational friction, prevent mistakes, and free our team to spend their time educating and supporting clients — not chasing paperwork.

---

## What Happens After a Client Signs an EOI

Once a client signs an Expression of Interest (EOI), a legally sensitive workflow begins:

1. **Vendor creates a contract pack** and emails it to us.
2. **We check it against the EOI** — purchaser details, property details, lot number, price, terms, special conditions, etc.
3. If correct → **we send it to the solicitor**.
4. If incorrect → **we request amendments**, sometimes multiple versions.
5. The **solicitor reviews and approves** the contract and then **books a signing appointment** with the client.
6. Once approved, we **ask the vendor to release the contract via DocuSign**.
7. The buyer signs → DocuSign notifies us.
8. The vendor countersigns → contract is executed.
9. We send the executed contract to finance.

This sounds linear, but the truth is:

- All communication happens via **one shared support email inbox**.
- Emails arrive in different formats, with different parties, different responsibilities.
- Documents can have discrepancies or multiple versions.
- Signing appointments are time-sensitive, and failing to follow up is an SLA breach.

---

## Where the Current Workflow Breaks Down

- Our team must manually figure out which email corresponds to which property.
- Contract checking is slow and error-prone.
- Amended contracts need special handling.
- Solicitor approvals and signing appointment dates are buried inside email bodies.
- SLAs depend on timing relative to the appointment — easy to overlook.
- Everything is flying through one inbox, making state-tracking hard.

---

## Why This Is a Multi-Agent Problem

No single agent can reliably handle:

- Document extraction
- Contract comparison
- Email classification
- Workflow state tracking
- Deadline monitoring
- Alert generation
- Decision logic about when to send which email

This naturally decomposes into a team of specialized agents:

- A **Document Extraction Agent**
- A **Comparison & Validation Agent**
- An **Email Classification Agent**
- A **Workflow Orchestration Agent**
- An **SLA Agent**
- An **Alert Generator Agent**

---

## The Challenge — Build a Working Multi-Agent Prototype

You will receive:

- **1 EOI**
- **1 incorrect contract** (V1)
- **1 correct contract** (V2)
- **8 sample emails**

Your prototype must:

### A. Ingest and interpret the dataset

- Extract structured fields from the EOI and both contracts.
- Classify each email and detect workflow events.
- Maintain state (e.g. "contract received", "solicitor approved", "buyer signed").

### B. Validate contracts against the EOI

- Identify every mismatch in the incorrect contract.
- Confirm the correct contract matches.

### C. Automatically send the correct emails at the correct workflow moment

**1. Send Contract to Solicitor**

Trigger when:
- The system validates a contract as **error-free**.

Email must:
- From: support@onecorpaustralia.com.au
- To: solicitor
- Attach the correct contract.

**2. Send Email to Vendor to Release Contract via DocuSign**

Trigger when:
- Solicitor approves **AND**
- Solicitor sets a signing appointment date.

### D. Generate two internal alert emails (required outputs)

**1. Discrepancy Alert Email (Internal Only)**

Triggered when incorrect contract is detected.

Email must list:
- Each mismatched field
- EOI value
- Contract value
- Contract filename

Sent to: support@onecorpaustralia.com.au

**2. SLA Overdue Alert Email (Internal Only)**

Triggered when:
- Signing appointment date + 2 days passes (morning of)
- **AND** no buyer-signed DocuSign email exists.

Email must include:
- Property
- Appointment date/time
- Time elapsed
- Recommended next action

### E. Demonstrate full end-to-end workflow

Your demo should show:

1. Contract checked
2. Incorrect contract → discrepancy alert
3. Correct contract → sent to solicitor
4. Solicitor approval detected
5. Signing appointment extracted
6. Vendor release email generated
7. DocuSign emails processed
8. Workflow reaches "executed" state
9. SLA agent logic tested (by removing the buyer-signed email)

---

## Required Fields for Extraction

### From EOI Document

| Field | Required |
|-------|----------|
| Purchaser first/last names | Yes |
| Purchaser emails | Yes |
| Purchaser mobile numbers | No |
| Residential address | No |
| Lot number | Yes |
| Property address | Yes |
| Project name | No |
| Total price | Yes |
| Land price | No |
| Build price | No |
| Finance terms | Yes |
| Solicitor name | No |
| Solicitor email | No |
| Finance provider | No |

### From EOI Signed Email

- Property address
- Lot number
- Purchaser names
- Solicitor email
- Vendor email (if known)

---

## Success Criteria

| Criterion | Priority |
|-----------|----------|
| **Accuracy of Contract Comparison** | Critical |
| **Workflow Automation Correctness** | Critical |
| **Alerts Logic** | Critical |
| **Multi-Agent Architecture** | High |
| **Working Demo** | Mandatory |
| **Robustness & Extensibility** | Medium |
| **Clarity of Documentation & Presentation** | Medium |

### Contract Comparison
Identifies all mismatches in incorrect contract, none in correct contract.

### Workflow Automation
System must autonomously:
- Validate contract
- Send solicitor email
- Detect solicitor approval
- Extract appointment date
- Send vendor release email
- Detect buyer signing
- Detect full execution
- Track state transitions in sequence

### Alerts Logic
System must:
- Generate discrepancy alert only when mismatches exist
- Generate SLA overdue alert **only** when conditions hold
- NEVER generate alerts incorrectly

### Multi-Agent Architecture
Agents must have:
- Clear responsibilities
- Clean interfaces
- Documented message passing or orchestration logic
- Ability to run sequentially or in parallel depending on workflow

### Working Demo
Must be runnable and demonstrate the workflow end-to-end with the supplied dataset.

### Robustness
System gracefully handles:
- Missing emails
- Different contract versions
- Out-of-order inputs
- Additional properties

### Documentation
Submission should include:
- Architecture diagram
- Workflow diagram
- Explanation of state machine
- Email triggers table
- Any additional required fields not currently in the EOI email
