"""Email classification agent for routing incoming emails to the correct workflow event.

This module implements a hybrid classification approach:
1. Deterministic pattern matching with confidence scoring (fast, no LLM cost)
2. LLM fallback for ambiguous cases (when confidence < 0.8)

The classifier uses pattern-based logic that generalizes to any property deal.
"""

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Literal, Optional, Any

from dotenv import load_dotenv
from openai import OpenAI

from src.utils.email_parser import ParsedEmail


# Load environment variables
load_dotenv()

# API Configuration
DEEPINFRA_API_KEY = os.getenv("DEEPINFRA_API_KEY")
DEEPINFRA_BASE_URL = "https://api.deepinfra.com/v1/openai"
DEEPSEEK_MODEL = "deepseek-ai/DeepSeek-V3.2"
MAX_TOKENS = 4000

# Confidence threshold for deterministic classification
CONFIDENCE_THRESHOLD = 0.8


@dataclass
class ClassificationResult:
    """Result of email classification.

    Attributes:
        event_type: The classified event type (one of 6 types)
        confidence: Confidence score (0.0 to 1.0)
        method: Classification method used ("deterministic" or "llm")
        metadata: Extracted metadata (lot_number, property_address, etc.)
    """
    event_type: str
    confidence: float
    method: Literal["deterministic", "llm"]
    metadata: Dict[str, Any] = field(default_factory=dict)


class ClassificationError(Exception):
    """Exception raised when classification fails."""
    pass


# ============================================================================
# Event Type Definitions
# ============================================================================

EVENT_TYPES = [
    "EOI_SIGNED",
    "CONTRACT_FROM_VENDOR",
    "SOLICITOR_APPROVED_WITH_APPOINTMENT",
    "DOCUSIGN_RELEASED",
    "DOCUSIGN_BUYER_SIGNED",
    "DOCUSIGN_EXECUTED",
]


# ============================================================================
# Deterministic Pattern Matching Rules
# ============================================================================

# Sender domain patterns mapped to possible event types
SENDER_PATTERNS = {
    # Internal OneCorp emails
    r".*@onecorpaustralia\.com\.au$": ["EOI_SIGNED"],

    # Vendor/developer emails
    r".*@.*developments?\.com\.au$": ["CONTRACT_FROM_VENDOR"],
    r"contracts@.*": ["CONTRACT_FROM_VENDOR"],
    r".*@buildwell.*": ["CONTRACT_FROM_VENDOR"],

    # Solicitor emails
    r".*@.*legal.*\.com\.au$": ["SOLICITOR_APPROVED_WITH_APPOINTMENT"],
    r".*@.*law.*\.com\.au$": ["SOLICITOR_APPROVED_WITH_APPOINTMENT"],

    # DocuSign system emails
    r".*@docusign\.(net|com)$": ["DOCUSIGN_RELEASED", "DOCUSIGN_BUYER_SIGNED", "DOCUSIGN_EXECUTED"],
}

# Subject line patterns mapped to event types
SUBJECT_PATTERNS = {
    "EOI_SIGNED": [
        r"EOI\s+Signed",
        r"Expression\s+of\s+Interest.*Signed",
    ],
    "CONTRACT_FROM_VENDOR": [
        r"Contract\s+Request",
        r"Contract\s+of\s+Sale.*attached",
        r"RE:\s*Contract\s+Request",
        r"Contract.*Amended",
    ],
    "SOLICITOR_APPROVED_WITH_APPOINTMENT": [
        r"RE:\s*Contract\s+for\s+Review",
        r"Contract.*Review",
    ],
    "DOCUSIGN_RELEASED": [
        r"Please.*DocuSign",
        r"Please.*Sign",
        r"ready\s+for.*signature",
    ],
    "DOCUSIGN_BUYER_SIGNED": [
        r"Buyer\s+Signed",
        r".*has\s+signed",
        r"completed.*signing",
    ],
    "DOCUSIGN_EXECUTED": [
        r"Completed",
        r"Fully\s+Executed",
        r"All\s+parties.*signed",
        r"Contract\s+Executed",
    ],
}

