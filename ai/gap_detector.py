"""
Deterministic Gap Detection Module
Uses pandas for precise, 100% accurate gap detection in CSV data.

This module provides deterministic analysis of:
- Column gaps (completely empty columns)
- Mostly empty columns (95%+ empty)
- Sparse columns (80-94% empty)
- Row gaps (empty rows)
"""

import pandas as pd
import io
from typing import Dict, Any, List
from logger import AppLogger

logger = AppLogger.get_logger(__file__)


def detect_gaps_deterministic(csv_content: str) -> Dict[str, Any]:
    """
    Deterministic pandas-based gap detection.
    Returns 100% accurate column gap information.

    Args:
        csv_content: CSV file content as string

    Returns:
        Dictionary containing:
        - column_gaps: List of detected column gaps with confidence scores
        - row_gaps: List of detected row gaps
        - method: 'deterministic_pandas'
        - total_gaps_detected: Total number of gaps found
    """
    try:
        logger.info("Starting deterministic gap detection using pandas")

        # Parse CSV
        df = pd.read_csv(io.StringIO(csv_content))

        # Detect column gaps
        column_gaps = _detect_column_gaps(df)

        # Detect row gaps
        row_gaps = _detect_row_gaps(df)

        result = {
            "column_gaps": column_gaps,
            "row_gaps": row_gaps,
            "method": "deterministic_pandas",
            "total_gaps_detected": len(column_gaps) + len(row_gaps),
            "total_columns": len(df.columns),
            "total_rows": len(df)
        }

        logger.info(
            f"Deterministic gap detection complete: "
            f"{len(column_gaps)} column gaps, {len(row_gaps)} row gaps"
        )

        return result

    except Exception as e:
        logger.error(f"Error in deterministic gap detection: {e}", exc_info=True)
        return {
            "column_gaps": [],
            "row_gaps": [],
            "method": "deterministic_pandas",
            "total_gaps_detected": 0,
            "error": str(e)
        }


