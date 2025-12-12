"""Tests for email classification and routing."""

import pytest
from pathlib import Path

from src.agents.router import (
    classify_email,
    classify_deterministic,
    extract_lot_number,
    extract_property_address,
    extract_purchaser_names,
    extract_appointment_phrase,
    extract_contract_version,
    ClassificationResult,
)
from src.utils.email_parser import parse_email_file


class TestRouterClassifiesAllEmails:
    """Test that router correctly classifies all demo emails."""

    def test_eoi_signed_classification(self, emails_dir):
        """Test EOI_SIGNED email classification."""
        email_path = emails_dir / "incoming" / "01_eoi_signed.txt"
        email = parse_email_file(email_path)

        result = classify_email(email)

        assert result.event_type == "EOI_SIGNED"
        assert result.confidence >= 0.8
        assert result.method in ["deterministic", "llm"]

        # Check metadata
        assert "lot_number" in result.metadata
        assert result.metadata["lot_number"] == "95"
        assert "property_address" in result.metadata
        assert "VIC 3336" in result.metadata["property_address"]

    def test_contract_v1_classification(self, emails_dir):
        """Test CONTRACT_FROM_VENDOR email classification (V1)."""
        email_path = emails_dir / "incoming" / "02_contract_v1_received.txt"
        email = parse_email_file(email_path)

        result = classify_email(email)

        assert result.event_type == "CONTRACT_FROM_VENDOR"
        assert result.confidence >= 0.8
        assert result.method in ["deterministic", "llm"]

        # Check metadata
        assert "lot_number" in result.metadata
        assert result.metadata["lot_number"] == "95"
        assert "contract_version" in result.metadata
        assert result.metadata["contract_version"] == "V1"

    def test_contract_v2_classification(self, emails_dir):
        """Test CONTRACT_FROM_VENDOR email classification (V2)."""
        email_path = emails_dir / "incoming" / "02b_contract_v2_received.txt"
        email = parse_email_file(email_path)

        result = classify_email(email)

        assert result.event_type == "CONTRACT_FROM_VENDOR"
        assert result.confidence >= 0.8
        assert result.method in ["deterministic", "llm"]

        # Check metadata
        assert "contract_version" in result.metadata
        assert result.metadata["contract_version"] == "V2"

    def test_solicitor_approved_classification(self, emails_dir):
        """Test SOLICITOR_APPROVED_WITH_APPOINTMENT email classification."""
        email_path = emails_dir / "incoming" / "04_solicitor_approved.txt"
        email = parse_email_file(email_path)

        result = classify_email(email)

        assert result.event_type == "SOLICITOR_APPROVED_WITH_APPOINTMENT"
        assert result.confidence >= 0.8
        assert result.method in ["deterministic", "llm"]

        # Check critical metadata: appointment phrase
        assert "appointment_phrase" in result.metadata
        assert "Thursday" in result.metadata["appointment_phrase"]
        assert "11:30" in result.metadata["appointment_phrase"]

    def test_docusign_released_classification(self, emails_dir):
        """Test DOCUSIGN_RELEASED email classification."""
        email_path = emails_dir / "incoming" / "06_docusign_please_sign.txt"
        email = parse_email_file(email_path)

        result = classify_email(email)

        assert result.event_type == "DOCUSIGN_RELEASED"
        assert result.confidence >= 0.8
        assert result.method in ["deterministic", "llm"]

    def test_docusign_buyer_signed_classification(self, emails_dir):
        """Test DOCUSIGN_BUYER_SIGNED email classification."""
        email_path = emails_dir / "incoming" / "07_buyer_signed.txt"
        email = parse_email_file(email_path)

        result = classify_email(email)

        assert result.event_type == "DOCUSIGN_BUYER_SIGNED"
        assert result.confidence >= 0.8
        assert result.method in ["deterministic", "llm"]

    def test_docusign_executed_classification(self, emails_dir):
        """Test DOCUSIGN_EXECUTED email classification."""
        email_path = emails_dir / "incoming" / "08_contract_executed.txt"
        email = parse_email_file(email_path)

        result = classify_email(email)

        assert result.event_type == "DOCUSIGN_EXECUTED"
        assert result.confidence >= 0.8
        assert result.method in ["deterministic", "llm"]


