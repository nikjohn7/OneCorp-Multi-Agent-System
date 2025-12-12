"""Outbound email generation (Comms agent).

Implements a hybrid approach:
1) Deterministic assembly of headers + required facts.
2) Optional LLM phrasing layer (Qwen3 via DeepInfra) to produce natural bodies.
3) Post‑validation to ensure all mandatory information is present.

The logic is pattern‑based and generalizable; no demo hardcoding.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from openai import OpenAI

from src.agents.auditor import ComparisonResult, Mismatch


load_dotenv()

DEEPINFRA_API_KEY = os.getenv("DEEPINFRA_API_KEY")
DEEPINFRA_BASE_URL = "https://api.deepinfra.com/v1/openai"
QWEN_MODEL = "Qwen/Qwen3-235B-A22B-Instruct-2507"
MAX_TOKENS = 1200
DEFAULT_TEMPERATURE = 0.35


class CommsError(Exception):
    """Raised when comms email generation fails."""


@dataclass
class GeneratedEmail:
    """Structured outbound email."""

    from_addr: str
    to_addrs: List[str]
    cc_addrs: List[str] = field(default_factory=list)
    subject: str = ""
    body: str = ""
    attachments: List[str] = field(default_factory=list)
    email_type: str = ""
    generated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_text(self) -> str:
        """Render email to plain text."""
        headers = [
            f"From: {self.from_addr}",
            f"To: {', '.join(self.to_addrs)}",
        ]
        if self.cc_addrs:
            headers.append(f"Cc: {', '.join(self.cc_addrs)}")
        if self.subject:
            headers.append(f"Subject: {self.subject}")
        text = "\n".join(headers) + "\n\n" + self.body.strip()
        if self.attachments:
            text += "\n\nAttachment: " + ", ".join(self.attachments)
        return text.strip() + "\n"


def load_comms_prompt() -> str:
    """Load the comms system prompt."""
    prompt_path = Path(__file__).parent / "prompts" / "comms_prompt.md"
    if not prompt_path.exists():
        raise FileNotFoundError(f"Comms prompt not found: {prompt_path}")
    return prompt_path.read_text(encoding="utf-8")


def _format_currency(value: Any) -> str:
    text = str(value).strip()
    try:
        number = int(float(text.replace("$", "").replace(",", "")))
        return f"${number:,}"
    except Exception:
        return text


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def _validate_required_fields(body: str, required_fields: Dict[str, str]) -> List[str]:
    """Return list of required field keys missing from body."""
    body_norm = _normalize(body)
    missing: List[str] = []
    for key, value in required_fields.items():
        if value is None:
            continue
        value_text = str(value).strip()
        if not value_text:
            continue
        # Allow minor currency formatting differences.
        candidates = {value_text, _format_currency(value_text)}
        found = any(_normalize(cand) in body_norm for cand in candidates)
        if not found:
            missing.append(key)
    return missing


def _call_comms_llm(
    email_type: str,
    context: Dict[str, Any],
    required_fields: Dict[str, str],
    system_prompt: str,
    temperature: float = DEFAULT_TEMPERATURE,
    repair_missing: Optional[List[str]] = None,
) -> str:
    if not DEEPINFRA_API_KEY:
        raise CommsError(
            "DEEPINFRA_API_KEY environment variable not set. "
            "Set it to enable LLM‑phrased emails."
        )

    client = OpenAI(api_key=DEEPINFRA_API_KEY, base_url=DEEPINFRA_BASE_URL)

    checklist_lines = []
    for k, v in required_fields.items():
        if v is None or str(v).strip() == "":
            continue
        checklist_lines.append(f"- {k}: {v}")

    user_message = (
        "Draft an email body using the facts below.\n\n"
        f"email_type: {email_type}\n\n"
        "required_fields (must all be included):\n"
        + "\n".join(checklist_lines)
        + "\n\ncontext (facts, JSON):\n"
        + re.sub(r"\s+", " ", str(context))
    )
    if repair_missing:
        user_message += (
            "\n\nThe previous draft was missing these required fields:\n"
            + "\n".join(f"- {m}" for m in repair_missing)
            + "\nPlease rewrite the body including them. Do not add new facts."
        )

    response = client.chat.completions.create(
        model=QWEN_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        max_tokens=MAX_TOKENS,
        temperature=temperature,
    )
    content = response.choices[0].message.content
    if not content:
        raise CommsError("LLM returned empty email body")
    return content.strip()


def _deterministic_body_contract_to_solicitor(
    solicitor_name: Optional[str],
    purchaser_names: str,
    full_property: str,
) -> str:
    greeting = f"Hi {solicitor_name}," if solicitor_name else "Hi,"
    return (
        f"{greeting}\n\n"
        f"Please find attached the contract for {purchaser_names} "
        f"for your review ({full_property}).\n\n"
        "Let us know if you have any questions.\n\n"
        "Kind regards,\n"
        "OneCorp"
    )


def _deterministic_body_vendor_release(
    vendor_contact_name: Optional[str],
    purchaser_names: str,
    full_property: str,
) -> str:
    greeting = f"Hi {vendor_contact_name}," if vendor_contact_name else "Hi,"
    return (
        f"{greeting}\n\n"
        f"The solicitor has approved the contract for {purchaser_names} "
        f"({full_property}).\n"
        "Could you please release the contract via DocuSign for purchaser signing?\n\n"
        "Thanks,\n"
        "OneCorp"
    )


def _deterministic_body_discrepancy_alert(
    full_property: str,
    contract_filename: str,
    mismatches: List[Mismatch],
    risk_score: Optional[str],
    recommendation: Optional[str],
) -> str:
    lines = [
        "Discrepancy detected between EOI and contract.",
        f"Property: {full_property}",
        f"Contract file: {contract_filename}",
        "",
        "Mismatches:",
    ]
    for m in mismatches:
        lines.append(
            f"- {m.field_display}: EOI '{m.eoi_value_formatted or m.eoi_value}' "
            f"vs Contract '{m.contract_value_formatted or m.contract_value}' "
            f"(Severity: {m.severity})"
        )
    if risk_score:
        lines.append("")
        lines.append(f"Risk score: {risk_score}")
    if recommendation:
        lines.append(f"Recommendation: {recommendation}")
    lines.append("")
    lines.append("Please review and request amendments if required.")
    return "\n".join(lines).strip()


def _coerce_comparison_result(
    comparison_result: ComparisonResult | Dict[str, Any],
) -> ComparisonResult:
    """Coerce dict comparison results into ComparisonResult.

    Some tests/flows may pass a plain dict (e.g., from ComparisonResult.to_dict()).
    """
    if isinstance(comparison_result, ComparisonResult):
        return comparison_result

    mismatches_raw = comparison_result.get("mismatches", []) if isinstance(comparison_result, dict) else []
    mismatches: List[Mismatch] = []
    for m in mismatches_raw:
        if isinstance(m, Mismatch):
            mismatches.append(m)
            continue
        if isinstance(m, dict):
            mismatches.append(
                Mismatch(
                    field=m.get("field", ""),
                    field_display=m.get("field_display", m.get("field", "")),
                    eoi_value=m.get("eoi_value"),
                    contract_value=m.get("contract_value"),
                    severity=m.get("severity", "LOW"),
                    rationale=m.get("rationale", ""),
                    eoi_value_formatted=m.get("eoi_value_formatted"),
                    contract_value_formatted=m.get("contract_value_formatted"),
                )
            )

    return ComparisonResult(
        contract_version=comparison_result.get("contract_version"),
        source_file=comparison_result.get("source_file"),
        compared_against=comparison_result.get("compared_against"),
        is_valid=bool(comparison_result.get("is_valid")),
        risk_score=str(comparison_result.get("risk_score") or ""),
        mismatch_count=int(comparison_result.get("mismatch_count") or len(mismatches)),
        mismatches=mismatches,
        amendment_recommendation=comparison_result.get("amendment_recommendation"),
        next_action=str(comparison_result.get("next_action") or ""),
        should_send_to_solicitor=bool(comparison_result.get("should_send_to_solicitor")),
    )


def _deterministic_body_sla_overdue(
    full_property: str,
    purchaser_names: str,
    solicitor_name: Optional[str],
    solicitor_email: Optional[str],
    signing_datetime: str,
    sla_deadline: str,
    time_overdue: str,
    recommended_actions: Optional[List[str]] = None,
) -> str:
    lines = [
        "SLA overdue for buyer DocuSign signature.",
        f"Property: {full_property}",
        f"Purchasers: {purchaser_names}",
    ]
    if solicitor_name or solicitor_email:
        lines.append(
            f"Solicitor: {solicitor_name or 'Unknown'}"
            + (f" ({solicitor_email})" if solicitor_email else "")
        )
    lines.extend(
        [
            f"Signing appointment: {signing_datetime}",
            f"SLA deadline: {sla_deadline}",
            f"Time overdue: {time_overdue}",
            "",
            "Recommended action:",
        ]
    )
    actions = recommended_actions or [
        "Contact solicitor to confirm appointment occurred.",
        "Contact purchasers to check for signing issues.",
        "Verify DocuSign envelope status.",
    ]
    for i, action in enumerate(actions, start=1):
        lines.append(f"{i}. {action}")
    return "\n".join(lines).strip()


def _build_email_with_llm(
    email_type: str,
    headers: Dict[str, Any],
    required_fields: Dict[str, str],
    deterministic_body: str,
    context: Dict[str, Any],
    use_llm: bool = True,
) -> GeneratedEmail:
    body = deterministic_body
    if use_llm:
        system_prompt = load_comms_prompt()
        body = _call_comms_llm(email_type, context, required_fields, system_prompt)
        missing = _validate_required_fields(body, required_fields)
        if missing:
            body = _call_comms_llm(
                email_type, context, required_fields, system_prompt, repair_missing=missing
            )
            missing2 = _validate_required_fields(body, required_fields)
            if missing2:
                body = deterministic_body

    return GeneratedEmail(
        email_type=email_type,
        from_addr=headers["from_addr"],
        to_addrs=headers["to_addrs"],
        cc_addrs=headers.get("cc_addrs", []),
        subject=headers.get("subject", ""),
        body=body,
        attachments=headers.get("attachments", []),
    )


def build_contract_to_solicitor_email(
    context: Dict[str, Any],
    use_llm: bool = True,
) -> GeneratedEmail:
    """Build contract‑to‑solicitor email."""
    fields = context.get("fields", context)
    property_fields = fields.get("property", {}) if isinstance(fields, dict) else {}
    solicitor = fields.get("solicitor", {}) if isinstance(fields, dict) else {}

    lot_number = property_fields.get("lot_number")
    address = property_fields.get("address")
    full_property = " ".join([p for p in [f"Lot {lot_number}" if lot_number else None, address] if p]).strip()

    purchaser_names = context.get("purchaser_names") or fields.get("purchaser_names") or context.get("purchasers")
    if isinstance(purchaser_names, list):
        purchaser_names_str = " & ".join(purchaser_names)
    else:
        purchaser_names_str = str(purchaser_names or "").strip()

    solicitor_email = solicitor.get("email") or context.get("solicitor_email")
    solicitor_name = solicitor.get("contact_name") or solicitor.get("firm_name") or context.get("solicitor_name")

    contract_filename = context.get("contract_filename") or context.get("attachment_name") or "contract.pdf"

    headers = {
        "from_addr": "support@onecorpaustralia.com.au",
        "to_addrs": [solicitor_email] if solicitor_email else [],
        "subject": f"Contract for Review – {purchaser_names_str} – {full_property}".strip(" –"),
        "attachments": [contract_filename],
    }

    required_fields = {
        "full_property": full_property,
        "purchaser_names": purchaser_names_str,
        "contract_filename": contract_filename,
    }

    deterministic_body = _deterministic_body_contract_to_solicitor(
        solicitor_name, purchaser_names_str, full_property
    )
    return _build_email_with_llm(
        "CONTRACT_TO_SOLICITOR",
        headers,
        required_fields,
        deterministic_body,
        context={**context, "full_property": full_property, "purchaser_names": purchaser_names_str},
        use_llm=use_llm,
    )


def build_vendor_release_email(
    context: Dict[str, Any],
    use_llm: bool = True,
) -> GeneratedEmail:
    """Build vendor DocuSign release request email."""
    fields = context.get("fields", context)
    property_fields = fields.get("property", {}) if isinstance(fields, dict) else {}

    lot_number = property_fields.get("lot_number")
    address = property_fields.get("address")
    full_property = " ".join([p for p in [f"Lot {lot_number}" if lot_number else None, address] if p]).strip()

    purchaser_names = context.get("purchaser_names") or fields.get("purchaser_names") or context.get("purchasers")
    if isinstance(purchaser_names, list):
        purchaser_names_str = " & ".join(purchaser_names)
    else:
        purchaser_names_str = str(purchaser_names or "").strip()

    vendor_email = context.get("vendor_email") or context.get("to_vendor_email")
    vendor_contact_name = context.get("vendor_contact_name")

    headers = {
        "from_addr": "support@onecorpaustralia.com.au",
        "to_addrs": [vendor_email] if vendor_email else [],
        "subject": f"RE: Contract Request: {full_property}".strip(),
    }

    required_fields = {
        "full_property": full_property,
        "purchaser_names": purchaser_names_str,
        "solicitor_approved_statement": "solicitor has approved",
        "docusign_request": "DocuSign",
    }

    deterministic_body = _deterministic_body_vendor_release(
        vendor_contact_name, purchaser_names_str, full_property
    )
    return _build_email_with_llm(
        "VENDOR_RELEASE_REQUEST",
        headers,
        required_fields,
        deterministic_body,
        context={**context, "full_property": full_property, "purchaser_names": purchaser_names_str},
        use_llm=use_llm,
    )


def build_discrepancy_alert_email(
    context: Dict[str, Any],
    comparison_result: ComparisonResult | Dict[str, Any],
    use_llm: bool = True,
) -> GeneratedEmail:
    """Build internal discrepancy alert email."""
    comparison = _coerce_comparison_result(comparison_result)
    fields = context.get("fields", context)
    property_fields = fields.get("property", {}) if isinstance(fields, dict) else {}

    lot_number = property_fields.get("lot_number")
    address = property_fields.get("address")
    full_property = " ".join([p for p in [f"Lot {lot_number}" if lot_number else None, address] if p]).strip()

    contract_filename = comparison.source_file or context.get("contract_filename") or "contract.pdf"

    headers = {
        "from_addr": "system@onecorpaustralia.com.au",
        "to_addrs": ["support@onecorpaustralia.com.au"],
        "subject": f"Discrepancy Alert – {full_property}".strip(),
    }

    mismatch_requirements: Dict[str, str] = {}
    for i, m in enumerate(comparison.mismatches, start=1):
        mismatch_requirements[f"mismatch_{i}"] = (
            f"{m.field_display}: {m.eoi_value_formatted or m.eoi_value} vs {m.contract_value_formatted or m.contract_value}"
        )

    required_fields: Dict[str, str] = {
        "full_property": full_property,
        "contract_filename": contract_filename,
        **mismatch_requirements,
    }
    if comparison.risk_score:
        required_fields["risk_score"] = comparison.risk_score
    if comparison.amendment_recommendation:
        required_fields["amendment_recommendation"] = comparison.amendment_recommendation

    deterministic_body = _deterministic_body_discrepancy_alert(
        full_property,
        contract_filename,
        comparison.mismatches,
        comparison.risk_score,
        comparison.amendment_recommendation,
    )
    return _build_email_with_llm(
        "DISCREPANCY_ALERT",
        headers,
        required_fields,
        deterministic_body,
        context={
            **context,
            "full_property": full_property,
            "contract_filename": contract_filename,
            "mismatches": [m.to_dict() for m in comparison.mismatches],
            "risk_score": comparison.risk_score,
            "amendment_recommendation": comparison.amendment_recommendation,
        },
        use_llm=use_llm,
    )


def build_sla_overdue_alert_email(
    context: Dict[str, Any],
    use_llm: bool = True,
) -> GeneratedEmail:
    """Build internal SLA overdue alert email."""
    fields = context.get("fields", context)
    property_fields = fields.get("property", {}) if isinstance(fields, dict) else {}
    solicitor = fields.get("solicitor", {}) if isinstance(fields, dict) else {}

    lot_number = property_fields.get("lot_number")
    address = property_fields.get("address")
    full_property = " ".join([p for p in [f"Lot {lot_number}" if lot_number else None, address] if p]).strip()

    purchaser_names = context.get("purchaser_names") or fields.get("purchaser_names") or context.get("purchasers")
    if isinstance(purchaser_names, list):
        purchaser_names_str = " & ".join(purchaser_names)
    else:
        purchaser_names_str = str(purchaser_names or "").strip()

    solicitor_name = solicitor.get("contact_name") or solicitor.get("firm_name") or context.get("solicitor_name")
    solicitor_email = solicitor.get("email") or context.get("solicitor_email")

    signing_datetime = str(context.get("signing_datetime") or context.get("appointment_datetime") or context.get("appointment_phrase") or "")
    sla_deadline = str(context.get("sla_deadline") or "")
    time_overdue = str(context.get("time_overdue") or "")

    headers = {
        "from_addr": "system@onecorpaustralia.com.au",
        "to_addrs": ["support@onecorpaustralia.com.au"],
        "subject": f"SLA Overdue – Buyer Signature Required – {full_property}".strip(),
    }

    required_fields = {
        "full_property": full_property,
        "purchaser_names": purchaser_names_str,
        "signing_datetime": signing_datetime,
        "sla_deadline": sla_deadline,
        "time_overdue": time_overdue,
        "recommended_action_header": "Recommended action",
    }
    if solicitor_name:
        required_fields["solicitor_name"] = solicitor_name
    if solicitor_email:
        required_fields["solicitor_email"] = solicitor_email

    deterministic_body = _deterministic_body_sla_overdue(
        full_property,
        purchaser_names_str,
        solicitor_name,
        solicitor_email,
        signing_datetime,
        sla_deadline,
        time_overdue,
        context.get("recommended_actions"),
    )
    return _build_email_with_llm(
        "SLA_OVERDUE_ALERT",
        headers,
        required_fields,
        deterministic_body,
        context={**context, "full_property": full_property, "purchaser_names": purchaser_names_str},
        use_llm=use_llm,
    )
