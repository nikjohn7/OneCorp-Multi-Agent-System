"""
Tests for utility modules: pdf_parser, email_parser, and date_resolver.

These tests validate the core utility functions using the demo dataset,
ensuring they extract information correctly using pattern-based logic.
"""

import pytest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from src.utils.pdf_parser import (
    read_pdf_text,
    read_pdf_pages,
    extract_tables_from_pdf,
    get_pdf_metadata,
    PDFParseError
)
from src.utils.email_parser import (
    parse_email_file,
    parse_emails_from_directory,
    ParsedEmail
)
from src.utils.date_resolver import (
    resolve_appointment_phrase,
    parse_time_string
)


class TestPDFParser:
    """Test PDF parsing utilities."""

    def test_read_eoi_pdf_returns_nonempty_text(self, eoi_pdf_path):
        """EOI PDF should return non-empty text with expected anchors."""
        text = read_pdf_text(eoi_pdf_path)

        assert len(text) > 0, "PDF text should not be empty"
        assert len(text) > 100, "PDF text should be reasonably long"
        # Check for expected content anchors
        assert "Expression of Interest" in text or "expression of interest" in text.lower()

    def test_read_contract_v1_pdf_returns_nonempty_text(self, contract_v1_pdf_path):
        """Contract V1 PDF should return non-empty text with expected anchors."""
        text = read_pdf_text(contract_v1_pdf_path)

        assert len(text) > 0, "PDF text should not be empty"
        assert len(text) > 100, "PDF text should be reasonably long"
        # Check for expected content anchors
        assert "CONTRACT" in text.upper()

    def test_read_contract_v2_pdf_returns_nonempty_text(self, contract_v2_pdf_path):
        """Contract V2 PDF should return non-empty text with expected anchors."""
        text = read_pdf_text(contract_v2_pdf_path)

        assert len(text) > 0, "PDF text should not be empty"
        assert len(text) > 100, "PDF text should be reasonably long"
        # Check for expected content anchors
        assert "CONTRACT" in text.upper()

    def test_read_pdf_pages_returns_list(self, eoi_pdf_path):
        """read_pdf_pages should return a list of page strings."""
        pages = read_pdf_pages(eoi_pdf_path)

        assert isinstance(pages, list), "Should return a list"
        assert len(pages) >= 1, "Should have at least one page"
        assert all(isinstance(page, str) for page in pages), "All pages should be strings"

    def test_read_pdf_text_raises_on_missing_file(self):
        """Should raise FileNotFoundError for non-existent file."""
        with pytest.raises(FileNotFoundError):
            read_pdf_text("/nonexistent/path/to/file.pdf")

    def test_extract_tables_from_pdf_returns_list(self, eoi_pdf_path):
        """extract_tables_from_pdf should return a list (may be empty)."""
        tables = extract_tables_from_pdf(eoi_pdf_path)

        assert isinstance(tables, list), "Should return a list"
        # Tables list may be empty if no tables detected, that's okay

    def test_get_pdf_metadata_returns_dict_with_page_count(self, eoi_pdf_path):
        """get_pdf_metadata should return dict with page_count."""
        metadata = get_pdf_metadata(eoi_pdf_path)

        assert isinstance(metadata, dict), "Should return a dict"
        assert "page_count" in metadata, "Should have page_count key"
        assert isinstance(metadata["page_count"], int), "page_count should be int"
        assert metadata["page_count"] >= 1, "Should have at least 1 page"

    def test_read_pdf_text_handles_path_objects(self, eoi_pdf_path):
        """Should accept both Path objects and strings."""
        # Test with Path object
        text1 = read_pdf_text(eoi_pdf_path)

        # Test with string
        text2 = read_pdf_text(str(eoi_pdf_path))

        assert text1 == text2, "Should produce same output for Path and string"


