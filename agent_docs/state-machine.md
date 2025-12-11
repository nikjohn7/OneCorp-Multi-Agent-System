# State Machine Guide

## Overview

The Orchestrator manages deal state transitions and enforces workflow rules. It is a **deterministic component** (not an LLM agent) that uses event-driven state transitions. The logic is deal-agnostic—it processes any deal through the same workflow.

---

## Part 1: Implementation Logic (Generalizable)

### State Definitions

```python
from enum import Enum

class DealState(Enum):
    # Initial states
    EOI_RECEIVED = "EOI_RECEIVED"
    AWAITING_FIRST_CONTRACT = "AWAITING_FIRST_CONTRACT"
    
    # Contract processing states (parameterized by version)
    CONTRACT_RECEIVED = "CONTRACT_RECEIVED"           # CONTRACT_V{n}_RECEIVED
    CONTRACT_VALIDATED_OK = "CONTRACT_VALIDATED_OK"   # CONTRACT_V{n}_VALIDATED_OK
    CONTRACT_HAS_DISCREPANCIES = "CONTRACT_HAS_DISCREPANCIES"
    
    # Amendment cycle
    AMENDMENT_REQUESTED = "AMENDMENT_REQUESTED"
    AWAITING_AMENDED_CONTRACT = "AWAITING_AMENDED_CONTRACT"
    
    # Solicitor flow
    SENT_TO_SOLICITOR = "SENT_TO_SOLICITOR"
    SOLICITOR_APPROVED = "SOLICITOR_APPROVED"
    
    # DocuSign flow
    DOCUSIGN_RELEASE_REQUESTED = "DOCUSIGN_RELEASE_REQUESTED"
    DOCUSIGN_RELEASED = "DOCUSIGN_RELEASED"
    BUYER_SIGNED = "BUYER_SIGNED"
    EXECUTED = "EXECUTED"
    
    # Alert states
    SLA_OVERDUE_ALERT_SENT = "SLA_OVERDUE_ALERT_SENT"
    HUMAN_REVIEW_REQUIRED = "HUMAN_REVIEW_REQUIRED"
```

### State Transition Rules

```python
TRANSITIONS = {
    # State: {Event: NextState}
    
    DealState.EOI_RECEIVED: {
        "CONTRACT_FROM_VENDOR": DealState.CONTRACT_RECEIVED,
    },
    
    DealState.AWAITING_FIRST_CONTRACT: {
        "CONTRACT_FROM_VENDOR": DealState.CONTRACT_RECEIVED,
    },
    
    DealState.CONTRACT_RECEIVED: {
        "VALIDATION_PASSED": DealState.CONTRACT_VALIDATED_OK,
        "VALIDATION_FAILED": DealState.CONTRACT_HAS_DISCREPANCIES,
        "HUMAN_REVIEW_NEEDED": DealState.HUMAN_REVIEW_REQUIRED,
    },
    
    DealState.CONTRACT_HAS_DISCREPANCIES: {
        "DISCREPANCY_ALERT_SENT": DealState.AMENDMENT_REQUESTED,
    },
    
    DealState.AMENDMENT_REQUESTED: {
        "AUTO": DealState.AWAITING_AMENDED_CONTRACT,
    },
    
    DealState.AWAITING_AMENDED_CONTRACT: {
        "CONTRACT_FROM_VENDOR": DealState.CONTRACT_RECEIVED,  # New version
    },
    
    DealState.CONTRACT_VALIDATED_OK: {
        "SOLICITOR_EMAIL_SENT": DealState.SENT_TO_SOLICITOR,
    },
    
    DealState.SENT_TO_SOLICITOR: {
        "SOLICITOR_APPROVED_WITH_APPOINTMENT": DealState.SOLICITOR_APPROVED,
    },
    
    DealState.SOLICITOR_APPROVED: {
        "VENDOR_RELEASE_EMAIL_SENT": DealState.DOCUSIGN_RELEASE_REQUESTED,
    },
    
    DealState.DOCUSIGN_RELEASE_REQUESTED: {
        "DOCUSIGN_RELEASED": DealState.DOCUSIGN_RELEASED,
    },
    
    DealState.DOCUSIGN_RELEASED: {
        "DOCUSIGN_BUYER_SIGNED": DealState.BUYER_SIGNED,
        "SLA_OVERDUE": DealState.SLA_OVERDUE_ALERT_SENT,
    },
    
    DealState.BUYER_SIGNED: {
        "DOCUSIGN_EXECUTED": DealState.EXECUTED,
    },
    
    # Terminal states - no transitions out
    DealState.EXECUTED: {},
    DealState.SLA_OVERDUE_ALERT_SENT: {
        "DOCUSIGN_BUYER_SIGNED": DealState.BUYER_SIGNED,  # Can still complete
    },
}
```

