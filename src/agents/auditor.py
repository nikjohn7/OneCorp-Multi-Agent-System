"""Contract vs EOI comparison (Auditor agent).

This module compares extracted EOI fields against extracted contract fields,
detects mismatches, assigns severities, computes overall risk/validity, and
generates amendment recommendations.

Deterministic logic is used to ensure generalizable, testable behavior. An LLM
helper using Qwen3 via DeepInfra is included for optional future use.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Tuple, Union, Literal

from dotenv import load_dotenv
from openai import OpenAI


# Load environment variables from .env
load_dotenv()

# DeepInfra / OpenAI-compatible config
DEEPINFRA_API_KEY = os.getenv("DEEPINFRA_API_KEY")
DEEPINFRA_BASE_URL = "https://api.deepinfra.com/v1/openai"
QWEN_MODEL = "Qwen/Qwen3-235B-A22B-Instruct-2507"
MAX_TOKENS = 6000


class AuditError(Exception):
    """Raised when contract auditing fails."""


@dataclass
class Mismatch:
    """A single field mismatch between EOI and Contract."""

    field: str
    field_display: str
    eoi_value: Any
    contract_value: Any
    severity: str
    rationale: str
    eoi_value_formatted: Optional[str] = None
    contract_value_formatted: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "field": self.field,
            "field_display": self.field_display,
            "eoi_value": self.eoi_value,
            "contract_value": self.contract_value,
            "severity": self.severity,
            "rationale": self.rationale,
        }
        if self.eoi_value_formatted is not None:
            data["eoi_value_formatted"] = self.eoi_value_formatted
        if self.contract_value_formatted is not None:
            data["contract_value_formatted"] = self.contract_value_formatted
        return data


@dataclass
class ComparisonResult:
    """Result of comparing a contract to an EOI."""

    contract_version: Optional[str]
    source_file: Optional[str]
    compared_against: Optional[str]
    is_valid: bool
    risk_score: str
    mismatch_count: int
    mismatches: List[Mismatch]
    amendment_recommendation: Optional[str]
    next_action: str
    should_send_to_solicitor: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "contract_version": self.contract_version,
            "source_file": self.source_file,
            "compared_against": self.compared_against,
            "is_valid": self.is_valid,
            "risk_score": self.risk_score,
            "mismatch_count": self.mismatch_count,
            "mismatches": [m.to_dict() for m in self.mismatches],
            "amendment_recommendation": self.amendment_recommendation,
            "next_action": self.next_action,
            "should_send_to_solicitor": self.should_send_to_solicitor,
        }


# ----------------------------------------------------------------------------
# Configuration: comparable fields, display names, severities
# ----------------------------------------------------------------------------

COMPARABLE_FIELDS: List[str] = [
    "property.lot_number",
    "property.address",
    "pricing.total_price",
    "pricing.land_price",
    "pricing.build_price",
    "pricing.tenancy_split",
    "finance.is_subject_to_finance",
    "finance.terms",
    "purchaser_1.first_name",
    "purchaser_1.last_name",
    "purchaser_1.email",
    "purchaser_1.mobile",
    "purchaser_2.first_name",
    "purchaser_2.last_name",
    "purchaser_2.email",
    "purchaser_2.mobile",
    "solicitor.firm_name",
    "solicitor.contact_name",
    "solicitor.email",
    "solicitor.phone",
    "deposits.eoi_deposit",
    "deposits.build_deposit",
    "deposits.balance_deposit",
    "deposits.total_deposit",
]

SEVERITY_MAP: Dict[str, str] = {
    "property.lot_number": "HIGH",
    "property.address": "HIGH",
    "pricing.total_price": "HIGH",
    "finance.is_subject_to_finance": "HIGH",
    "purchaser_1.first_name": "HIGH",
    "purchaser_1.last_name": "HIGH",
    "purchaser_2.first_name": "HIGH",
    "purchaser_2.last_name": "HIGH",
    "pricing.build_price": "MEDIUM",
    "pricing.land_price": "MEDIUM",
    "pricing.tenancy_split": "MEDIUM",
    "deposits.eoi_deposit": "MEDIUM",
    "deposits.build_deposit": "MEDIUM",
    "deposits.balance_deposit": "MEDIUM",
    "deposits.total_deposit": "MEDIUM",
    "purchaser_1.email": "LOW",
    "purchaser_2.email": "LOW",
    "purchaser_1.mobile": "LOW",
    "purchaser_2.mobile": "LOW",
    "solicitor.email": "LOW",
    "solicitor.phone": "LOW",
    "solicitor.firm_name": "LOW",
    "solicitor.contact_name": "LOW",
}


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------


def _get_nested(data: Dict[str, Any], field_path: str) -> Any:
    current: Any = data
    for part in field_path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _normalize_name(text: str) -> str:
    return _normalize_whitespace(text).lower()


def _normalize_address(text: str) -> str:
    # Ignore commas/periods and case; keep digits/letters/spaces.
    cleaned = re.sub(r"[,\.\-]", " ", text)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip().lower()


def _normalize_email(email: str) -> str:
    email = email.strip()
    if "@" not in email:
        return email.lower()
    local, domain = email.split("@", 1)
    return f"{local.strip()}@{domain.strip().lower()}"


def _format_currency(value: Optional[Union[int, float, str]]) -> Optional[str]:
    if value is None:
        return None
    try:
        int_val = int(float(str(value).replace("$", "").replace(",", "").strip()))
    except (ValueError, TypeError):
        return str(value)
    return f"${int_val:,}"


def _finance_display(value: Optional[bool]) -> Optional[str]:
    if value is None:
        return None
    return "Subject to Finance" if value else "Not Subject to Finance"


def _field_display(field_path: str, eoi_fields: Dict[str, Any]) -> str:
    if field_path == "property.lot_number":
        return "Lot Number"
    if field_path == "property.address":
        return "Property Address"
    if field_path == "pricing.total_price":
        return "Total Price"
    if field_path == "pricing.land_price":
        return "Land Price"
    if field_path == "pricing.build_price":
        return "Build Price"
    if field_path == "pricing.tenancy_split":
        return "Tenancy Split"
    if field_path == "finance.is_subject_to_finance":
        return "Finance Terms"
    if field_path.startswith("purchaser_"):
        purchaser_key, subfield = field_path.split(".", 1)
        purchaser = eoi_fields.get(purchaser_key, {}) if isinstance(eoi_fields.get(purchaser_key), dict) else {}
        first = purchaser.get("first_name")
        last = purchaser.get("last_name")
        full = " ".join([p for p in [first, last] if p])
        label_base = full or purchaser_key.replace("_", " ").title()
        return f"{label_base} {subfield.replace('_', ' ').title()}"
    if field_path.startswith("solicitor."):
        return f"Solicitor {field_path.split('.', 1)[1].replace('_', ' ').title()}"
    if field_path.startswith("deposits."):
        return field_path.split(".", 1)[1].replace("_", " ").title()
    return field_path.replace("_", " ").title()


def _get_severity(field_path: str) -> str:
    return SEVERITY_MAP.get(field_path, "LOW")


def _values_match(field_path: str, eoi_value: Any, contract_value: Any) -> bool:
    # Treat both None as matching.
    if eoi_value is None and contract_value is None:
        return True

    # Finance terms handled by boolean comparison.
    if field_path == "finance.terms":
        return True

    if field_path.endswith(".lot_number"):
        return str(eoi_value).strip() == str(contract_value).strip()

    if field_path.endswith(".total_price") or field_path.endswith(".land_price") or field_path.endswith(".build_price") or field_path.startswith("deposits."):
        try:
            return int(eoi_value) == int(contract_value)
        except (TypeError, ValueError):
            return False

    if field_path.endswith(".is_subject_to_finance"):
        return bool(eoi_value) == bool(contract_value)

    if field_path.endswith(".email"):
        if eoi_value is None or contract_value is None:
            return False
        return _normalize_email(str(eoi_value)) == _normalize_email(str(contract_value))

    if field_path.endswith(".address"):
        if eoi_value is None or contract_value is None:
            return False
        return _normalize_address(str(eoi_value)) == _normalize_address(str(contract_value))

    if isinstance(eoi_value, str) and isinstance(contract_value, str):
        return _normalize_name(eoi_value) == _normalize_name(contract_value)

    return eoi_value == contract_value


def _rationale_for(field_path: str, eoi_value: Any, contract_value: Any, deltas: Dict[str, int]) -> str:
    if field_path == "property.lot_number":
        return "Lot number mismatch affects title registration - legally critical"
    if field_path == "pricing.total_price":
        delta = deltas.get("pricing.total_price")
        if delta is not None:
            return f"Price difference of {_format_currency(delta)} - financially material"
        return "Total price mismatch - financially material"
    if field_path == "pricing.build_price":
        delta = deltas.get("pricing.build_price")
        if delta is not None:
            return f"Build price difference of {_format_currency(delta)} - explains total price mismatch"
        return "Build price mismatch - may explain total price mismatch"
    if field_path == "pricing.land_price":
        delta = deltas.get("pricing.land_price")
        if delta is not None:
            return f"Land price difference of {_format_currency(delta)} - contributes to total price mismatch"
        return "Land price mismatch - contributes to total price mismatch"
    if field_path.endswith(".email"):
        return "Email address typo - may affect DocuSign delivery"
    if field_path == "finance.is_subject_to_finance":
        return (
            "Boolean inversion of finance terms creates legal liability - "
            "purchaser may have different obligations"
        )
    return f"{field_path.replace('_', ' ')} mismatch"


def _compute_deltas(eoi_fields: Dict[str, Any], contract_fields: Dict[str, Any]) -> Dict[str, int]:
    deltas: Dict[str, int] = {}
    for path in ["pricing.total_price", "pricing.build_price", "pricing.land_price"]:
        e = _get_nested(eoi_fields, path)
        c = _get_nested(contract_fields, path)
        try:
            if e is not None and c is not None:
                deltas[path] = abs(int(c) - int(e))
        except (TypeError, ValueError):
            continue
    return deltas


def _generate_recommendation(mismatches: List[Mismatch]) -> str:
    severity_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    sorted_ms = sorted(mismatches, key=lambda m: severity_order.get(m.severity, 3))
    parts: List[str] = []
    for idx, m in enumerate(sorted_ms, 1):
        if m.field == "property.lot_number":
            parts.append(f"({idx}) Lot number from {m.contract_value} to {m.eoi_value}")
        elif m.field.startswith("pricing."):
            parts.append(
                f"({idx}) {m.field_display} from {m.contract_value_formatted or m.contract_value} "
                f"to {m.eoi_value_formatted or m.eoi_value}"
            )
        elif m.field == "finance.is_subject_to_finance":
            from_text = _finance_display(bool(m.contract_value))
            to_text = _finance_display(bool(m.eoi_value))
            parts.append(f"({idx}) Finance terms from '{from_text}' to '{to_text}' as per EOI")
        elif m.field.endswith(".email"):
            parts.append(
                f"({idx}) {m.field_display.split(' Email')[0]}'s email from {m.contract_value} to {m.eoi_value}"
            )
        else:
            parts.append(f"({idx}) {m.field_display} from {m.contract_value} to {m.eoi_value}")
    return "Request vendor to correct: " + ", ".join(parts) + "."


def _risk_score(mismatches: List[Mismatch]) -> str:
    if not mismatches:
        return "NONE"
    severities = {m.severity for m in mismatches}
    if "HIGH" in severities:
        return "HIGH"
    if "MEDIUM" in severities:
        return "MEDIUM"
    return "LOW"


# ----------------------------------------------------------------------------
# Optional LLM helper (Qwen3 via DeepInfra)
# ----------------------------------------------------------------------------


def load_auditor_prompt() -> str:
    """Load auditor system prompt."""
    prompt_path = Path(__file__).parent / "prompts" / "auditor_prompt.md"
    if not prompt_path.exists():
        raise FileNotFoundError(f"Auditor prompt not found: {prompt_path}")
    return prompt_path.read_text(encoding="utf-8")


def call_auditor_llm(
    eoi_fields: Dict[str, Any],
    contract_fields: Dict[str, Any],
    contract_version: Optional[str],
    source_file: Optional[str],
    compared_against: Optional[str],
) -> Dict[str, Any]:
    """Call Qwen3 Auditor LLM for a comparison result.

    This is not used by default in deterministic comparison, but can be used
    for ambiguous cases in future tasks.
    """
    if not DEEPINFRA_API_KEY:
        raise AuditError(
            "DEEPINFRA_API_KEY environment variable not set. "
            "Please set it to use the Auditor LLM."
        )

    client = OpenAI(api_key=DEEPINFRA_API_KEY, base_url=DEEPINFRA_BASE_URL)
    system_prompt = load_auditor_prompt()
    user_payload = {
        "eoi_fields": eoi_fields,
        "contract_fields": contract_fields,
        "contract_version": contract_version,
        "source_file": source_file,
        "compared_against": compared_against,
    }
    response = client.chat.completions.create(
        model=QWEN_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(user_payload)},
        ],
        max_tokens=MAX_TOKENS,
        temperature=0.1,
    )
    content = response.choices[0].message.content or ""
    if "```json" in content:
        content = content.split("```json", 1)[1].split("```", 1)[0].strip()
    elif "```" in content:
        content = content.split("```", 1)[1].split("```", 1)[0].strip()
    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        raise AuditError(f"Failed to parse Auditor LLM response: {e}\nResponse: {content}")


# ----------------------------------------------------------------------------
# Public API
# ----------------------------------------------------------------------------


LLMMode = Literal["deterministic", "auto", "llm"]


def _is_int_like(value: Any) -> bool:
    if value is None:
        return False
    try:
        int(str(value).replace("$", "").replace(",", "").strip())
        return True
    except (ValueError, TypeError):
        return False


def _address_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, _normalize_address(a), _normalize_address(b)).ratio()


def _finance_terms_conflict(finance_block: Any) -> bool:
    if not isinstance(finance_block, dict):
        return False
    terms = str(finance_block.get("terms") or "").lower()
    is_subject = finance_block.get("is_subject_to_finance")
    if is_subject is None or not terms:
        return False
    # Heuristic semantic check.
    contains_not = "not subject" in terms or "not" in terms and "subject to finance" in terms
    contains_subject = "subject to finance" in terms or "is subject" in terms
    if contains_not and bool(is_subject) is True:
        return True
    if contains_subject and bool(is_subject) is False:
        return True
    return False


def _detect_doubt(
    eoi_fields: Dict[str, Any],
    contract_fields: Dict[str, Any],
    mismatches: List[Mismatch],
) -> Tuple[bool, List[str]]:
    """Detect whether deterministic comparison is uncertain.

    Returns:
        (has_doubt, reasons)
    """
    reasons: List[str] = []

    # Critical fields: any missing on either side triggers doubt.
    critical_paths = [
        "purchaser_1.first_name",
        "purchaser_1.last_name",
        "purchaser_1.email",
        "purchaser_2.first_name",
        "purchaser_2.last_name",
        "purchaser_2.email",
        "property.lot_number",
        "property.address",
        "pricing.total_price",
        "finance.is_subject_to_finance",
    ]
    for path in critical_paths:
        if _get_nested(eoi_fields, path) is None or _get_nested(contract_fields, path) is None:
            reasons.append(f"missing critical field: {path}")

    # Numeric parse uncertainty.
    numeric_paths = [
        "pricing.total_price",
        "pricing.land_price",
        "pricing.build_price",
        "deposits.eoi_deposit",
        "deposits.build_deposit",
        "deposits.balance_deposit",
        "deposits.total_deposit",
    ]
    for path in numeric_paths:
        e = _get_nested(eoi_fields, path)
        c = _get_nested(contract_fields, path)
        if (e is not None and not _is_int_like(e)) or (c is not None and not _is_int_like(c)):
            reasons.append(f"non-numeric value for {path}")

    # Finance semantic conflict between terms and boolean.
    if _finance_terms_conflict(eoi_fields.get("finance")) or _finance_terms_conflict(contract_fields.get("finance")):
        reasons.append("finance terms text conflicts with boolean")

    # Near-match address mismatch (likely formatting variance).
    for m in mismatches:
        if m.field == "property.address" and isinstance(m.eoi_value, str) and isinstance(m.contract_value, str):
            sim = _address_similarity(m.eoi_value, m.contract_value)
            if sim >= 0.85:
                reasons.append("property address close but not exact")

    return (len(reasons) > 0), reasons


def compare_contract_to_eoi(
    eoi_data: Dict[str, Any],
    contract_data: Dict[str, Any],
    *,
    use_llm: Union[bool, LLMMode] = "auto",
) -> Dict[str, Any]:
    """Compare contract extracted fields against EOI extracted fields.

    Args:
        eoi_data: Extracted EOI JSON object or dict with "fields" key.
        contract_data: Extracted contract JSON object or dict with "fields" key.
        use_llm: If True, call Qwen3 Auditor LLM instead of deterministic logic.

    Returns:
        Dict matching the schema in auditor_prompt.md / v1_mismatches.json.

    Raises:
        AuditError: If inputs are malformed or LLM call fails.
    """
    eoi_fields = eoi_data.get("fields", eoi_data)
    contract_fields = contract_data.get("fields", contract_data)
    if not isinstance(eoi_fields, dict) or not isinstance(contract_fields, dict):
        raise AuditError("compare_contract_to_eoi expects dict inputs with 'fields'")

    contract_version = contract_data.get("version") or contract_data.get("contract_version")
    source_file = contract_data.get("source_file")
    compared_against = eoi_data.get("source_file")

    mode: LLMMode
    if use_llm is True:
        mode = "llm"
    elif use_llm is False:
        mode = "deterministic"
    else:
        mode = use_llm

    llm_disabled = os.getenv("AUDITOR_DISABLE_LLM", "").lower() in {"1", "true", "yes"}

    if mode == "llm":
        return call_auditor_llm(
            eoi_fields=eoi_fields,
            contract_fields=contract_fields,
            contract_version=contract_version,
            source_file=source_file,
            compared_against=compared_against,
        )

    mismatches: List[Mismatch] = []
    deltas = _compute_deltas(eoi_fields, contract_fields)

    for field_path in COMPARABLE_FIELDS:
        # Avoid double-counting finance terms when boolean differs.
        if field_path == "finance.terms":
            continue

        eoi_value = _get_nested(eoi_fields, field_path)
        contract_value = _get_nested(contract_fields, field_path)

        if _values_match(field_path, eoi_value, contract_value):
            continue

        field_display = _field_display(field_path, eoi_fields)
        severity = _get_severity(field_path)
        rationale = _rationale_for(field_path, eoi_value, contract_value, deltas)

        eoi_formatted = None
        contract_formatted = None

        if field_path.startswith("pricing.") or field_path.startswith("deposits."):
            eoi_formatted = _format_currency(eoi_value)
            contract_formatted = _format_currency(contract_value)

        if field_path == "finance.is_subject_to_finance":
            eoi_formatted = eoi_fields.get("finance", {}).get("terms") or _finance_display(bool(eoi_value))
            contract_formatted = contract_fields.get("finance", {}).get("terms") or _finance_display(bool(contract_value))

        mismatches.append(
            Mismatch(
                field=field_path,
                field_display=field_display,
                eoi_value=eoi_value,
                contract_value=contract_value,
                severity=severity,
                rationale=rationale,
                eoi_value_formatted=eoi_formatted,
                contract_value_formatted=contract_formatted,
            )
        )

    # Auto LLM trigger if any doubt detected.
    has_doubt, doubt_reasons = _detect_doubt(eoi_fields, contract_fields, mismatches)
    if mode == "auto" and has_doubt and not llm_disabled:
        try:
            return call_auditor_llm(
                eoi_fields=eoi_fields,
                contract_fields=contract_fields,
                contract_version=contract_version,
                source_file=source_file,
                compared_against=compared_against,
            )
        except Exception:
            # Fall back to deterministic output but flag for review.
            pass

    mismatch_count = len(mismatches)
    risk_score = _risk_score(mismatches)
    is_valid = mismatch_count == 0 and not has_doubt
    should_send_to_solicitor = is_valid

    amendment_recommendation = _generate_recommendation(mismatches) if mismatches else None
    if has_doubt:
        next_action = "REQUEST_HUMAN_REVIEW"
    else:
        next_action = "PROCEED_TO_SOLICITOR" if is_valid else "SEND_DISCREPANCY_ALERT"

    result = ComparisonResult(
        contract_version=contract_version,
        source_file=source_file,
        compared_against=compared_against,
        is_valid=is_valid,
        risk_score=risk_score,
        mismatch_count=mismatch_count,
        mismatches=mismatches,
        amendment_recommendation=amendment_recommendation,
        next_action=next_action,
        should_send_to_solicitor=should_send_to_solicitor,
    )
    return result.to_dict()