class TestEmailParser:
    """Test email parsing utilities."""

    def test_parse_all_incoming_emails_without_error(self, incoming_emails_dir):
        """Should parse all incoming emails without raising exceptions."""
        parsed_emails = parse_emails_from_directory(incoming_emails_dir)

        assert len(parsed_emails) > 0, "Should parse at least one email"
        assert all(isinstance(email, ParsedEmail) for email in parsed_emails)

    def test_parsed_emails_match_manifest_count(self, incoming_emails_dir, emails_manifest):
        """Number of parsed emails should match INPUT emails in manifest."""
        parsed_emails = parse_emails_from_directory(incoming_emails_dir)

        # Count INPUT type emails in manifest
        input_emails = [e for e in emails_manifest["emails"] if e["type"] == "INPUT"]

        assert len(parsed_emails) == len(input_emails), \
            f"Expected {len(input_emails)} emails, parsed {len(parsed_emails)}"

    def test_parsed_emails_have_required_fields(self, incoming_emails_dir):
        """All parsed emails should have required fields populated."""
        parsed_emails = parse_emails_from_directory(incoming_emails_dir)

        for email in parsed_emails:
            assert email.from_addr, "from_addr should not be empty"
            assert email.to_addrs, "to_addrs should not be empty"
            assert email.subject, "subject should not be empty"
            assert email.file_path, "file_path should not be empty"
            # body can be empty for some emails, so we don't check it
            # cc_addrs and attachment_filenames are optional

    def test_eoi_signed_email_matches_manifest(self, incoming_emails_dir, emails_manifest):
        """EOI signed email should match manifest metadata."""
        # Find the EOI email in manifest
        eoi_manifest = next(e for e in emails_manifest["emails"] if e["email_id"] == "email_1")

        # Parse the email
        email_path = incoming_emails_dir / "01_eoi_signed.txt"
        parsed_email = parse_email_file(email_path)

        # Verify fields match
        assert parsed_email.from_addr == eoi_manifest["from"]
        assert set(parsed_email.to_addrs) == set(eoi_manifest["to"])
        assert len(parsed_email.attachment_filenames) == len(eoi_manifest["attachments"])

    def test_solicitor_approved_email_matches_manifest(self, incoming_emails_dir, emails_manifest):
        """Solicitor approved email should match manifest metadata."""
        # Find the solicitor email in manifest
        solicitor_manifest = next(e for e in emails_manifest["emails"] if e["email_id"] == "email_4")

        # Parse the email
        email_path = incoming_emails_dir / "04_solicitor_approved.txt"
        parsed_email = parse_email_file(email_path)

        # Verify fields match
        assert parsed_email.from_addr == solicitor_manifest["from"]
        assert set(parsed_email.to_addrs) == set(solicitor_manifest["to"])

    def test_email_with_cc_parses_correctly(self, incoming_emails_dir, emails_manifest):
        """Email with CC field should parse CC addresses correctly."""
        # Find an email with CC in manifest
        cc_email_manifest = next(
            (e for e in emails_manifest["emails"] if "cc" in e and e["type"] == "INPUT"),
            None
        )

        if cc_email_manifest:
            # Parse the email
            email_filename = Path(cc_email_manifest["file"]).name
            email_path = incoming_emails_dir / email_filename
            parsed_email = parse_email_file(email_path)

            # Verify CC addresses match
            assert set(parsed_email.cc_addrs) == set(cc_email_manifest["cc"])

    def test_parse_email_file_raises_on_missing_file(self):
        """Should raise FileNotFoundError for non-existent email file."""
        with pytest.raises(FileNotFoundError):
            parse_email_file("/nonexistent/email.txt")

    def test_email_parser_handles_path_objects(self, incoming_emails_dir):
        """Should accept both Path objects and strings."""
        email_path = incoming_emails_dir / "01_eoi_signed.txt"

        # Test with Path object
        parsed1 = parse_email_file(email_path)

        # Test with string
        parsed2 = parse_email_file(str(email_path))

        assert parsed1.from_addr == parsed2.from_addr
        assert parsed1.subject == parsed2.subject