### Transition Function

```python
class StateMachine:
    def __init__(self, deal_id: str):
        self.deal_id = deal_id
        self.current_state = DealState.EOI_RECEIVED
        self.contract_version = 0
        self.contracts = {}  # version -> ContractRecord
        self.sla_deadline = None
        self.events = []
    
    def transition(self, event: str, **context) -> bool:
        """
        Attempt state transition based on event.
        Returns True if transition occurred, False if invalid.
        """
        allowed = TRANSITIONS.get(self.current_state, {})
        
        if event not in allowed:
            self.log_event(event, success=False, reason="Invalid transition")
            return False
        
        # Execute transition
        old_state = self.current_state
        new_state = allowed[event]
        
        # Pre-transition hooks
        self._pre_transition(event, context)
        
        self.current_state = new_state
        self.log_event(event, success=True, old_state=old_state, new_state=new_state)
        
        # Post-transition hooks
        self._post_transition(event, context)
        
        return True
    
    def _pre_transition(self, event: str, context: dict):
        """Execute pre-transition logic."""
        
        if event == "CONTRACT_FROM_VENDOR":
            # Increment version and supersede old contracts
            self.contract_version += 1
            self._supersede_old_contracts()
    
    def _post_transition(self, event: str, context: dict):
        """Execute post-transition logic."""
        
        if event == "SOLICITOR_APPROVED_WITH_APPOINTMENT":
            # Schedule SLA timer
            appointment = context.get('appointment_datetime')
            if appointment:
                self._schedule_sla_timer(appointment)
```

### Version Superseding Logic

When a new contract version arrives, all older versions are marked superseded:

```python
def _supersede_old_contracts(self):
    """Mark all existing contracts as superseded."""
    for version, contract in self.contracts.items():
        if contract.status not in ['SUPERSEDED', 'EXECUTED']:
            contract.status = 'SUPERSEDED'
            self.log_event(
                "CONTRACT_SUPERSEDED",
                version=version,
                reason=f"Superseded by V{self.contract_version}"
            )

def can_send_to_solicitor(self, version: int) -> bool:
    """
    Only the highest validated version can be sent to solicitor.
    """
    # Must be validated
    if self.contracts[version].status != 'VALIDATED_OK':
        return False
    
    # Must be highest version
    highest = max(self.contracts.keys())
    if version != highest:
        return False
    
    return True
```

### SLA Timer Logic

```python
from datetime import datetime, timedelta

def _schedule_sla_timer(self, appointment: datetime):
    """
    Schedule SLA check for appointment + 2 days.
    """
    # SLA deadline = appointment + 2 days at 9:00 AM
    deadline = appointment + timedelta(days=2)
    deadline = deadline.replace(hour=9, minute=0, second=0, microsecond=0)
    
    self.sla_deadline = deadline
    
    # Schedule the check (implementation depends on infrastructure)
    schedule_task(
        task_id=f"sla_check_{self.deal_id}",
        run_at=deadline,
        callback=self.check_sla
    )

def check_sla(self):
    """
    Evaluate SLA status. Called when timer fires.
    """
    # If already signed or executed, no alert needed
    if self.current_state in [DealState.BUYER_SIGNED, DealState.EXECUTED]:
        return
    
    # If past deadline and still awaiting signature
    if datetime.now() > self.sla_deadline:
        if self.current_state in [DealState.DOCUSIGN_RELEASED, DealState.DOCUSIGN_RELEASE_REQUESTED]:
            self.transition("SLA_OVERDUE")
            return True  # Alert should be generated
    
    return False
```

### Deal Data Model