# Body content patterns mapped to event types
BODY_PATTERNS = {
    "EOI_SIGNED": [
        r"signed\s+the\s+Expression\s+of\s+Interest",
        r"EOI\s+document\s+is\s+attached",
        r"clients?\s+.*\s+have\s+signed",
    ],
    "CONTRACT_FROM_VENDOR": [
        r"Please\s+find\s+attached\s+the\s+Contract",
        r"Contract\s+for\s+the\s+purchasers?",
        r"Let\s+us\s+know\s+if\s+you\s+need\s+anything\s+amended",
        r"amended\s+contract",
    ],
    "SOLICITOR_APPROVED_WITH_APPOINTMENT": [
        r"completed\s+our\s+review",
        r"Everything\s+is\s+in\s+order",
        r"contract\s+is\s+approved",
        r"signing\s+appointment",
        r"appointment.*scheduled",
    ],
    "DOCUSIGN_RELEASED": [
        r"ready\s+for\s+review\s+and\s+signature",
        r"Please\s+click.*to\s+view\s+and\s+sign",
        r"document\s+ready\s+for\s+signature",
    ],
    "DOCUSIGN_BUYER_SIGNED": [
        r"buyer\s+has\s+completed.*signing",
        r"purchasers?\s+.*signed",
        r"Next\s+step:\s+Vendor\s+signature",
    ],
    "DOCUSIGN_EXECUTED": [
        r"envelope\s+has\s+been\s+completed",
        r"All\s+parties\s+have\s+signed",
        r"final\s+executed\s+contract",
        r"Download.*executed\s+contract",
    ],
}

# Attachment patterns
ATTACHMENT_PATTERNS = {
    "EOI_SIGNED": [r"EOI.*\.pdf", r"Expression.*Interest.*\.pdf"],
    "CONTRACT_FROM_VENDOR": [r"CONTRACT.*\.pdf", r"Contract.*Sale.*\.pdf"],
}


# ============================================================================
# Confidence Scoring Functions
# ============================================================================

def calculate_confidence(
    email: ParsedEmail,
    candidate_event_type: str,
    sender_match: bool,
    subject_matches: int,
    body_matches: int,
    attachment_match: bool,
    exclusivity: float
) -> float:
    """Calculate confidence score for a candidate event type.

    Args:
        email: Parsed email object
        candidate_event_type: The event type being evaluated
        sender_match: Whether sender domain matches this event type
        subject_matches: Number of subject patterns matched
        body_matches: Number of body patterns matched
        attachment_match: Whether attachments match this event type
        exclusivity: How exclusive the patterns are (0.0-1.0, higher = more exclusive)

    Returns:
        Confidence score between 0.0 and 1.0
    """
    score = 0.0

    # Sender domain match (strong signal)
    if sender_match:
        score += 0.35

    # Subject line matches
    if subject_matches > 0:
        score += min(subject_matches * 0.25, 0.40)  # Cap at 0.40 for multiple matches

    # Body content matches
    if body_matches > 0:
        score += min(body_matches * 0.15, 0.30)  # Cap at 0.30 for multiple matches

    # Attachment match
    if attachment_match:
        score += 0.20

    # Exclusivity bonus (if only one event type matches strongly)
    score += exclusivity * 0.15

    # Special case: DocuSign emails need strong subject/body disambiguation
    if candidate_event_type.startswith("DOCUSIGN_"):
        # DocuSign sender is guaranteed, but we need clear subject/body signals
        if subject_matches == 0 and body_matches == 0:
            score *= 0.5  # Penalize if only sender matches

    # Cap at 1.0
    return min(score, 1.0)