class TestDateResolver:
    """Test date resolver utilities."""

    def test_resolve_appointment_phrase_from_manifest(self, emails_manifest):
        """
        Should resolve the solicitor appointment phrase to the expected datetime.

        From manifest:
        - email_4 timestamp: 2025-01-14T09:12:00+11:00
        - appointment_phrase: "Thursday at 11:30am"
        - expected appointment_datetime: 2025-01-16T11:30:00+11:00
        """
        # Get manifest data
        solicitor_email = next(
            e for e in emails_manifest["emails"] if e["email_id"] == "email_4"
        )

        # Parse timestamp
        timestamp_str = solicitor_email["timestamp"]
        base_dt = datetime.fromisoformat(timestamp_str)

        # Get appointment phrase
        appointment_phrase = solicitor_email["extracted_data"]["appointment_phrase"]

        # Resolve appointment
        resolved_dt = resolve_appointment_phrase(
            base_dt,
            appointment_phrase,
            "Australia/Melbourne"
        )

        # Expected datetime
        expected_str = solicitor_email["extracted_data"]["appointment_datetime"]
        expected_dt = datetime.fromisoformat(expected_str)

        assert resolved_dt is not None, "Should successfully resolve appointment"
        assert resolved_dt == expected_dt, \
            f"Expected {expected_dt}, got {resolved_dt}"

    def test_resolve_appointment_phrase_thursday_11_30am(self):
        """Should correctly parse 'Thursday at 11:30am' pattern."""
        # Tuesday 2025-01-14 at 9:12am
        base_dt = datetime(2025, 1, 14, 9, 12, tzinfo=ZoneInfo("Australia/Melbourne"))

        resolved = resolve_appointment_phrase(
            base_dt,
            "Thursday at 11:30am",
            "Australia/Melbourne"
        )

        # Should resolve to Thursday 2025-01-16 at 11:30am
        assert resolved is not None
        assert resolved.year == 2025
        assert resolved.month == 1
        assert resolved.day == 16
        assert resolved.hour == 11
        assert resolved.minute == 30
        assert resolved.weekday() == 3  # Thursday

    def test_resolve_appointment_phrase_case_insensitive(self):
        """Should handle case-insensitive weekday names."""
        base_dt = datetime(2025, 1, 14, 9, 12, tzinfo=ZoneInfo("Australia/Melbourne"))

        # Test various cases
        resolved1 = resolve_appointment_phrase(base_dt, "THURSDAY at 11:30am")
        resolved2 = resolve_appointment_phrase(base_dt, "thursday at 11:30am")
        resolved3 = resolve_appointment_phrase(base_dt, "Thursday at 11:30am")

        assert resolved1 == resolved2 == resolved3

    def test_resolve_appointment_phrase_handles_pm(self):
        """Should correctly handle PM times."""
        base_dt = datetime(2025, 1, 14, 9, 12, tzinfo=ZoneInfo("Australia/Melbourne"))

        resolved = resolve_appointment_phrase(base_dt, "Friday at 2:30pm")

        assert resolved is not None
        assert resolved.hour == 14  # 2pm in 24-hour format
        assert resolved.minute == 30

    def test_resolve_appointment_phrase_handles_time_without_minutes(self):
        """Should handle times without minutes (e.g., '9am')."""
        base_dt = datetime(2025, 1, 14, 9, 12, tzinfo=ZoneInfo("Australia/Melbourne"))

        resolved = resolve_appointment_phrase(base_dt, "Friday at 9am")

        assert resolved is not None
        assert resolved.hour == 9
        assert resolved.minute == 0

    def test_resolve_appointment_phrase_returns_none_for_invalid(self):
        """Should return None for phrases that can't be parsed."""
        base_dt = datetime(2025, 1, 14, 9, 12, tzinfo=ZoneInfo("Australia/Melbourne"))

        invalid_phrases = [
            "",
            "tomorrow",
            "next week",
            "invalid text",
            "25:00",  # Invalid hour
        ]

        for phrase in invalid_phrases:
            resolved = resolve_appointment_phrase(base_dt, phrase)
            assert resolved is None, f"Should return None for invalid phrase: {phrase}"

    def test_parse_time_string_11_30am(self):
        """Should parse '11:30am' correctly."""
        time_obj = parse_time_string("11:30am")

        assert time_obj is not None
        assert time_obj.hour == 11
        assert time_obj.minute == 30

    def test_parse_time_string_2pm(self):
        """Should parse '2pm' (without minutes) correctly."""
        time_obj = parse_time_string("2pm")

        assert time_obj is not None
        assert time_obj.hour == 14  # 2pm in 24-hour
        assert time_obj.minute == 0

    def test_parse_time_string_9_00_am_with_space(self):
        """Should parse '9:00 AM' (with space) correctly."""
        time_obj = parse_time_string("9:00 AM")

        assert time_obj is not None
        assert time_obj.hour == 9
        assert time_obj.minute == 0

    def test_parse_time_string_returns_none_for_invalid(self):
        """Should return None for invalid time strings."""
        invalid_times = [
            "",
            "invalid",
            "25:00",
            "99pm",
        ]

        for time_str in invalid_times:
            time_obj = parse_time_string(time_str)
            assert time_obj is None, f"Should return None for invalid time: {time_str}"