```python
@dataclass
class Deal:
    deal_id: str  # Unique identifier, e.g., "LOT{n}_{ADDRESS_SLUG}"
    status: DealState
    
    # Canonical values (from EOI - source of truth)
    canonical: Dict[str, Any]
    
    # Contract tracking
    contracts: Dict[int, ContractRecord]  # version -> record
    current_version: int
    
    # Solicitor and appointment
    solicitor_email: str
    solicitor_appointment: Optional[datetime]
    sla_deadline: Optional[datetime]
    
    # Vendor
    vendor_email: str
    
    # Audit trail
    events: List[DealEvent]
    created_at: datetime
    updated_at: datetime

@dataclass
class ContractRecord:
    version: int
    filename: str
    status: str  # RECEIVED, VALIDATED_OK, HAS_DISCREPANCIES, SUPERSEDED
    received_at: datetime
    validated_at: Optional[datetime]
    is_valid: bool
    mismatches: List[Mismatch]
    risk_score: str

@dataclass
class DealEvent:
    event_type: str
    timestamp: datetime
    source: str  # email_id, "system", "user"
    old_state: Optional[str]
    new_state: Optional[str]
    metadata: Dict[str, Any]
```

### Deal ID Generation

```python
def generate_deal_id(lot_number: str, property_address: str) -> str:
    """
    Generate unique deal ID from property identifiers.
    """
    # Normalize address: remove spaces, uppercase
    address_slug = re.sub(r'[^A-Za-z0-9]+', '_', property_address).upper()
    
    return f"LOT{lot_number}_{address_slug}"

# Example: LOT95_FAKE_RISE_VIC_3336
```

---

## Part 2: State Diagram

### Visual Representation

```
                        ┌─────────────────┐
                        │  EOI_RECEIVED   │
                        └────────┬────────┘
                                 │ CONTRACT_FROM_VENDOR
                                 ▼
                        ┌─────────────────┐
                        │ CONTRACT_V{n}_  │
                        │   RECEIVED      │
                        └────────┬────────┘
                                 │
                  ┌──────────────┴──────────────┐
                  │ VALIDATION_PASSED           │ VALIDATION_FAILED
                  ▼                             ▼
         ┌────────────────┐           ┌─────────────────┐
         │  VALIDATED_OK  │           │ HAS_DISCREPANCIES│
         └────────┬───────┘           └────────┬────────┘
                  │                            │ DISCREPANCY_ALERT_SENT
                  │                            ▼
                  │                   ┌─────────────────┐
                  │                   │   AMENDMENT_    │
                  │                   │   REQUESTED     │
                  │                   └────────┬────────┘
                  │                            │ AUTO
                  │                            ▼
                  │                   ┌─────────────────┐
                  │                   │ AWAITING_V{n+1} │◄────┐
                  │                   └────────┬────────┘     │
                  │                            │ CONTRACT_    │
                  │                            │ FROM_VENDOR  │
                  │                            ▼              │
                  │                   ┌─────────────────┐     │
                  │                   │ CONTRACT_V{n+1} │     │
                  │                   │   RECEIVED      │     │
                  │                   └────────┬────────┘     │
                  │                            │              │
                  │              ┌─────────────┴──────┐       │
                  │              │                    │       │
                  │              ▼                    ▼       │
                  │     ┌────────────┐      ┌──────────────┐  │
                  └────►│ VALIDATED  │      │ DISCREPANCIES├──┘
                        │    OK      │      └──────────────┘
                        └─────┬──────┘       (loops until valid)
                              │ SOLICITOR_EMAIL_SENT
                              ▼
                     ┌─────────────────┐
                     │ SENT_TO_SOLICITOR│
                     └────────┬────────┘
                              │ SOLICITOR_APPROVED_WITH_APPOINTMENT
                              ▼
                     ┌─────────────────┐
                     │SOLICITOR_APPROVED│──► Schedule SLA timer
                     └────────┬────────┘
                              │ VENDOR_RELEASE_EMAIL_SENT
                              ▼
                     ┌─────────────────┐
                     │DOCUSIGN_RELEASE_│
                     │   REQUESTED     │
                     └────────┬────────┘
                              │ DOCUSIGN_RELEASED
                              ▼
                     ┌─────────────────┐
                     │DOCUSIGN_RELEASED │──► SLA timer running
                     └────────┬────────┘
                              │
               ┌──────────────┴──────────────┐
               │ BUYER_SIGNED                │ SLA_OVERDUE
               ▼                             ▼
       ┌──────────────┐            ┌─────────────────┐
       │ BUYER_SIGNED │            │ SLA_OVERDUE_    │
       └───────┬──────┘            │  ALERT_SENT     │
               │                   └────────┬────────┘
               │ DOCUSIGN_EXECUTED          │ BUYER_SIGNED (can still complete)
               ▼                            ▼
       ┌──────────────┐            ┌──────────────┐
       │   EXECUTED   │ ✓          │ BUYER_SIGNED │
       └──────────────┘            └──────────────┘
```

