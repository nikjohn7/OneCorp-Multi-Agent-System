# Email Guide

## Overview

This guide covers two agents:
1. **Router Agent** — Classifies incoming emails by event type and extracts key data
2. **Comms Agent** — Generates outbound emails from templates

Both agents use **pattern-based logic** that generalizes to any property deal, not hardcoded to specific values.

---

## Part 1: Router Agent — Implementation Logic

### Event Type Classification

The Router classifies emails into event types based on **sender patterns** and **subject/body patterns**:

```python
EVENT_TYPES = [
    "EOI_SIGNED",                        # New deal initiated
    "CONTRACT_FROM_VENDOR",              # Contract PDF received
    "SOLICITOR_APPROVED_WITH_APPOINTMENT", # Legal approval + signing time
    "DOCUSIGN_RELEASED",                 # "Please sign" sent to buyers
    "DOCUSIGN_BUYER_SIGNED",             # Buyer completed signing
    "DOCUSIGN_EXECUTED",                 # All parties signed
]
```

### Classification Rules

#### By Sender Domain

```python
SENDER_PATTERNS = {
    # Internal emails
    r".*@onecorpaustralia\.com\.au$": ["EOI_SIGNED", "INTERNAL"],
    
    # Vendor/developer emails
    r".*@.*developments?\.com\.au$": ["CONTRACT_FROM_VENDOR"],
    r"contracts@.*": ["CONTRACT_FROM_VENDOR"],
    
    # Solicitor emails
    r".*@.*legal.*\.com\.au$": ["SOLICITOR_APPROVED_WITH_APPOINTMENT"],
    r".*@.*law.*\.com\.au$": ["SOLICITOR_APPROVED_WITH_APPOINTMENT"],
    
    # DocuSign system emails
    r".*@docusign\.(net|com)$": ["DOCUSIGN_RELEASED", "DOCUSIGN_BUYER_SIGNED", "DOCUSIGN_EXECUTED"],
}
```

#### By Subject Line Patterns

```python
SUBJECT_PATTERNS = {
    r"EOI Signed": "EOI_SIGNED",
    r"Expression of Interest": "EOI_SIGNED",
    
    r"Contract Request": "CONTRACT_FROM_VENDOR",
    r"Contract of Sale.*attached": "CONTRACT_FROM_VENDOR",
    
    r"Contract for Review": "SOLICITOR_APPROVED_WITH_APPOINTMENT",  # If from solicitor domain
    r"RE:.*Contract.*Review": "SOLICITOR_APPROVED_WITH_APPOINTMENT",
    
    r"Please.*DocuSign": "DOCUSIGN_RELEASED",
    r"Please.*Sign": "DOCUSIGN_RELEASED",
    
    r"Buyer Signed": "DOCUSIGN_BUYER_SIGNED",
    r".*has signed": "DOCUSIGN_BUYER_SIGNED",
    
    r"Completed": "DOCUSIGN_EXECUTED",
    r"Fully Executed": "DOCUSIGN_EXECUTED",
    r"All parties.*signed": "DOCUSIGN_EXECUTED",
}
```

#### By Body Content Patterns

```python
BODY_PATTERNS = {
    r"signed the Expression of Interest": "EOI_SIGNED",
    r"Please find attached the Contract": "CONTRACT_FROM_VENDOR",
    r"completed our review": "SOLICITOR_APPROVED_WITH_APPOINTMENT",
    r"signing appointment": "SOLICITOR_APPROVED_WITH_APPOINTMENT",
    r"ready for review and signature": "DOCUSIGN_RELEASED",
    r"buyer has completed": "DOCUSIGN_BUYER_SIGNED",
    r"envelope has been completed": "DOCUSIGN_EXECUTED",
    r"All parties have signed": "DOCUSIGN_EXECUTED",
}
```

### Classification Algorithm