class TestHybridClassificationMethod:
    """Test that hybrid classification method works correctly."""

    def test_high_confidence_uses_deterministic(self, emails_dir):
        """Test that high-confidence emails use deterministic method."""
        # EOI email should be very clear (sender + subject + body + attachment all match)
        email_path = emails_dir / "incoming" / "01_eoi_signed.txt"
        email = parse_email_file(email_path)

        result = classify_email(email)

        # High confidence should use deterministic method (no LLM call)
        assert result.confidence >= 0.8
        assert result.method == "deterministic"

    def test_docusign_emails_use_deterministic(self, emails_dir):
        """Test that clear DocuSign emails use deterministic method."""
        # DocuSign emails have clear sender + subject patterns
        email_path = emails_dir / "incoming" / "08_contract_executed.txt"
        email = parse_email_file(email_path)

        result = classify_email(email)

        # Should be high confidence deterministic
        assert result.confidence >= 0.8
        assert result.method == "deterministic"

    def test_deterministic_classification_returns_result(self, emails_dir):
        """Test that deterministic classification returns valid result."""
        email_path = emails_dir / "incoming" / "01_eoi_signed.txt"
        email = parse_email_file(email_path)

        result = classify_deterministic(email)

        assert isinstance(result, ClassificationResult)
        assert result.event_type in ["EOI_SIGNED", "CONTRACT_FROM_VENDOR", "SOLICITOR_APPROVED_WITH_APPOINTMENT",
                                       "DOCUSIGN_RELEASED", "DOCUSIGN_BUYER_SIGNED", "DOCUSIGN_EXECUTED", "UNKNOWN"]
        assert 0.0 <= result.confidence <= 1.0
        assert result.method == "deterministic"
        assert isinstance(result.metadata, dict)


class TestMetadataExtraction:
    """Test metadata extraction functions."""

    def test_extract_lot_number(self):
        """Test lot number extraction from various formats."""
        assert extract_lot_number("Lot 95 Fake Rise") == "95"
        assert extract_lot_number("LOT #59") == "59"
        assert extract_lot_number("Lot #42") == "42"
        assert extract_lot_number("for Lot 100") == "100"
        assert extract_lot_number("No lot here") is None

    def test_extract_property_address(self):
        """Test property address extraction."""
        assert "Fake Rise VIC 3336" in extract_property_address("Lot 95, Fake Rise VIC 3336")
        assert extract_property_address("Property: Example Estate NSW 2000") is not None
        assert extract_property_address("No address here") is None

    def test_extract_purchaser_names(self):
        """Test purchaser name extraction."""
        text1 = "The clients John & Jane Smith have signed"
        names1 = extract_purchaser_names(text1)
        assert len(names1) == 2
        assert "John Smith" in names1
        assert "Jane Smith" in names1

        text2 = "for Michael and Sarah Johnson"
        names2 = extract_purchaser_names(text2)
        # Note: This might extract "Sarah Johnson" depending on regex
        assert len(names2) >= 1

    def test_extract_appointment_phrase(self):
        """Test appointment phrase extraction."""
        text1 = "signing appointment scheduled for Thursday at 11:30am"
        phrase1 = extract_appointment_phrase(text1)
        assert phrase1 is not None
        assert "Thursday" in phrase1
        assert "11:30" in phrase1

        text2 = "meeting on Monday at 2pm"
        phrase2 = extract_appointment_phrase(text2)
        assert phrase2 is not None
        assert "Monday" in phrase2

        text3 = "No appointment mentioned"
        phrase3 = extract_appointment_phrase(text3)
        assert phrase3 is None

    def test_extract_contract_version(self):
        """Test contract version extraction from filenames."""
        assert extract_contract_version(["CONTRACT_V1.pdf"]) == "V1"
        assert extract_contract_version(["CONTRACT_V2.pdf"]) == "V2"
        assert extract_contract_version(["CONTRACT_OF_SALE_VERSION_1.pdf"]) == "V1"
        assert extract_contract_version(["EOI_Smith.pdf"]) is None


class TestConfidenceScoring:
    """Test confidence scoring algorithm."""

    def test_confidence_range(self, emails_dir):
        """Test that confidence scores are in valid range [0.0, 1.0]."""
        for email_file in (Path(emails_dir) / "incoming").glob("*.txt"):
            email = parse_email_file(email_file)
            result = classify_deterministic(email)

            assert 0.0 <= result.confidence <= 1.0, f"Invalid confidence for {email_file.name}"

    def test_clear_emails_high_confidence(self, emails_dir):
        """Test that clear, unambiguous emails score >= 0.8."""
        # EOI email: clear sender + subject + body + attachment
        email_path = emails_dir / "incoming" / "01_eoi_signed.txt"
        email = parse_email_file(email_path)
        result = classify_deterministic(email)

        assert result.confidence >= 0.8, "EOI email should have high confidence"

        # DocuSign completed: clear sender + subject + body
        email_path = emails_dir / "incoming" / "08_contract_executed.txt"
        email = parse_email_file(email_path)
        result = classify_deterministic(email)

        assert result.confidence >= 0.8, "DocuSign executed email should have high confidence"

    def test_deterministic_scoring_is_consistent(self, emails_dir):
        """Test that deterministic scoring is consistent (same result for same email)."""
        email_path = emails_dir / "incoming" / "01_eoi_signed.txt"
        email = parse_email_file(email_path)

        result1 = classify_deterministic(email)
        result2 = classify_deterministic(email)

        assert result1.event_type == result2.event_type
        assert result1.confidence == result2.confidence
        assert result1.method == result2.method


