"""Field extraction agent for EOI and contract documents.

This module uses the DeepSeek V3.2 LLM via DeepInfra to extract structured
field data from property documents using pattern-based extraction logic.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Union, Dict, Any, Optional

from dotenv import load_dotenv
from openai import OpenAI

from src.utils.pdf_parser import read_pdf_text


# Load environment variables from .env file
load_dotenv()

# API Configuration
DEEPINFRA_API_KEY = os.getenv("DEEPINFRA_API_KEY")
DEEPINFRA_BASE_URL = "https://api.deepinfra.com/v1/openai"
DEEPSEEK_MODEL = "deepseek-ai/DeepSeek-V3.2"
MAX_TOKENS = 24000


class ExtractionError(Exception):
    """Exception raised when extraction fails."""
    pass


def load_extractor_prompt() -> str:
    """Load the extractor system prompt from the prompts directory.

    Returns:
        System prompt content as string

    Raises:
        FileNotFoundError: If prompt file doesn't exist
    """
    prompt_path = Path(__file__).parent / "prompts" / "extractor_prompt.md"

    if not prompt_path.exists():
        raise FileNotFoundError(f"Extractor prompt not found: {prompt_path}")

    return prompt_path.read_text(encoding="utf-8")


def call_extraction_llm(
    document_text: str,
    document_type: str,
    source_filename: str,
    system_prompt: str
) -> Dict[str, Any]:
    """Call DeepSeek V3.2 LLM to extract fields from document text.

    Args:
        document_text: Plain text extracted from PDF
        document_type: "EOI" or "CONTRACT" or "UNKNOWN"
        source_filename: Original PDF filename
        system_prompt: Extraction instructions from extractor_prompt.md

    Returns:
        Parsed JSON response from the LLM

    Raises:
        ExtractionError: If API call fails or response is invalid
    """
    if not DEEPINFRA_API_KEY:
        raise ExtractionError(
            "DEEPINFRA_API_KEY environment variable not set. "
            "Please set it to use the extraction agent."
        )

    # Create OpenAI client configured for DeepInfra
    client = OpenAI(
        api_key=DEEPINFRA_API_KEY,
        base_url=DEEPINFRA_BASE_URL,
    )

    # Construct user message with document context
    user_message = f"""Please extract structured fields from the following document.

**Document Type**: {document_type}
**Source Filename**: {source_filename}

**Document Text**:
{document_text}

