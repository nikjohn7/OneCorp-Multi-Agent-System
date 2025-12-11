"""
Email Parser Utilities

This module provides utilities to parse raw email .txt files into structured Python objects.
The parser extracts headers (From, To, Cc, Subject), body, and attachments using pattern-based logic.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass
class ParsedEmail:
    """
    Structured representation of a parsed email.

    Attributes:
        file_path: Path to the original email file
        from_addr: Sender email address
        to_addrs: List of recipient email addresses
        cc_addrs: List of CC email addresses
        subject: Email subject line
        body: Email body content (excluding headers)
        attachment_filenames: List of attachment filenames mentioned in the email
    """
    file_path: str
    from_addr: str
    to_addrs: List[str]
    cc_addrs: List[str]
    subject: str
    body: str
    attachment_filenames: List[str] = field(default_factory=list)


def parse_email_file(file_path: Path | str) -> ParsedEmail:
    """
    Parse a raw email .txt file into a structured ParsedEmail object.

    The parser expects emails to follow this format:
    - Headers: From, To, Cc (optional), Subject
    - Blank line separator
    - Body: Optional "Body:" label followed by content
    - Attachments: Lines starting with "Attachment:" or "Attachments:"

    Args:
        file_path: Path to the email .txt file

    Returns:
        ParsedEmail object with extracted fields

    Raises:
        FileNotFoundError: If the file does not exist
        ValueError: If required headers are missing
    """
    file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError(f"Email file not found: {file_path}")

    content = file_path.read_text(encoding='utf-8')

    # Initialize parsed fields
    from_addr = ""
    to_addrs: List[str] = []
    cc_addrs: List[str] = []
    subject = ""
    body = ""
    attachment_filenames: List[str] = []

    # Split into lines for parsing
    lines = content.split('\n')

    # Track parsing state
    in_body = False
    body_lines = []

    for line in lines:
        stripped = line.strip()

        # Parse From header
        if line.startswith('From:'):
            from_addr = line[5:].strip()
            continue

        # Parse To header
        if line.startswith('To:'):
            to_line = line[3:].strip()
            to_addrs = _parse_email_list(to_line)
            continue

        # Parse Cc header (optional)
        if line.startswith('Cc:') or line.startswith('CC:'):
            cc_line = line[3:].strip()
            cc_addrs = _parse_email_list(cc_line)
            continue

        # Parse Subject header
        if line.startswith('Subject:'):
            subject = line[8:].strip()
            continue

        # Parse attachment lines
        if re.match(r'^Attachments?:', stripped, re.IGNORECASE):
            attachment_text = re.sub(r'^Attachments?:\s*', '', stripped, flags=re.IGNORECASE)
            if attachment_text:
                # Handle comma-separated attachments
                attachments = [a.strip() for a in attachment_text.split(',')]
                attachment_filenames.extend(attachments)
            continue

        # Detect body start (blank line after headers or explicit "Body:" label)
        if not in_body:
            if stripped == '':
                in_body = True
                continue
            if stripped.lower() == 'body:':
                in_body = True
                continue

        # Collect body lines
        if in_body:
            # Skip the "Body:" label if it appears on its own line
            if stripped.lower() == 'body:':
                continue
            body_lines.append(line)

    # Join body lines, removing leading/trailing blank lines
    body = '\n'.join(body_lines).strip()

    # Extract attachments mentioned in the body if not already found in headers
    if not attachment_filenames:
        attachment_filenames = _extract_attachments_from_body(body)

    # Validate required fields
    if not from_addr:
        raise ValueError(f"Missing 'From:' header in {file_path}")
    if not to_addrs:
        raise ValueError(f"Missing 'To:' header in {file_path}")
    if not subject:
        raise ValueError(f"Missing 'Subject:' header in {file_path}")

    return ParsedEmail(
        file_path=str(file_path),
        from_addr=from_addr,
        to_addrs=to_addrs,
        cc_addrs=cc_addrs,
        subject=subject,
        body=body,
        attachment_filenames=attachment_filenames
    )


def _parse_email_list(email_str: str) -> List[str]:
    """
    Parse a comma-separated, semicolon-separated, or bracketed list of email addresses.

    Handles formats like:
    - "email@example.com"
    - "email1@example.com, email2@example.com"
    - "email1@example.com; email2@example.com"
    - "[email1@example.com, email2@example.com]"

    Args:
        email_str: String containing one or more email addresses

    Returns:
        List of email addresses (strings)
    """
    # Remove brackets if present
    email_str = email_str.strip()
    email_str = re.sub(r'^\[|\]$', '', email_str)

    # Split by comma or semicolon and clean up
    # First try semicolon, then comma
    if ';' in email_str:
        emails = [e.strip() for e in email_str.split(';')]
    else:
        emails = [e.strip() for e in email_str.split(',')]

    # Filter out empty strings
    emails = [e for e in emails if e]

    return emails


def _extract_attachments_from_body(body: str) -> List[str]:
    """
    Extract attachment filenames mentioned in the email body.

    Looks for patterns like:
    - "Attachment: filename.pdf"
    - "Attachments: file1.pdf, file2.doc"

    Args:
        body: Email body text

    Returns:
        List of attachment filenames
    """
    attachments = []

    # Pattern: "Attachment:" or "Attachments:" followed by filename(s)
    pattern = r'(?:^|\n)Attachments?:\s*(.+?)(?:\n|$)'
    matches = re.finditer(pattern, body, re.IGNORECASE | re.MULTILINE)

    for match in matches:
        attachment_text = match.group(1).strip()
        # Handle comma-separated attachments
        files = [f.strip() for f in attachment_text.split(',')]
        attachments.extend(files)

    return attachments


def parse_emails_from_directory(directory: Path | str, pattern: str = "*.txt") -> List[ParsedEmail]:
    """
    Parse all email files in a directory matching the given pattern.

    Args:
        directory: Path to directory containing email files
        pattern: Glob pattern for matching email files (default: "*.txt")

    Returns:
        List of ParsedEmail objects

    Raises:
        FileNotFoundError: If directory does not exist
    """
    directory = Path(directory)

    if not directory.exists():
        raise FileNotFoundError(f"Directory not found: {directory}")

    if not directory.is_dir():
        raise ValueError(f"Path is not a directory: {directory}")

    email_files = sorted(directory.glob(pattern))
    parsed_emails = []

    for email_file in email_files:
        try:
            parsed_email = parse_email_file(email_file)
            parsed_emails.append(parsed_email)
        except Exception as e:
            # Log warning but continue parsing other files
            print(f"Warning: Failed to parse {email_file}: {e}")

    return parsed_emails