```python
def classify_email(email: ParsedEmail) -> ClassificationResult:
    """
    Classify email using sender, subject, and body patterns.
    Returns event type with confidence score.
    """
    candidates = []
    
    # Check sender patterns
    for pattern, event_types in SENDER_PATTERNS.items():
        if re.match(pattern, email.sender, re.IGNORECASE):
            for event_type in event_types:
                candidates.append((event_type, 0.3))  # Base confidence
    
    # Check subject patterns
    for pattern, event_type in SUBJECT_PATTERNS.items():
        if re.search(pattern, email.subject, re.IGNORECASE):
            candidates.append((event_type, 0.4))
    
    # Check body patterns
    for pattern, event_type in BODY_PATTERNS.items():
        if re.search(pattern, email.body, re.IGNORECASE):
            candidates.append((event_type, 0.3))
    
    # Aggregate scores by event type
    scores = defaultdict(float)
    for event_type, score in candidates:
        scores[event_type] += score
    
    if not scores:
        return ClassificationResult(event_type="UNKNOWN", confidence=0.0)
    
    # Return highest scoring
    best_event = max(scores.items(), key=lambda x: x[1])
    return ClassificationResult(
        event_type=best_event[0],
        confidence=min(best_event[1], 1.0)
    )
```

### Data Extraction

The Router extracts key identifiers from classified emails:

```python
def extract_deal_identifiers(email: ParsedEmail) -> DealIdentifiers:
    """Extract deal-related identifiers from email."""
    
    return DealIdentifiers(
        lot_number=extract_lot_number(email),
        property_address=extract_property_address(email),
        purchaser_names=extract_purchaser_names(email),
        appointment_datetime=extract_appointment_datetime(email),
    )

def extract_lot_number(email: ParsedEmail) -> Optional[str]:
    """Extract lot number from email subject or body."""
    patterns = [
        r"Lot\s*#?\s*(\d+)",
        r"Lot\s+(\d+)",
        r"LOT\s*(\d+)",
    ]
    
    text = email.subject + " " + email.body
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)
    return None

def extract_property_address(email: ParsedEmail) -> Optional[str]:
    """Extract property address from email."""
    # Look for patterns like "Lot XX, Address" or "Lot XX - Address"
    patterns = [
        r"Lot\s*\d+[,\s\-–]+([A-Za-z\s]+(?:VIC|NSW|QLD|SA|WA|TAS|NT|ACT)\s*\d{4})",
        r"Property:\s*(.+(?:VIC|NSW|QLD|SA|WA|TAS|NT|ACT)\s*\d{4})",
    ]
    
    text = email.subject + " " + email.body
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return None

def extract_purchaser_names(email: ParsedEmail) -> List[str]:
    """Extract purchaser names from email."""
    patterns = [
        r"(?:clients?|purchasers?|buyers?)\s+([A-Z][a-z]+(?:\s*&\s*|\s+and\s+)?[A-Z][a-z]+\s+[A-Z][a-z]+)",
        r"for\s+([A-Z][a-z]+(?:\s*&\s*|\s+and\s+)?[A-Z][a-z]+\s+[A-Z][a-z]+)",
    ]
    
    names = []
    for pattern in patterns:
        matches = re.findall(pattern, email.body)
        names.extend(matches)
    
    return names
```

### Appointment Date Resolution

Solicitor emails often contain relative dates that must be resolved:

```python
from dateutil import parser as date_parser
from dateutil.relativedelta import relativedelta, MO, TU, WE, TH, FR, SA, SU

WEEKDAY_MAP = {
    'monday': MO, 'tuesday': TU, 'wednesday': WE,
    'thursday': TH, 'friday': FR, 'saturday': SA, 'sunday': SU
}

def extract_appointment_datetime(email: ParsedEmail) -> Optional[datetime]:
    """
    Extract and resolve appointment datetime from email.
    Handles relative references like "Thursday at 11:30am".
    """
    # Pattern for relative day + time
    pattern = r"(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\s+at\s+(\d{1,2}[:\.]?\d{0,2}\s*(?:am|pm)?)"
    
    match = re.search(pattern, email.body, re.IGNORECASE)
    if not match:
        return None
    
    day_name = match.group(1).lower()
    time_str = match.group(2)
    
    # Parse the time
    try:
        time_part = date_parser.parse(time_str).time()
    except:
        return None
    
    # Resolve the day relative to email date
    email_date = email.timestamp.date()
    weekday = WEEKDAY_MAP[day_name]
    
    # Find next occurrence of that weekday
    target_date = email_date + relativedelta(weekday=weekday(+1))
    
    # Combine date and time
    return datetime.combine(target_date, time_part, tzinfo=email.timestamp.tzinfo)
```