def _detect_column_gaps(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """
    Detect column gaps in dataframe.

    Args:
        df: Pandas DataFrame

    Returns:
        List of column gap detections
    """
    column_gaps = []

    for col_idx, col_name in enumerate(df.columns):
        column_data = df[col_name]
        total_cells = len(column_data)

        if total_cells == 0:
            continue

        # Count empty cells (NaN or empty string)
        empty_cells = column_data.isna().sum()

        # Also count cells that are empty strings
        if column_data.dtype == 'object':
            empty_cells += (column_data.str.strip() == '').sum()

        empty_percentage = (empty_cells / total_cells) * 100

        # Classify gap type based on empty percentage
        gap_info = _classify_gap_type(
            col_idx, col_name, empty_percentage, total_cells, empty_cells
        )

        if gap_info:
            column_gaps.append(gap_info)

    return column_gaps


def _classify_gap_type(
    col_idx: int,
    col_name: str,
    empty_percentage: float,
    total_cells: int,
    empty_cells: int
) -> Dict[str, Any]:
    """
    Classify gap type based on empty percentage.

    Args:
        col_idx: Column index
        col_name: Column name
        empty_percentage: Percentage of empty cells
        total_cells: Total cells in column
        empty_cells: Number of empty cells

    Returns:
        Gap information dictionary or None if not a gap
    """
    if empty_percentage == 100.0:
        # Completely empty column - DEFINITE GAP
        return {
            "column_index": col_idx,
            "column_name": col_name,
            "gap_type": "completely_empty",
            "empty_percentage": 100.0,
            "total_cells": total_cells,
            "empty_cells": empty_cells,
            "confidence": 1.0,
            "reasoning": "Column is 100% empty - definite gap"
        }

    elif empty_percentage >= 95.0:
        # Mostly empty (95%+) - PROBABLE GAP
        return {
            "column_index": col_idx,
            "column_name": col_name,
            "gap_type": "mostly_empty",
            "empty_percentage": round(empty_percentage, 2),
            "total_cells": total_cells,
            "empty_cells": empty_cells,
            "confidence": 0.9,
            "reasoning": f"Column is {round(empty_percentage, 1)}% empty - highly likely gap"
        }

    elif empty_percentage >= 80.0:
        # Sparse column (80-94%) - POSSIBLE GAP
        return {
            "column_index": col_idx,
            "column_name": col_name,
            "gap_type": "sparse",
            "empty_percentage": round(empty_percentage, 2),
            "total_cells": total_cells,
            "empty_cells": empty_cells,
            "confidence": 0.7,
            "reasoning": f"Column is {round(empty_percentage, 1)}% empty - possibly intentional gap or sparse data"
        }

    else:
        # Not a gap (<80% empty)
        return None


def _detect_row_gaps(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """
    Detect row gaps (completely empty rows) in dataframe.

    Args:
        df: Pandas DataFrame

    Returns:
        List of row gap detections
    """
    row_gaps = []

    for row_idx in range(len(df)):
        row_data = df.iloc[row_idx]

        # Check if row is completely empty
        empty_cells = row_data.isna().sum()

        # Also count empty strings
        if row_data.dtype == 'object':
            empty_cells += (row_data.str.strip() == '').sum()

        if empty_cells == len(row_data):
            # Completely empty row
            row_gaps.append({
                "row_index": row_idx,
                "gap_type": "empty_row",
                "location": f"row {row_idx}",
                "confidence": 1.0,
                "reasoning": "Row is completely empty - separator or formatting gap"
            })

    return row_gaps


def analyze_column_distribution(df: pd.DataFrame, col_name: str) -> Dict[str, Any]:
    """
    Analyze the distribution of values in a column.
    Useful for understanding data patterns and quality.

    Args:
        df: Pandas DataFrame
        col_name: Column name to analyze

    Returns:
        Dictionary with distribution statistics
    """
    try:
        column_data = df[col_name]

        total_cells = len(column_data)
        empty_cells = column_data.isna().sum()
        filled_cells = total_cells - empty_cells

        # Calculate percentages
        empty_pct = (empty_cells / total_cells * 100) if total_cells > 0 else 0
        filled_pct = (filled_cells / total_cells * 100) if total_cells > 0 else 0

        # Get unique values count
        unique_values = column_data.nunique(dropna=True)

        return {
            "column_name": col_name,
            "total_cells": total_cells,
            "empty_cells": empty_cells,
            "filled_cells": filled_cells,
            "empty_percentage": round(empty_pct, 2),
            "filled_percentage": round(filled_pct, 2),
            "unique_values": unique_values,
            "data_type": str(column_data.dtype)
        }

    except Exception as e:
        logger.error(f"Error analyzing column distribution for '{col_name}': {e}")
        return {
            "column_name": col_name,
            "error": str(e)
        }


def get_gap_summary(gaps_result: Dict[str, Any]) -> str:
    """
    Generate a human-readable summary of gap detection results.

    Args:
        gaps_result: Result from detect_gaps_deterministic()

    Returns:
        Human-readable summary string
    """
    column_gaps = gaps_result.get("column_gaps", [])
    row_gaps = gaps_result.get("row_gaps", [])

    summary_lines = []

    # Column gaps summary
    if column_gaps:
        summary_lines.append(f"Found {len(column_gaps)} column gap(s):")
        for gap in column_gaps:
            summary_lines.append(
                f"  - Column {gap['column_index']} ('{gap['column_name']}'): "
                f"{gap['gap_type']} ({gap['empty_percentage']}% empty, confidence: {gap['confidence']})"
            )
    else:
        summary_lines.append("No column gaps detected")

    # Row gaps summary
    if row_gaps:
        summary_lines.append(f"\nFound {len(row_gaps)} row gap(s):")
        for gap in row_gaps:
            summary_lines.append(f"  - {gap['location']}: {gap['gap_type']}")
    else:
        summary_lines.append("No row gaps detected")

    return "\n".join(summary_lines)