def classify_deterministic(email: ParsedEmail) -> ClassificationResult:
    """Classify email using deterministic pattern matching.

    Args:
        email: Parsed email object

    Returns:
        ClassificationResult with confidence score
    """
    candidates: Dict[str, Dict[str, Any]] = {}

    # Check sender patterns
    sender_matches = {}
    for pattern, event_types in SENDER_PATTERNS.items():
        if re.match(pattern, email.from_addr, re.IGNORECASE):
            for event_type in event_types:
                sender_matches[event_type] = True

    # Check subject patterns
    subject_matches = {}
    for event_type, patterns in SUBJECT_PATTERNS.items():
        count = 0
        for pattern in patterns:
            if re.search(pattern, email.subject, re.IGNORECASE):
                count += 1
        if count > 0:
            subject_matches[event_type] = count

    # Check body patterns
    body_matches = {}
    for event_type, patterns in BODY_PATTERNS.items():
        count = 0
        for pattern in patterns:
            if re.search(pattern, email.body, re.IGNORECASE):
                count += 1
        if count > 0:
            body_matches[event_type] = count

    # Check attachment patterns
    attachment_matches = {}
    for event_type, patterns in ATTACHMENT_PATTERNS.items():
        for attachment in email.attachment_filenames:
            for pattern in patterns:
                if re.search(pattern, attachment, re.IGNORECASE):
                    attachment_matches[event_type] = True
                    break

    # Aggregate candidates
    all_candidate_types = set(
        list(sender_matches.keys()) +
        list(subject_matches.keys()) +
        list(body_matches.keys()) +
        list(attachment_matches.keys())
    )

    # Calculate confidence for each candidate
    for event_type in all_candidate_types:
        # Calculate exclusivity (how many event types match)
        total_matches = len(all_candidate_types)
        exclusivity = 1.0 / total_matches if total_matches > 0 else 0.0

        confidence = calculate_confidence(
            email=email,
            candidate_event_type=event_type,
            sender_match=event_type in sender_matches,
            subject_matches=subject_matches.get(event_type, 0),
            body_matches=body_matches.get(event_type, 0),
            attachment_match=event_type in attachment_matches,
            exclusivity=exclusivity
        )

        candidates[event_type] = {
            "confidence": confidence,
            "signals": {
                "sender": event_type in sender_matches,
                "subject": subject_matches.get(event_type, 0),
                "body": body_matches.get(event_type, 0),
                "attachment": event_type in attachment_matches,
            }
        }

    # Select best candidate
    if not candidates:
        # No patterns matched
        return ClassificationResult(
            event_type="UNKNOWN",
            confidence=0.0,
            method="deterministic",
            metadata={}
        )

    best_event_type = max(candidates.items(), key=lambda x: x[1]["confidence"])
    event_type = best_event_type[0]
    confidence = best_event_type[1]["confidence"]

    # Extract metadata
    metadata = extract_metadata(email, event_type)

    return ClassificationResult(
        event_type=event_type,
        confidence=confidence,
        method="deterministic",
        metadata=metadata
    )


# ============================================================================
# Metadata Extraction Functions
# ============================================================================