### Output Schema

```python
@dataclass
class ClassificationResult:
    email_id: str
    event_type: str
    confidence: float
    deal_id: Optional[str]  # Resolved by Orchestrator
    extracted_data: DealIdentifiers

@dataclass
class DealIdentifiers:
    lot_number: Optional[str]
    property_address: Optional[str]
    purchaser_names: List[str]
    appointment_phrase: Optional[str]  # Raw text, e.g., "Thursday at 11:30am"
    appointment_datetime: Optional[datetime]  # Resolved datetime
```

---

## Part 2: Comms Agent — Implementation Logic

### Email Types

The Comms agent generates four types of outbound emails:

| Email Type | Trigger Condition | Recipient |
|------------|-------------------|-----------|
| `CONTRACT_TO_SOLICITOR` | Contract validated OK | Solicitor |
| `VENDOR_DOCUSIGN_RELEASE` | Solicitor approved + appointment set | Vendor |
| `DISCREPANCY_ALERT` | Contract has mismatches | Internal (support@) |
| `SLA_OVERDUE_ALERT` | Appointment + 2 days, no buyer signature | Internal (support@) |

### Template Structure

All templates use placeholder variables that are filled from deal context:

```python
PLACEHOLDERS = {
    "{{purchaser_names}}": "John & Jane Smith",  # Formatted purchaser names
    "{{lot_number}}": "95",
    "{{property_address}}": "Fake Rise VIC 3336",
    "{{full_property}}": "Lot 95 Fake Rise VIC 3336",
    "{{solicitor_name}}": "Michael Ken",
    "{{solicitor_email}}": "michael@biglegalfirm.com.au",
    "{{vendor_email}}": "contracts@buildwelldevelopments.com.au",
    "{{contract_filename}}": "CONTRACT_OF_SALE_V2.pdf",
    "{{contract_version}}": "V1",
    "{{signing_datetime}}": "Thursday, 16 January 2025 at 11:30 AM",
    "{{sla_deadline}}": "Saturday, 18 January 2025 at 9:00 AM",
    "{{time_overdue}}": "6 hours",
}
```

### Template: Contract to Solicitor

```python
CONTRACT_TO_SOLICITOR_TEMPLATE = """
From: support@onecorpaustralia.com.au
To: {{solicitor_email}}
Subject: Contract for Review – {{purchaser_names}} – {{full_property}}

Hi {{solicitor_name}},

Please find attached the contract for {{purchaser_names}} for your review.

Let us know if you have any questions.

Kind regards,
Adrian
OneCorp

Attachment: {{contract_filename}}
"""
```

### Template: Vendor DocuSign Release

```python
VENDOR_RELEASE_TEMPLATE = """
From: support@onecorpaustralia.com.au
To: {{vendor_email}}
Subject: RE: Contract Request: {{full_property}}

Hi Sarah,

The solicitor has approved the contract for {{purchaser_names}}.
Could you please release the contract via DocuSign for purchaser signing?

Thanks,
Adrian
OneCorp
"""
```

### Template: Discrepancy Alert (Internal)

```python
DISCREPANCY_ALERT_TEMPLATE = """
From: system@onecorpaustralia.com.au
To: support@onecorpaustralia.com.au
Subject: ⚠️ Contract Discrepancy Alert – {{full_property}}

Contract Version: {{contract_version}}
File: {{contract_filename}}
Risk Score: {{risk_score}}

The following discrepancies were found between the EOI and contract:

{{mismatch_table}}

Recommended Action:
{{amendment_recommendation}}

This contract should NOT proceed to solicitor until amendments are received.

— OneCorp Contract Workflow System
"""

def format_mismatch_table(mismatches: List[Mismatch]) -> str:
    """Format mismatches as readable table."""
    lines = ["| Field | EOI Value | Contract Value | Severity |"]
    lines.append("|-------|-----------|----------------|----------|")
    
    for m in mismatches:
        lines.append(f"| {format_field_name(m.field)} | {m.eoi_value} | {m.contract_value} | {m.severity} |")
    
    return "\n".join(lines)
```

### Template: SLA Overdue Alert (Internal)

