"""
Shared pytest fixtures for OneCorp MAS testing.

This module provides reusable fixtures that load ground truth data and test data
from JSON files. These fixtures are used across all test modules to ensure
consistent test data access.
"""

import json
from pathlib import Path
from typing import Any, Dict

import pytest


# Path to the project root (parent of tests/)
PROJECT_ROOT = Path(__file__).parent.parent


@pytest.fixture
def eoi_extracted() -> Dict[str, Any]:
    """
    Load the expected EOI extraction ground truth.

    Returns:
        Dict containing the expected field values when Extractor processes
        the demo EOI PDF.
    """
    ground_truth_path = PROJECT_ROOT / "ground-truth" / "eoi_extracted.json"
    with open(ground_truth_path, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def v1_extracted() -> Dict[str, Any]:
    """
    Load the expected V1 contract extraction ground truth.

    Returns:
        Dict containing the expected field values when Extractor processes
        the demo V1 contract PDF.
    """
    ground_truth_path = PROJECT_ROOT / "ground-truth" / "v1_extracted.json"
    with open(ground_truth_path, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def v2_extracted() -> Dict[str, Any]:
    """
    Load the expected V2 contract extraction ground truth.

    Returns:
        Dict containing the expected field values when Extractor processes
        the demo V2 contract PDF.
    """
    ground_truth_path = PROJECT_ROOT / "ground-truth" / "v2_extracted.json"
    with open(ground_truth_path, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def v1_mismatches() -> Dict[str, Any]:
    """
    Load the expected V1 contract mismatches ground truth.

    Returns:
        Dict containing the expected mismatches when Auditor compares
        the demo V1 contract to the EOI.
    """
    ground_truth_path = PROJECT_ROOT / "ground-truth" / "v1_mismatches.json"
    with open(ground_truth_path, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def expected_outputs() -> Dict[str, Any]:
    """
    Load the expected workflow outputs ground truth.

    Returns:
        Dict containing the expected emails and states at each workflow step.
    """
    ground_truth_path = PROJECT_ROOT / "ground-truth" / "expected_outputs.json"
    with open(ground_truth_path, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def emails_manifest() -> Dict[str, Any]:
    """
    Load the email manifest describing all demo emails.

    Returns:
        Dict containing metadata for all emails in the demo dataset,
        including timestamps, senders, recipients, and expected event types.
    """
    manifest_path = PROJECT_ROOT / "data" / "emails_manifest.json"
    with open(manifest_path, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def eoi_pdf_path() -> Path:
    """
    Get the path to the EOI PDF file.

    Returns:
        Path to the demo EOI PDF.
    """
    return PROJECT_ROOT / "data" / "source-of-truth" / "EOI_John_JaneSmith.pdf"


@pytest.fixture
def contract_v1_pdf_path() -> Path:
    """
    Get the path to the V1 contract PDF file.

    Returns:
        Path to the demo V1 contract PDF.
    """
    return PROJECT_ROOT / "data" / "contracts" / "CONTRACT_V1.pdf"


@pytest.fixture
def contract_v2_pdf_path() -> Path:
    """
    Get the path to the V2 contract PDF file.

    Returns:
        Path to the demo V2 contract PDF.
    """
    return PROJECT_ROOT / "data" / "contracts" / "CONTRACT_V2.pdf"


@pytest.fixture
def incoming_emails_dir() -> Path:
    """
    Get the path to the incoming emails directory.

    Returns:
        Path to the directory containing demo incoming email files.
    """
    return PROJECT_ROOT / "data" / "emails" / "incoming"


@pytest.fixture
def email_templates_dir() -> Path:
    """
    Get the path to the email templates directory.

    Returns:
        Path to the directory containing reference email templates.
    """
    return PROJECT_ROOT / "data" / "emails" / "templates"
