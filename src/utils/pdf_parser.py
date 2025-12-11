"""PDF parsing utilities for extracting text and tables from PDF documents.

This module provides generalizable functions for reading PDF content,
supporting both EOI and contract documents without hardcoded values.
"""

from pathlib import Path
from typing import Union, List
import pdfplumber


class PDFParseError(Exception):
    """Exception raised when PDF parsing fails."""
    pass


def read_pdf_text(path: Union[Path, str]) -> str:
    """Extract all text from a PDF file as a single string.

    Args:
        path: Path to the PDF file (can be Path object or string)

    Returns:
        Complete text content of the PDF with pages concatenated

    Raises:
        FileNotFoundError: If the PDF file does not exist
        PDFParseError: If the PDF cannot be parsed

    Examples:
        >>> text = read_pdf_text("contract.pdf")
        >>> "Expression of Interest" in text
        True
    """
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(f"PDF file not found: {path}")

    if not path.is_file():
        raise PDFParseError(f"Path is not a file: {path}")

    try:
        with pdfplumber.open(path) as pdf:
            text_parts = []
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)

            if not text_parts:
                raise PDFParseError(f"No text could be extracted from PDF: {path}")

            return "\n".join(text_parts)
    except Exception as e:
        if isinstance(e, (FileNotFoundError, PDFParseError)):
            raise
        raise PDFParseError(f"Failed to parse PDF {path}: {str(e)}") from e


def read_pdf_pages(path: Union[Path, str]) -> List[str]:
    """Extract text from a PDF file, returning each page as a separate string.

    Args:
        path: Path to the PDF file (can be Path object or string)

    Returns:
        List of strings, one per page, in order

    Raises:
        FileNotFoundError: If the PDF file does not exist
        PDFParseError: If the PDF cannot be parsed

    Examples:
        >>> pages = read_pdf_pages("contract.pdf")
        >>> len(pages) >= 1
        True
        >>> "CONTRACT OF SALE" in pages[0]
        True
    """
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(f"PDF file not found: {path}")

    if not path.is_file():
        raise PDFParseError(f"Path is not a file: {path}")

    try:
        with pdfplumber.open(path) as pdf:
            pages = []
            for page in pdf.pages:
                page_text = page.extract_text()
                # Include even empty pages to maintain page numbering
                pages.append(page_text if page_text else "")

            if not pages:
                raise PDFParseError(f"PDF has no pages: {path}")

            return pages
    except Exception as e:
        if isinstance(e, (FileNotFoundError, PDFParseError)):
            raise
        raise PDFParseError(f"Failed to parse PDF {path}: {str(e)}") from e


def extract_tables_from_pdf(path: Union[Path, str]) -> List[List[List[str]]]:
    """Extract all tables from a PDF file.

    Useful for EOI forms that contain structured data in table format.

    Args:
        path: Path to the PDF file (can be Path object or string)

    Returns:
        List of tables, where each table is a list of rows,
        and each row is a list of cell values (strings)

    Raises:
        FileNotFoundError: If the PDF file does not exist
        PDFParseError: If the PDF cannot be parsed

    Examples:
        >>> tables = extract_tables_from_pdf("eoi.pdf")
        >>> isinstance(tables, list)
        True
    """
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(f"PDF file not found: {path}")

    if not path.is_file():
        raise PDFParseError(f"Path is not a file: {path}")

    try:
        with pdfplumber.open(path) as pdf:
            all_tables = []
            for page in pdf.pages:
                page_tables = page.extract_tables()
                if page_tables:
                    all_tables.extend(page_tables)

            return all_tables
    except Exception as e:
        if isinstance(e, (FileNotFoundError, PDFParseError)):
            raise
        raise PDFParseError(f"Failed to extract tables from PDF {path}: {str(e)}") from e


def get_pdf_metadata(path: Union[Path, str]) -> dict:
    """Extract metadata from a PDF file.

    Args:
        path: Path to the PDF file (can be Path object or string)

    Returns:
        Dictionary containing PDF metadata (title, author, page count, etc.)

    Raises:
        FileNotFoundError: If the PDF file does not exist
        PDFParseError: If the PDF cannot be parsed

    Examples:
        >>> metadata = get_pdf_metadata("contract.pdf")
        >>> "page_count" in metadata
        True
    """
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(f"PDF file not found: {path}")

    if not path.is_file():
        raise PDFParseError(f"Path is not a file: {path}")

    try:
        with pdfplumber.open(path) as pdf:
            metadata = {
                "page_count": len(pdf.pages),
                "metadata": pdf.metadata or {},
            }
            return metadata
    except Exception as e:
        if isinstance(e, (FileNotFoundError, PDFParseError)):
            raise
        raise PDFParseError(f"Failed to extract metadata from PDF {path}: {str(e)}") from e