class TestIntegration:
    """Integration tests combining multiple utilities."""

    def test_full_email_processing_pipeline(self, incoming_emails_dir, emails_manifest):
        """
        Test full pipeline: parse email -> extract appointment -> resolve datetime.

        This simulates how the Router agent would process the solicitor approval email.
        """
        # Get solicitor email from manifest
        solicitor_manifest = next(
            e for e in emails_manifest["emails"] if e["email_id"] == "email_4"
        )

        # Parse the email file
        email_path = incoming_emails_dir / "04_solicitor_approved.txt"
        parsed_email = parse_email_file(email_path)

        # Verify email was parsed correctly
        assert parsed_email.from_addr == solicitor_manifest["from"]

        # Extract appointment phrase from body (pattern-based)
        # Looking for "Thursday at 11:30am" or similar patterns
        import re
        appointment_pattern = r'\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\s+at\s+\d{1,2}(?:[:\.]?\d{2})?\s*(?:am|pm)?\b'
        match = re.search(appointment_pattern, parsed_email.body, re.IGNORECASE)

        assert match is not None, "Should find appointment phrase in email body"
        appointment_phrase = match.group(0)

        # Resolve the appointment datetime
        email_timestamp = datetime.fromisoformat(solicitor_manifest["timestamp"])
        resolved_dt = resolve_appointment_phrase(
            email_timestamp,
            appointment_phrase,
            "Australia/Melbourne"
        )

        # Verify against manifest expectation
        expected_dt = datetime.fromisoformat(
            solicitor_manifest["extracted_data"]["appointment_datetime"]
        )

        assert resolved_dt == expected_dt, \
            f"Resolved appointment {resolved_dt} doesn't match expected {expected_dt}"

    def test_all_pdfs_readable(self, eoi_pdf_path, contract_v1_pdf_path, contract_v2_pdf_path):
        """Verify all demo PDFs are readable and contain text."""
        pdfs = {
            "EOI": eoi_pdf_path,
            "Contract V1": contract_v1_pdf_path,
            "Contract V2": contract_v2_pdf_path,
        }

        for name, pdf_path in pdfs.items():
            text = read_pdf_text(pdf_path)
            assert len(text) > 0, f"{name} should contain text"
            assert len(text) > 100, f"{name} should have substantial content"

    def test_all_incoming_emails_parseable(self, incoming_emails_dir, emails_manifest):
        """Verify all INPUT emails in manifest are parseable."""
        input_emails = [
            e for e in emails_manifest["emails"] if e["type"] == "INPUT"
        ]

        for email_entry in input_emails:
            email_filename = Path(email_entry["file"]).name
            email_path = incoming_emails_dir / email_filename

            # Should not raise exception
            parsed_email = parse_email_file(email_path)

            # Basic sanity checks
            assert parsed_email.from_addr, f"{email_entry['email_id']} should have from_addr"
            assert parsed_email.to_addrs, f"{email_entry['email_id']} should have to_addrs"
            assert parsed_email.subject, f"{email_entry['email_id']} should have subject"