```python
SLA_OVERDUE_TEMPLATE = """
From: system@onecorpaustralia.com.au
To: support@onecorpaustralia.com.au
Subject: 🚨 SLA Overdue – Buyer Signature Required – {{full_property}}

Property: {{full_property}}
Purchasers: {{purchaser_names}}
Solicitor: {{solicitor_name}} ({{solicitor_email}})

Signing Appointment: {{signing_datetime}}
SLA Deadline: {{sla_deadline}}
Current Status: DOCUSIGN_RELEASED (awaiting buyer signature)
Time Overdue: {{time_overdue}}

Recommended Action:
1. Contact solicitor to confirm appointment occurred
2. Contact purchasers to check for signing issues
3. Verify DocuSign envelope status

— OneCorp Contract Workflow System
"""
```

### Email Generation Function

```python
def generate_email(
    email_type: str, 
    deal_context: DealContext,
    comparison_result: Optional[ComparisonResult] = None
) -> GeneratedEmail:
    """
    Generate an outbound email from template and context.
    """
    template = get_template(email_type)
    
    # Build placeholder values from deal context
    placeholders = build_placeholders(deal_context)
    
    # Add comparison-specific placeholders if applicable
    if comparison_result and email_type == "DISCREPANCY_ALERT":
        placeholders["{{mismatch_table}}"] = format_mismatch_table(comparison_result.mismatches)
        placeholders["{{risk_score}}"] = comparison_result.risk_score
        placeholders["{{amendment_recommendation}}"] = comparison_result.amendment_recommendation
    
    # Fill template
    email_content = template
    for placeholder, value in placeholders.items():
        email_content = email_content.replace(placeholder, str(value))
    
    return parse_generated_email(email_content)
```

---

## Part 3: Email Triggers Table

| Current State | Event | Generated Email | Next State |
|---------------|-------|-----------------|------------|
| `CONTRACT_Vn_VALIDATED_OK` | (auto) | Contract to Solicitor | `SENT_TO_SOLICITOR` |
| `SOLICITOR_APPROVED` | (auto) | Vendor DocuSign Release | `DOCUSIGN_RELEASE_REQUESTED` |
| `CONTRACT_Vn_HAS_DISCREPANCIES` | (auto) | Discrepancy Alert | `AMENDMENT_REQUESTED` |
| `DOCUSIGN_RELEASED` | SLA timer fires | SLA Overdue Alert | `SLA_OVERDUE_ALERT_SENT` |

---

## Part 4: Demo Validation

### Email Manifest Reference

For the demo dataset, email metadata is defined in:

```
data/emails_manifest.json
```

This file contains timestamp, sender, recipients, and expected event type for each email. The Router should produce classifications matching the `expected_event` field.

### Input vs Output Emails

| File Pattern | Type | Purpose |
|--------------|------|---------|
| `data/emails/incoming/0X_*.txt` | INPUT | Emails the system processes |
| `data/emails/templates/0X_*.txt` | OUTPUT TEMPLATE | Reference format for generated emails |

**Important:** Emails 03 and 05 in the dataset are OUTPUT TEMPLATES (system generates these), not inputs to process.

### Validation Test Pattern

```python
def test_email_classification():
    """Router should classify demo emails correctly."""
    
    manifest = load_json('data/emails_manifest.json')
    
    for email_entry in manifest['emails']:
        if email_entry['type'] != 'INPUT':
            continue  # Skip output templates
        
        email = load_email(email_entry['file'])
        result = classify_email(email)
        
        assert result.event_type == email_entry['expected_event'], \
            f"Email {email_entry['email_id']}: expected {email_entry['expected_event']}, got {result.event_type}"
```

---

## Quick Reference

### Router Function Signatures

```python
def classify_email(email: ParsedEmail) -> ClassificationResult:
    """Classify email by event type."""

def extract_deal_identifiers(email: ParsedEmail) -> DealIdentifiers:
    """Extract lot, address, purchasers, appointment from email."""

def resolve_appointment_datetime(phrase: str, reference_date: datetime) -> datetime:
    """Convert relative date phrase to concrete datetime."""
```

### Comms Function Signatures

```python
def generate_email(email_type: str, deal_context: DealContext, ...) -> GeneratedEmail:
    """Generate outbound email from template."""

def format_mismatch_table(mismatches: List[Mismatch]) -> str:
    """Format mismatches for discrepancy alert."""
```