Return a valid JSON object matching the schema specified in the system prompt.
"""

    try:
        # Call LLM
        response = client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            max_tokens=MAX_TOKENS,
            temperature=0.1,  # Low temperature for deterministic extraction
        )

        # Extract response content
        content = response.choices[0].message.content

        if not content:
            raise ExtractionError("LLM returned empty response")

        # Parse JSON response
        try:
            # Try to find JSON in the response (handle markdown code blocks)
            if "```json" in content:
                # Extract JSON from markdown code block
                json_start = content.find("```json") + 7
                json_end = content.find("```", json_start)
                content = content[json_start:json_end].strip()
            elif "```" in content:
                # Generic code block
                json_start = content.find("```") + 3
                json_end = content.find("```", json_start)
                content = content[json_start:json_end].strip()

            extracted_data = json.loads(content)
            return extracted_data

        except json.JSONDecodeError as e:
            raise ExtractionError(f"Failed to parse LLM response as JSON: {e}\nResponse: {content}")

    except Exception as e:
        if isinstance(e, ExtractionError):
            raise
        raise ExtractionError(f"LLM API call failed: {str(e)}") from e


def extract_eoi(pdf_path: Union[str, Path]) -> Dict[str, Any]:
    """Extract structured fields from an EOI (Expression of Interest) PDF.

    This function:
    1. Extracts text from the PDF using pdfplumber
    2. Sends the text to DeepSeek V3.2 LLM with extraction instructions
    3. Returns structured data matching the EOI schema

    Args:
        pdf_path: Path to the EOI PDF file (str or Path object)

    Returns:
        Dictionary with structure matching ground-truth/eoi_extracted.json:
        {
            "document_type": "EOI",
            "version": null,
            "source_file": "filename.pdf",
            "extracted_at": "ISO timestamp",
            "fields": {
                "purchaser_1": {...},
                "purchaser_2": {...},
                "residential_address": "...",
                "property": {...},
                "pricing": {...},
                "finance": {...},
                "solicitor": {...},
                "deposits": {...},
                "introducer": {...}
            },
            "confidence_scores": {...},
            "extraction_notes": [...]
        }

    Raises:
        FileNotFoundError: If PDF file doesn't exist
        ExtractionError: If extraction fails

    Examples:
        >>> data = extract_eoi("data/source-of-truth/EOI_John_JaneSmith.pdf")
        >>> data["document_type"]
        'EOI'
        >>> data["fields"]["property"]["lot_number"]
        '95'
    """
    pdf_path = Path(pdf_path)

    # Extract text from PDF
    try:
        document_text = read_pdf_text(pdf_path)
    except Exception as e:
        raise ExtractionError(f"Failed to read PDF: {str(e)}") from e

    # Load system prompt
    try:
        system_prompt = load_extractor_prompt()
    except Exception as e:
        raise ExtractionError(f"Failed to load extractor prompt: {str(e)}") from e

    # Call LLM for extraction
    extracted_data = call_extraction_llm(
        document_text=document_text,
        document_type="EOI",
        source_filename=pdf_path.name,
        system_prompt=system_prompt
    )

    # Validate response structure
    if "fields" not in extracted_data:
        raise ExtractionError("LLM response missing 'fields' key")

    # Ensure extracted_at timestamp is present
    if not extracted_data.get("extracted_at"):
        extracted_data["extracted_at"] = datetime.now(timezone.utc).isoformat()

    # Ensure document_type is EOI
    extracted_data["document_type"] = "EOI"

    # Ensure source_file is set
    extracted_data["source_file"] = pdf_path.name

    # Ensure version is null for EOI
    extracted_data["version"] = None

    return extracted_data


def extract_contract(pdf_path: Union[str, Path]) -> Dict[str, Any]:
    """Extract structured fields from a Contract of Sale PDF.

    This function:
    1. Extracts text from the PDF using pdfplumber
    2. Sends the text to DeepSeek V3.2 LLM with extraction instructions
    3. Returns structured data matching the CONTRACT schema

    Args:
        pdf_path: Path to the contract PDF file (str or Path object)

    Returns:
        Dictionary with structure matching ground-truth/v1_extracted.json or v2_extracted.json:
        {
            "document_type": "CONTRACT",
            "version": "V1" | "V2" | null,
            "source_file": "filename.pdf",
            "extracted_at": "ISO timestamp",
            "fields": {
                "purchaser_1": {...},
                "purchaser_2": {...},
                "property": {...},
                "pricing": {...},
                "finance": {...},
                "solicitor": {...},
                "deposits": {...},
                "vendor": {...}
            },
            "confidence_scores": {...},
            "extraction_notes": [...]
        }

    Raises:
        FileNotFoundError: If PDF file doesn't exist
        ExtractionError: If extraction fails

    Examples:
        >>> data = extract_contract("data/contracts/CONTRACT_V1.pdf")
        >>> data["document_type"]
        'CONTRACT'
        >>> data["version"]
        'V1'
    """
    pdf_path = Path(pdf_path)

    # Extract text from PDF
    try:
        document_text = read_pdf_text(pdf_path)
    except Exception as e:
        raise ExtractionError(f"Failed to read PDF: {str(e)}") from e

    # Load system prompt
    try:
        system_prompt = load_extractor_prompt()
    except Exception as e:
        raise ExtractionError(f"Failed to load extractor prompt: {str(e)}") from e

    # Call LLM for extraction
    extracted_data = call_extraction_llm(
        document_text=document_text,
        document_type="CONTRACT",
        source_filename=pdf_path.name,
        system_prompt=system_prompt
    )

    # Validate response structure
    if "fields" not in extracted_data:
        raise ExtractionError("LLM response missing 'fields' key")

    # Ensure extracted_at timestamp is present
    if not extracted_data.get("extracted_at"):
        extracted_data["extracted_at"] = datetime.now(timezone.utc).isoformat()

    # Ensure document_type is CONTRACT
    extracted_data["document_type"] = "CONTRACT"

    # Ensure source_file is set
    extracted_data["source_file"] = pdf_path.name

    return extracted_data
