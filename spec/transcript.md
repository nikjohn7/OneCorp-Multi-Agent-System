# OneCorp Problem Statement Transcript

*Summary of the stakeholder explanation of the contract workflow challenge.*

---

## The Business Context

OneCorp helps clients with property investment strategies, finding suitable properties that fit their financial situation. When a suitable property is found, the client signs an Expression of Interest (EOI), typically paying a $1,000 deposit to hold the property while the legal paperwork is processed.

---

## The Workflow (Simplified)

1. **EOI Signed** → Client commits to the property
2. **Vendor creates contract pack** → Based on EOI conditions
3. **OneCorp reviews contracts** → Compares against EOI for accuracy
4. **If match** → Send to solicitor
5. **If discrepancy** → Flag and recommend fix
6. **Solicitor reviews** → Books signing appointment with client
7. **OneCorp notifies vendor** → Release contracts via DocuSign
8. **Client signs** → Within 2-day window
9. **Vendor countersigns** → Contract executed
10. **Contracts go to finance** → Funds released

---

## Why This Is Complex

> "This sounds linear, but in reality it's branching, it's asynchronous workflow happening entirely through a single shared email box."

Key challenges:

- **Single inbox**: All emails (from developers, solicitors, clients, DocuSign) arrive at one support@email address
- **Property identification**: Usually by address in subject line, but lot numbers for similar properties (30-50 in a development) can be confusing
- **Manual comparison**: Long documents need careful checking — first name, last name, all details must be exact because these are legal documents
- **Version control**: If amendments are needed, multiple contract versions exist with different timestamps
- **External dependencies**: Solicitors are engaged by the client (not OneCorp), so OneCorp must follow up to keep things moving
- **Time sensitivity**: The industry is slow, causing cash flow delays for deals in progress

---

## Why Single-Agent AI Won't Work

> "The workflow can't be handled reliably from a single AI agent because there's just so many moving parts and integrations. Even if you do assign a couple of different tools or APIs to a particular AI, from what I've seen... it works with a handful of tools. It doesn't work with 20 or 30 different tools."

The system needs to:

- Read and classify incoming emails
- Extract contract details and compare to EOI
- Identify discrepancies and flag for human oversight
- Track contract versions and recognize amendments
- Enforce approval rules (auto-progress vs. escalate)
- Monitor solicitor approvals and signing appointments
- Extract appointment dates for SLA triggers
- Draft communication templates to vendors and solicitors

---

## The Challenge

> "Design a multi-agent system that can manage this contract workflow end to end."

Your solution should:

1. **Identify** contract versions and relevant properties
2. **Extract** and compare contract data against EOIs
3. **Flag** discrepancies and decide when human review is required
4. **Handle** amended contracts differently from clean first versions
5. **Interpret** emails from vendors, solicitors, and DocuSign
6. **Track** signing appointments with SLA windows
7. **Orchestrate** the workflow so each agent knows when to act next

---

## The Goal

> "Ultimately we want this system that reduces manual workload, prevents errors and reliably shepherds the contract through the execution process while keeping humans in the loop and be able to judge where required."

Key principles:
- **Human-in-the-loop**: AI assists but humans approve where needed
- **Error prevention**: Catches mistakes before contracts are signed
- **Efficiency**: Reduces back-and-forth delays
- **Accuracy**: Every detail matters for legal documents worth $500K-$1M

---

## Workflow Diagram Reference

See `assets/workflow_diagram.jpeg` for the visual representation showing:

- Shared inbox as the central bottleneck
- Classification and extraction flows
- Discrepancy detection branches
- Solicitor review and approval path
- DocuSign release and monitoring
- SLA follow-up triggers