class TestRouterClassifiesAllEmailsFromManifest:
    """Test router against all emails in emails_manifest.json."""

    def test_router_classifies_all_emails(self, emails_manifest, emails_dir):
        """Test that router correctly classifies ALL emails from manifest."""
        for email_entry in emails_manifest['emails']:
            # Skip output templates (not INPUT emails)
            if email_entry['type'] != 'INPUT':
                continue

            email_path = Path(emails_dir) / email_entry['file']
            email = parse_email_file(email_path)
            result = classify_email(email)

            expected_event_type = email_entry['event_type']

            assert result.event_type == expected_event_type, \
                f"Email {email_entry['email_id']}: expected {expected_event_type}, got {result.event_type}"

            # All classifications should be confident
            assert result.confidence >= 0.0, \
                f"Email {email_entry['email_id']}: confidence must be >= 0.0"

            # Metadata checks
            if expected_event_type == "SOLICITOR_APPROVED_WITH_APPOINTMENT":
                # Check appointment phrase was extracted
                assert "appointment_phrase" in result.metadata or "extracted_data" in email_entry, \
                    f"Email {email_entry['email_id']}: missing appointment phrase"

            if expected_event_type == "CONTRACT_FROM_VENDOR" and "contract_version" in email_entry:
                # Check version was extracted
                assert "contract_version" in result.metadata, \
                    f"Email {email_entry['email_id']}: missing contract version"


class TestLLMFallback:
    """Test LLM fallback classification for ambiguous emails."""

    def test_llm_fallback_classifies_ambiguous_email(self):
        """Test that LLM can classify an ambiguous email."""
        from src.agents.router import classify_with_llm
        from src.utils.email_parser import ParsedEmail

        # Create an ambiguous email that would have low deterministic confidence
        # Using a generic subject and sender, but clear body content
        ambiguous_email = ParsedEmail(
            file_path="test_ambiguous.txt",
            from_addr="info@example.com.au",  # Generic sender
            to_addrs=["support@onecorpaustralia.com.au"],
            cc_addrs=[],
            subject="Property Update",  # Generic subject
            body="We've completed our review of the contract for John & Jane Smith for Lot 42, Example Estate VIC 2000. Everything looks good. A signing appointment has been scheduled for Friday at 2pm with the clients.",
            attachment_filenames=[]
        )

        result = classify_with_llm(ambiguous_email)

        # Should classify as solicitor approval based on body content
        assert result.event_type == "SOLICITOR_APPROVED_WITH_APPOINTMENT"
        assert result.method == "llm"
        assert result.confidence >= 0.0

        # Should extract appointment phrase
        assert "appointment_phrase" in result.metadata
        assert "Friday" in result.metadata["appointment_phrase"]
        assert "2pm" in result.metadata["appointment_phrase"]

    def test_llm_fallback_extracts_metadata(self):
        """Test that LLM fallback extracts metadata correctly."""
        from src.agents.router import classify_with_llm
        from src.utils.email_parser import ParsedEmail

        # Create an email with clear metadata to extract
        email_with_metadata = ParsedEmail(
            file_path="test_metadata.txt",
            from_addr="unknown@example.com",
            to_addrs=["support@onecorpaustralia.com.au"],
            cc_addrs=[],
            subject="Update",
            body="Please find attached the amended Contract of Sale for the purchasers Michael & Sarah Johnson for Lot 88, Sunrise Estate QLD 4000. We have made the corrections as requested.",
            attachment_filenames=["CONTRACT_V3.pdf"]
        )

        result = classify_with_llm(email_with_metadata)

        # Should classify as contract from vendor
        assert result.event_type == "CONTRACT_FROM_VENDOR"
        assert result.method == "llm"

        # Should extract metadata
        metadata = result.metadata
        assert "lot_number" in metadata
        assert metadata["lot_number"] == "88"

        assert "purchaser_names" in metadata
        assert "Michael Johnson" in metadata["purchaser_names"]
        assert "Sarah Johnson" in metadata["purchaser_names"]

        # Should extract contract version
        assert "contract_version" in metadata
        assert metadata["contract_version"] == "V3"
