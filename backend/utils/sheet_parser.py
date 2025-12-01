"""Utilities for parsing Google Sheets data."""
from typing import Callable


def find_header_row(rows: list[list[str]], min_matches: int = 2) -> int:
    """
    Find the row that contains the expected column headers.
    
    Args:
        rows: List of rows from the sheet
        min_matches: Minimum number of expected keywords to match (default: 2)
    
    Returns:
        Index of the header row, or 0 if not found
    """
    expected_keywords = ["company", "position", "date"]
    for idx, row in enumerate(rows):
        row_lower = [str(cell).lower() for cell in row]
        # Check if this row contains the expected keywords
        has_company = any("company" in cell for cell in row_lower)
        has_position = any("position" in cell for cell in row_lower)
        has_date = any("date" in cell for cell in row_lower)
        has_url = any("job url" in cell or "url" in cell for cell in row_lower)
        
        # Count matches
        matches = sum([has_company, has_position, has_date, has_url])
        if matches >= min_matches:
            return idx
    # Fallback to first row if no header row found
    return 0


def find_column_index(headers: list[str], predicate: Callable[[str], bool], default: int) -> int:
    """
    Find the index of a column matching the predicate.
    
    Args:
        headers: List of header strings
        predicate: Function that returns True if header matches
        default: Default index if not found
    
    Returns:
        Column index
    """
    try:
        return next(i for i, h in enumerate(headers) if predicate(h.lower()))
    except StopIteration:
        return default


def parse_sheet_columns(headers: list[str]) -> dict[str, int]:
    """
    Parse sheet headers to find column indices for common fields.
    
    Returns:
        Dictionary with keys: company_idx, position_idx, job_url_idx, date_idx
    """
    # Ensure headers are padded to at least 7 columns
    padded_headers = (headers + [""] * 7)[:7]
    
    return {
        "company_idx": find_column_index(padded_headers, lambda h: "company" in h, 0),
        "position_idx": find_column_index(padded_headers, lambda h: "position" in h, 2),
        "job_url_idx": find_column_index(padded_headers, lambda h: "job url" in h or "url" in h, 3),
        "date_idx": find_column_index(padded_headers, lambda h: "date" in h, 1),
    }