### Simplified Demo View (7 States)

For presentation, collapse to user-friendly progression:

```
1. EOI Received        → Deal created, awaiting contract
2. Contract Received   → Validation in progress...
3. Discrepancies Found → Amendment requested (or skipped if valid)
4. Contract Validated  → Ready for legal review
5. Sent to Solicitor   → Awaiting approval
6. DocuSign Released   → Awaiting signatures
7. Executed ✓          → Deal complete (or SLA Alert ⚠️)
```

---

## Part 3: Workflow Guards

### Guard: Only Valid Contracts Proceed

```python
def guard_solicitor_email(deal: Deal) -> bool:
    """Can we send this contract to solicitor?"""
    current_contract = deal.contracts[deal.current_version]
    
    # Must be validated OK
    if not current_contract.is_valid:
        return False
    
    # Must be highest version
    if deal.current_version != max(deal.contracts.keys()):
        return False
    
    # Must not already be sent
    if deal.status in [DealState.SENT_TO_SOLICITOR, DealState.SOLICITOR_APPROVED]:
        return False
    
    return True
```

### Guard: SLA Alert Conditions

```python
def guard_sla_alert(deal: Deal) -> bool:
    """Should SLA alert fire?"""
    
    # Must have a deadline set
    if not deal.sla_deadline:
        return False
    
    # Must be past deadline
    if datetime.now() <= deal.sla_deadline:
        return False
    
    # Must not already be signed
    if deal.status in [DealState.BUYER_SIGNED, DealState.EXECUTED]:
        return False
    
    # Must be in DocuSign phase
    if deal.status not in [DealState.DOCUSIGN_RELEASED, DealState.DOCUSIGN_RELEASE_REQUESTED]:
        return False
    
    return True
```

---

## Part 4: Demo Validation

### Expected State Sequence

For the demo dataset, the expected state progression is:

```
EOI_RECEIVED
    ↓ (contract V1 received)
CONTRACT_V1_RECEIVED
    ↓ (validation finds mismatches)
CONTRACT_V1_HAS_DISCREPANCIES
    ↓ (alert sent)
AMENDMENT_REQUESTED
    ↓ (auto)
AWAITING_AMENDED_CONTRACT
    ↓ (contract V2 received)
CONTRACT_V2_RECEIVED
    ↓ (validation passes)
CONTRACT_V2_VALIDATED_OK
    ↓ (solicitor email sent)
SENT_TO_SOLICITOR
    ↓ (solicitor approval email received)
SOLICITOR_APPROVED
    ↓ (vendor release email sent)
DOCUSIGN_RELEASE_REQUESTED
    ↓ (DocuSign "please sign" email received)
DOCUSIGN_RELEASED
    ↓ (buyer signed email received)
BUYER_SIGNED
    ↓ (executed email received)
EXECUTED ✓
```

### SLA Test Scenario

To test SLA alerting, remove the buyer-signed email and simulate time passing:

```python
def test_sla_alert_fires():
    """SLA alert fires when buyer hasn't signed after deadline."""
    
    # Setup deal at DOCUSIGN_RELEASED state
    deal = create_test_deal_at_state(DealState.DOCUSIGN_RELEASED)
    deal.sla_deadline = datetime.now() - timedelta(hours=1)  # Past deadline
    
    # Check SLA
    result = deal.check_sla()
    
    assert result == True
    assert deal.status == DealState.SLA_OVERDUE_ALERT_SENT
```

---

## Quick Reference

### State Machine Interface

```python
class StateMachine:
    def transition(self, event: str, **context) -> bool
    def can_transition(self, event: str) -> bool
    def get_allowed_events(self) -> List[str]
    def check_sla(self) -> bool
```

### Event Types

```python
EVENTS = [
    "CONTRACT_FROM_VENDOR",
    "VALIDATION_PASSED",
    "VALIDATION_FAILED",
    "HUMAN_REVIEW_NEEDED",
    "DISCREPANCY_ALERT_SENT",
    "SOLICITOR_EMAIL_SENT",
    "SOLICITOR_APPROVED_WITH_APPOINTMENT",
    "VENDOR_RELEASE_EMAIL_SENT",
    "DOCUSIGN_RELEASED",
    "DOCUSIGN_BUYER_SIGNED",
    "DOCUSIGN_EXECUTED",
    "SLA_OVERDUE",
]
```