def extract_lot_number(text: str) -> Optional[str]:
    """Extract lot number from text using pattern matching.

    Args:
        text: Combined subject + body text

    Returns:
        Lot number as string (e.g., "95") or None if not found
    """
    patterns = [
        r"Lot\s*#?\s*(\d+)",
        r"LOT\s*#?\s*(\d+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)

    return None


def extract_property_address(text: str) -> Optional[str]:
    """Extract property address from text.

    Looks for Australian address patterns with state codes.

    Args:
        text: Combined subject + body text

    Returns:
        Property address (e.g., "Fake Rise VIC 3336") or None
    """
    # Pattern: suburb/street name + state + postcode
    patterns = [
        r"(?:Lot\s*\d+[,\s\-]+)?([A-Z][A-Za-z\s]+(?:VIC|NSW|QLD|SA|WA|TAS|NT|ACT)\s*\d{4})",
        r"Property:\s*(.+?(?:VIC|NSW|QLD|SA|WA|TAS|NT|ACT)\s*\d{4})",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            address = match.group(1).strip()
            # Clean up common prefixes
            address = re.sub(r"^[\s\-,]+", "", address)
            return address

    return None


def extract_purchaser_names(text: str) -> List[str]:
    """Extract purchaser/buyer names from text.

    Args:
        text: Combined subject + body text

    Returns:
        List of purchaser names (e.g., ["John Smith", "Jane Smith"])
    """
    names = []

    # Pattern: "clients/purchasers/buyers Name & Name" or "Name and Name"
    patterns = [
        r"(?:clients?|purchasers?|buyers?)\s+([A-Z][a-z]+(?:\s*&\s*|\s+and\s+)[A-Z][a-z]+\s+[A-Z][a-z]+)",
        r"for\s+([A-Z][a-z]+(?:\s*&\s*|\s+and\s+)[A-Z][a-z]+\s+[A-Z][a-z]+)",
    ]

    for pattern in patterns:
        matches = re.findall(pattern, text)
        for match in matches:
            # Handle cases like "John & Jane Smith" (shared last name)
            # Split by & or "and"
            if "&" in match:
                parts = match.split("&")
            elif " and " in match:
                parts = match.split(" and ")
            else:
                parts = [match]

            # If we have 2 parts, check if the second has both first and last name
            if len(parts) == 2:
                first_part = parts[0].strip()
                second_part = parts[1].strip()

                # Check if second part has both first and last name
                second_match = re.match(r"([A-Z][a-z]+)\s+([A-Z][a-z]+)", second_part)
                if second_match:
                    # Second part has full name, extract it
                    second_name = f"{second_match.group(1)} {second_match.group(2)}"
                    last_name = second_match.group(2)

                    # Check if first part is just a first name (shared last name case)
                    first_match = re.match(r"^([A-Z][a-z]+)$", first_part)
                    if first_match:
                        # Shared last name case: "John & Jane Smith"
                        first_name = first_match.group(1)
                        first_full_name = f"{first_name} {last_name}"
                        if first_full_name not in names:
                            names.append(first_full_name)
                    else:
                        # First part might be a full name
                        first_full_match = re.match(r"([A-Z][a-z]+)\s+([A-Z][a-z]+)", first_part)
                        if first_full_match:
                            first_full_name = f"{first_full_match.group(1)} {first_full_match.group(2)}"
                            if first_full_name not in names:
                                names.append(first_full_name)

                    # Add second name
                    if second_name not in names:
                        names.append(second_name)
            else:
                # Single part or more than 2 parts - extract names directly
                for part in parts:
                    part = part.strip()
                    # Extract first and last name
                    name_match = re.match(r"([A-Z][a-z]+)\s+([A-Z][a-z]+)", part)
                    if name_match:
                        full_name = f"{name_match.group(1)} {name_match.group(2)}"
                        if full_name not in names:
                            names.append(full_name)

    return names if names else []


def extract_appointment_phrase(text: str) -> Optional[str]:
    """Extract appointment phrase from solicitor emails.

    Looks for patterns like "Thursday at 11:30am".

    Args:
        text: Email body text

    Returns:
        Raw appointment phrase (e.g., "Thursday at 11:30am") or None
    """
    # Pattern: day of week + "at" + time
    pattern = r"((?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\s+at\s+\d{1,2}:?\d{0,2}\s*(?:am|pm)?)"

    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        return match.group(1).strip()

    return None


def extract_contract_version(attachments: List[str]) -> Optional[str]:
    """Extract contract version from attachment filenames.

    Args:
        attachments: List of attachment filenames

    Returns:
        Version string (e.g., "V1", "V2") or None
    """
    for attachment in attachments:
        # Look for V1, V2, VERSION 1, VERSION 2, VERSION_1, VERSION_2 patterns
        match = re.search(r"_V(\d+)", attachment, re.IGNORECASE)
        if match:
            return f"V{match.group(1)}"

        match = re.search(r"VERSION[\s_]*(\d+)", attachment, re.IGNORECASE)
        if match:
            return f"V{match.group(1)}"

    return None


def extract_metadata(email: ParsedEmail, event_type: str) -> Dict[str, Any]:
    """Extract metadata from email based on event type.

    Args:
        email: Parsed email object
        event_type: Classified event type

    Returns:
        Dictionary of extracted metadata
    """
    metadata: Dict[str, Any] = {}

    # Combine subject and body for text extraction
    text = f"{email.subject} {email.body}"

    # Extract common fields
    lot_number = extract_lot_number(text)
    if lot_number:
        metadata["lot_number"] = lot_number

    property_address = extract_property_address(text)
    if property_address:
        metadata["property_address"] = property_address

    purchaser_names = extract_purchaser_names(text)
    if purchaser_names:
        metadata["purchaser_names"] = purchaser_names

    # Event-specific metadata
    if event_type == "SOLICITOR_APPROVED_WITH_APPOINTMENT":
        appointment_phrase = extract_appointment_phrase(email.body)
        if appointment_phrase:
            metadata["appointment_phrase"] = appointment_phrase

    if event_type == "CONTRACT_FROM_VENDOR":
        contract_version = extract_contract_version(email.attachment_filenames)
        if contract_version:
            metadata["contract_version"] = contract_version

    return metadata


# ============================================================================
# LLM Fallback Classification
# ============================================================================

def load_router_prompt() -> str:
    """Load the router system prompt from the prompts directory.

    Returns:
        System prompt content as string

    Raises:
        FileNotFoundError: If prompt file doesn't exist
    """
    prompt_path = Path(__file__).parent / "prompts" / "router_prompt.md"

    if not prompt_path.exists():
        raise FileNotFoundError(f"Router prompt not found: {prompt_path}")

    return prompt_path.read_text(encoding="utf-8")


def classify_with_llm(email: ParsedEmail) -> ClassificationResult:
    """Classify email using LLM fallback.

    Args:
        email: Parsed email object

    Returns:
        ClassificationResult from LLM

    Raises:
        ClassificationError: If LLM call fails
    """
    if not DEEPINFRA_API_KEY:
        raise ClassificationError(
            "DEEPINFRA_API_KEY environment variable not set. "
            "Cannot use LLM fallback classification."
        )

    # Load system prompt
    system_prompt = load_router_prompt()

    # Prepare email data for LLM
    email_data = {
        "from": email.from_addr,
        "to": email.to_addrs,
        "cc": email.cc_addrs,
        "subject": email.subject,
        "body": email.body,
        "attachments": email.attachment_filenames,
    }

    user_message = f"""Classify this email:

```json
{json.dumps(email_data, indent=2)}
```

Return your classification as a JSON object following the output format specified in the system prompt."""

    # Create OpenAI client configured for DeepInfra
    client = OpenAI(
        api_key=DEEPINFRA_API_KEY,
        base_url=DEEPINFRA_BASE_URL,
    )

    try:
        response = client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=0.1,  # Low temperature for consistent classification
            max_tokens=MAX_TOKENS,
        )

        response_text = response.choices[0].message.content.strip()

        # Parse JSON response (handle markdown code blocks)
        if "```json" in response_text:
            json_match = re.search(r"```json\s*\n(.*?)\n```", response_text, re.DOTALL)
            if json_match:
                response_text = json_match.group(1)
        elif "```" in response_text:
            json_match = re.search(r"```\s*\n(.*?)\n```", response_text, re.DOTALL)
            if json_match:
                response_text = json_match.group(1)

        result_data = json.loads(response_text)

        return ClassificationResult(
            event_type=result_data.get("event_type", "UNKNOWN"),
            confidence=result_data.get("confidence", 0.0),
            method="llm",
            metadata=result_data.get("metadata", {})
        )

    except Exception as e:
        raise ClassificationError(f"LLM classification failed: {e}")


# ============================================================================
# Main Classification Function
# ============================================================================

def classify_email(email: ParsedEmail) -> ClassificationResult:
    """Classify an email using hybrid approach (deterministic + LLM fallback).

    Process:
    1. Attempt deterministic pattern matching with confidence scoring
    2. If confidence >= 0.8, return deterministic result (fast, no LLM cost)
    3. If confidence < 0.8, fall back to LLM for ambiguous cases

    Args:
        email: Parsed email object

    Returns:
        ClassificationResult with event_type, confidence, method, and metadata

    Raises:
        ClassificationError: If both deterministic and LLM classification fail
    """
    # Step 1: Try deterministic classification
    deterministic_result = classify_deterministic(email)

    # Step 2: Check confidence threshold
    if deterministic_result.confidence >= CONFIDENCE_THRESHOLD:
        # High confidence - use deterministic result
        return deterministic_result

    # Step 3: Low confidence - fall back to LLM
    try:
        llm_result = classify_with_llm(email)
        return llm_result
    except ClassificationError as e:
        # LLM failed, return deterministic result with warning
        # (Better to have low-confidence deterministic result than nothing)
        deterministic_result.metadata["llm_fallback_failed"] = str(e)
        return deterministic_result
