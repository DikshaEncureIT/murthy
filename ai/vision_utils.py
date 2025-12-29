"""
Vision Utilities for Excel Analysis
Handles conversion of Excel sheets to HIGH-QUALITY images and base64 encoding for vision API
"""

import io
import base64
from pathlib import Path
from typing import List, Tuple, Dict, Any
from datetime import datetime
import openpyxl
from openpyxl.utils import get_column_letter
from openpyxl.styles import Font, Alignment
from PIL import Image, ImageDraw, ImageFont
import asyncio
from logger import AppLogger

logger = AppLogger.get_logger(__file__)


def convert_excel_sheet_to_image(
    excel_path: Path,
    sheet_name: str,
    output_path: Path,
    max_width: int = 3840,  # 4K width
    max_height: int = 2160, # 4K height
    cell_width: int = 150,  # Increased width
    cell_height: int = 45   # Increased height
) -> Tuple[Path, Dict[str, Any]]:
    """
    Convert an Excel sheet to a HIGH-QUALITY PNG image using openpyxl + Pillow.

    ENHANCED FEATURES:
    - 4K resolution support
    - Cell background colors
    - Better borders and grid
    - Supports up to 200 rows x 50 columns
    - Larger, clearer fonts
    - Better color contrast

    Args:
        excel_path: Path to Excel file
        sheet_name: Name of sheet to convert
        output_path: Where to save the PNG
        max_width: Maximum image width in pixels
        max_height: Maximum image height in pixels
        cell_width: Width of each cell in pixels
        cell_height: Height of each cell in pixels

    Returns:
        Tuple of (image_path, metadata)
    """
    try:
        logger.info(f"Converting sheet '{sheet_name}' to HIGH-QUALITY image")

        # Load workbook and sheet
        wb = openpyxl.load_workbook(excel_path, data_only=True)
        ws = wb[sheet_name]

        # Get the used range
        if ws.max_row == 0 or ws.max_column == 0:
            # Empty sheet
            logger.warning(f"Sheet '{sheet_name}' is empty, creating minimal image")
            img = Image.new('RGB', (400, 200), color='white')
            draw = ImageDraw.Draw(img)
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
            except:
                font = ImageFont.load_default()
            draw.text((20, 80), f"Empty Sheet: {sheet_name}", fill='black', font=font)
            img.save(output_path, quality=95, optimize=True)
            wb.close()
            return output_path, {"rows": 0, "columns": 0, "empty": True}

        # Increased limits for better coverage
        max_rows = min(ws.max_row, 200)  # Increased from 100 to 200
        max_cols = min(ws.max_column, 50)  # Increased from 26 to 50

        # Calculate image dimensions
        img_width = min(max_cols * cell_width + 1, max_width)
        img_height = min(max_rows * cell_height + 1, max_height)

        logger.info(f"Creating image: {img_width}x{img_height} ({max_rows} rows x {max_cols} cols)")

        # Create image with white background
        img = Image.new('RGB', (img_width, img_height), color='white')
        draw = ImageDraw.Draw(img)

        # Load fonts with larger size
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)  # Increased from 12
            font_bold = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 14)
        except:
            font = ImageFont.load_default()
            font_bold = font

        # Track merged cells
        merged_ranges = list(ws.merged_cells.ranges)
        merged_cells_data = []

        # Helper function to convert Excel color to RGB
        def get_color_rgb(color):
            """Convert openpyxl color to RGB tuple."""
            if color is None:
                return None
            try:
                if hasattr(color, 'rgb'):
                    rgb_hex = color.rgb
                    # Check for default/white colors and return None
                    if rgb_hex in [None, '00000000', 'FFFFFFFF', 'FFFFFF', '000000']:
                        return None
                    if rgb_hex and len(rgb_hex) == 8:  # ARGB format
                        rgb = tuple(int(rgb_hex[i:i+2], 16) for i in (2, 4, 6))
                        # Check if it's white or very close to white
                        if all(c >= 250 for c in rgb):
                            return None
                        return rgb
                    elif rgb_hex and len(rgb_hex) == 6:  # RGB format
                        rgb = tuple(int(rgb_hex[i:i+2], 16) for i in (0, 2, 4))
                        # Check if it's white or very close to white
                        if all(c >= 250 for c in rgb):
                            return None
                        return rgb
            except:
                pass
            return None

        # Draw grid and cells
        for row_idx in range(1, max_rows + 1):
            for col_idx in range(1, max_cols + 1):
                cell = ws.cell(row=row_idx, column=col_idx)

                # Calculate cell position
                x = (col_idx - 1) * cell_width
                y = (row_idx - 1) * cell_height

                # Get cell background color (only if it's a solid fill with actual color)
                bg_color = None
                if cell.fill and hasattr(cell.fill, 'patternType'):
                    # Only process solid fills (not patterns)
                    if cell.fill.patternType == 'solid' and hasattr(cell.fill, 'fgColor'):
                        cell_color = get_color_rgb(cell.fill.fgColor)
                        if cell_color:
                            bg_color = cell_color

                # Draw cell background if it has a color
                if bg_color:
                    draw.rectangle(
                        [(x, y), (x + cell_width, y + cell_height)],
                        fill=bg_color,
                        outline='darkgray',
                        width=1
                    )
                else:
                    # Draw cell border only (light gray for normal cells)
                    draw.rectangle(
                        [(x, y), (x + cell_width, y + cell_height)],
                        outline='lightgray',
                        width=1
                    )

                # Check if cell is merged
                is_merged = False
                for merged_range in merged_ranges:
                    if cell.coordinate in merged_range:
                        is_merged = True
                        # Draw merged cell border (thicker)
                        if cell.coordinate == merged_range.min_cell:
                            # Calculate merged cell dimensions
                            min_row, min_col, max_row, max_col = merged_range.bounds
                            merge_x = (min_col - 1) * cell_width
                            merge_y = (min_row - 1) * cell_height
                            merge_width = (max_col - min_col + 1) * cell_width
                            merge_height = (max_row - min_row + 1) * cell_height

                            # Draw merged cell border
                            draw.rectangle(
                                [(merge_x, merge_y), (merge_x + merge_width, merge_y + merge_height)],
                                outline='darkblue',
                                width=2
                            )

                            merged_cells_data.append({
                                "range": str(merged_range),
                                "value": str(cell.value) if cell.value else ""
                            })
                        break

                # Get cell value
                cell_value = str(cell.value) if cell.value is not None else ""

                # Truncate long values but allow more characters
                if len(cell_value) > 30:
                    cell_value = cell_value[:27] + "..."

                # Check formatting
                is_bold = False
                text_color = 'black'

                if cell.font:
                    if cell.font.bold:
                        is_bold = True
                    # Get text color
                    font_color = get_color_rgb(cell.font.color)
                    if font_color:
                        text_color = font_color

                # Draw cell value
                if cell_value:
                    text_font = font_bold if is_bold else font

                    # Add padding for text
                    text_x = x + 5
                    text_y = y + 12

                    # Draw text with color
                    draw.text(
                        (text_x, text_y),
                        cell_value,
                        fill=text_color,
                        font=text_font
                    )

        # Draw outer border (thick)
        draw.rectangle(
            [(0, 0), (img_width - 1, img_height - 1)],
            outline='black',
            width=2
        )

        # Save image with high quality
        img.save(output_path, quality=95, optimize=True)
        logger.info(f"HIGH-QUALITY image saved: {output_path.name} ({img_width}x{img_height})")

        metadata = {
            "rows": max_rows,
            "columns": max_cols,
            "dimensions": (img_width, img_height),
            "merged_cells_count": len(merged_cells_data),
            "merged_cells": merged_cells_data,
            "empty": False,
            "quality": "enhanced"
        }

        wb.close()
        return output_path, metadata

    except Exception as e:
        logger.error(f"Error converting sheet '{sheet_name}' to image: {e}", exc_info=True)
        raise RuntimeError(f"Error converting sheet '{sheet_name}': {e}")


async def convert_all_sheets_to_images(
    excel_path: Path,
    output_folder: Path,
    sheets: List[str] = None
) -> List[Dict[str, Any]]:
    """
    Convert all sheets in an Excel file to HIGH-QUALITY images in parallel.

    Args:
        excel_path: Path to Excel file
        output_folder: Folder to save images
        sheets: List of sheet names (None = all sheets)

    Returns:
        List of dicts with sheet_name, image_path, dimensions, metadata
    """
    try:
        logger.info(f"Starting HIGH-QUALITY image conversion for {excel_path.name}")

        # Load workbook to get sheet names
        wb = openpyxl.load_workbook(excel_path, read_only=True)
        sheet_names = sheets if sheets else wb.sheetnames
        wb.close()

        if not sheet_names:
            logger.warning(f"No sheets found in {excel_path.name}")
            return []

        logger.info(f"Converting {len(sheet_names)} sheets to images")

        # Create output folder if not exists
        output_folder.mkdir(parents=True, exist_ok=True)

        # Prepare tasks for parallel processing
        loop = asyncio.get_event_loop()
        tasks = []

        for sheet_name in sheet_names:
            # Generate unique output filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_sheet_name = "".join(c for c in sheet_name if c.isalnum() or c in (' ', '-', '_')).strip().replace(' ', '_')
            output_filename = f"{excel_path.stem}_{safe_sheet_name}_{timestamp}.png"
            output_path = output_folder / output_filename

            # Run conversion in executor (CPU-bound)
            task = loop.run_in_executor(
                None,
                convert_excel_sheet_to_image,
                excel_path,
                sheet_name,
                output_path
            )
            tasks.append((sheet_name, task))

        # Wait for all conversions to complete
        results = []
        for sheet_name, task in tasks:
            try:
                image_path, metadata = await task
                results.append({
                    "sheet_name": sheet_name,
                    "image_path": str(image_path),
                    "metadata": metadata
                })
                logger.info(f"Sheet '{sheet_name}' converted successfully")
            except Exception as e:
                logger.error(f"Failed to convert sheet '{sheet_name}': {e}")
                results.append({
                    "sheet_name": sheet_name,
                    "image_path": None,
                    "error": str(e),
                    "metadata": None
                })

        logger.info(f"Image conversion complete: {len(results)} sheets processed")
        return results

    except Exception as e:
        logger.error(f"Error converting sheets to images: {e}", exc_info=True)
        raise


def encode_image_to_base64(image_path: Path) -> str:
    """
    Encode image to base64 for OpenAI Vision API.

    Args:
        image_path: Path to image file

    Returns:
        Base64 encoded string
    """
    try:
        with open(image_path, "rb") as image_file:
            image_data = image_file.read()
            base64_image = base64.b64encode(image_data).decode('utf-8')
            logger.debug(f"Encoded image {image_path.name} to base64 ({len(base64_image)} chars)")
            return base64_image
    except Exception as e:
        logger.error(f"Error encoding image to base64: {e}", exc_info=True)
        raise RuntimeError(f"Error encoding image: {e}")


def extract_excel_data_for_vision(
    excel_path: Path,
    sheet_name: str,
    max_rows: int = 100,
    max_cols: int = 50
) -> str:
    """
    Extract Excel sheet data in CSV-like format for vision model.

    Provides structured Excel data including:
    - Raw cell values (text, numbers, dates)
    - Merged cell information (which cells are merged)
    - Cell formulas (where they exist)
    - Cell coordinates (for correlation with visual image)

    Args:
        excel_path: Path to Excel file
        sheet_name: Name of sheet to extract
        max_rows: Maximum rows to extract (default: 100)
        max_cols: Maximum columns to extract (default: 50)

    Returns:
        Formatted string with Excel data in CSV-like structure

    Raises:
        FileNotFoundError: If excel_path doesn't exist
        ValueError: If sheet_name not found in workbook
    """
    try:
        logger.info(f"Extracting Excel data for vision analysis: sheet '{sheet_name}'")

        # Validate Excel file exists
        if not excel_path.exists():
            raise FileNotFoundError(f"Excel file not found: {excel_path}")

        # Load workbook (data_only=False to get formulas)
        wb = openpyxl.load_workbook(excel_path, data_only=False)

        # Validate sheet exists
        if sheet_name not in wb.sheetnames:
            wb.close()
            raise ValueError(f"Sheet '{sheet_name}' not found in {excel_path.name}. Available sheets: {', '.join(wb.sheetnames)}")

        ws = wb[sheet_name]

        # Handle empty sheet
        if ws.max_row == 0 or ws.max_column == 0:
            wb.close()
            logger.info(f"Sheet '{sheet_name}' is empty")
            return f"[EXCEL DATA - Sheet: {sheet_name}]\n[EMPTY SHEET]\n[END EXCEL DATA]"

        # Limit dimensions
        actual_rows = min(ws.max_row, max_rows)
        actual_cols = min(ws.max_column, max_cols)

        logger.info(f"Extracting {actual_rows} rows × {actual_cols} columns")

        # Build merged cells lookup
        merged_lookup = {}  # {cell_coordinate: (merged_range, top_left_coord, bottom_right_coord)}
        for merged_range in ws.merged_cells.ranges:
            top_left = f"{get_column_letter(merged_range.min_col)}{merged_range.min_row}"
            bottom_right = f"{get_column_letter(merged_range.max_col)}{merged_range.max_row}"

            for row in range(merged_range.min_row, merged_range.max_row + 1):
                for col in range(merged_range.min_col, merged_range.max_col + 1):
                    coord = f"{get_column_letter(col)}{row}"
                    merged_lookup[coord] = (merged_range, top_left, bottom_right)

        # Build output
        lines = [f"[EXCEL DATA - Sheet: {sheet_name}]"]

        for row_idx in range(1, actual_rows + 1):
            row_parts = [f"Row {row_idx}:"]

            for col_idx in range(1, actual_cols + 1):
                cell = ws.cell(row=row_idx, column=col_idx)
                coord = cell.coordinate

                # Check if cell is part of merged range
                if coord in merged_lookup:
                    _, top_left, bottom_right = merged_lookup[coord]

                    if coord == top_left:
                        # Top-left of merged range - include value and merge annotation
                        value = str(cell.value) if cell.value is not None else ""
                        # No truncation - send full value
                        row_parts.append(f"[{coord}→{bottom_right} MERGED] {value}")
                    else:
                        # Other cells in merged range - just show coordinate (empty)
                        row_parts.append(f"[{coord}]")
                    continue

                # Check if cell has formula
                if hasattr(cell, 'value') and isinstance(cell.value, str) and cell.value.startswith('='):
                    formula = cell.value
                    # For formulas, we show the formula itself
                    row_parts.append(f"[{coord} {formula}]")
                else:
                    # Regular cell with value
                    value = str(cell.value) if cell.value is not None else ""
                    # No truncation - send full value for accurate extraction

                    if value:
                        row_parts.append(f"[{coord}] {value}")
                    else:
                        # Empty cell - just coordinate
                        row_parts.append(f"[{coord}]")

            lines.append("\t".join(row_parts))

        lines.append("[END EXCEL DATA]")

        result = "\n".join(lines)
        wb.close()

        logger.info(f"Excel data extracted: {len(result)} characters")
        return result

    except (FileNotFoundError, ValueError):
        # Re-raise validation errors
        raise
    except Exception as e:
        logger.error(f"Error extracting Excel data: {e}", exc_info=True)
        raise RuntimeError(f"Error extracting Excel data: {e}")


def analyze_column_usage_sequences(excel_path: Path, sheet_name: str) -> Dict[str, Any]:
    """
    Analyze Excel sheet to determine column usage patterns and sequence gaps.

    This function deterministically analyzes which columns contain data and identifies
    sequence gaps where columns are unused between columns with data.

    Args:
        excel_path: Path to Excel file
        sheet_name: Name of sheet to analyze

    Returns:
        Dictionary with column usage analysis including:
        - sheet_name: Name of the analyzed sheet
        - total_columns_in_sheet: Total columns analyzed
        - columns_with_data: List of column letters that contain data
        - column_sequences: List of sequences (data/gap regions)
        - gap_summary: Human-readable summary string
        - total_gaps: Number of gap sequences found
        - confidence: 1.0 (deterministic analysis)
        - method: 'deterministic_openpyxl'
    """
    try:
        logger.info(f"Analyzing column usage for sheet '{sheet_name}'")

        # Load workbook
        wb = openpyxl.load_workbook(excel_path, data_only=True)

        # Check if sheet exists
        if sheet_name not in wb.sheetnames:
            logger.error(f"Sheet '{sheet_name}' not found in workbook")
            wb.close()
            return {
                "sheet_name": sheet_name,
                "error": f"Sheet '{sheet_name}' not found",
                "total_columns_in_sheet": 0,
                "columns_with_data": [],
                "column_sequences": [],
                "gap_summary": "Sheet not found",
                "total_gaps": 0,
                "confidence": 0.0,
                "method": "deterministic_openpyxl"
            }

        ws = wb[sheet_name]

        # Handle empty sheets
        if ws.max_row == 0 or ws.max_column == 0:
            logger.info(f"Sheet '{sheet_name}' is empty")
            wb.close()
            return {
                "sheet_name": sheet_name,
                "total_columns_in_sheet": 0,
                "columns_with_data": [],
                "column_sequences": [],
                "gap_summary": "Empty sheet - no data",
                "total_gaps": 0,
                "confidence": 1.0,
                "method": "deterministic_openpyxl"
            }

        # Limit columns for performance
        MAX_COLUMNS_TO_ANALYZE = 100
        max_cols = min(ws.max_column, MAX_COLUMNS_TO_ANALYZE)

        logger.info(f"Analyzing {max_cols} columns in sheet '{sheet_name}'")

        # Determine which columns have data
        columns_with_data = []
        for col_idx in range(1, max_cols + 1):
            has_data = False
            # Check if any cell in this column has data
            for row in ws.iter_rows(min_col=col_idx, max_col=col_idx, min_row=1, max_row=ws.max_row):
                for cell in row:
                    if cell.value is not None and str(cell.value).strip() != "":
                        has_data = True
                        break
                if has_data:
                    break

            if has_data:
                col_letter = get_column_letter(col_idx)
                columns_with_data.append(col_letter)

        wb.close()

        # If no columns have data
        if not columns_with_data:
            return {
                "sheet_name": sheet_name,
                "total_columns_in_sheet": max_cols,
                "columns_with_data": [],
                "column_sequences": [],
                "gap_summary": "No columns with data found",
                "total_gaps": 0,
                "confidence": 1.0,
                "method": "deterministic_openpyxl"
            }

        # Build column sequences
        column_sequences = []
        gap_count = 0

        # Convert column letters to indices for easier comparison
        col_indices_with_data = []
        for col_letter in columns_with_data:
            col_idx = openpyxl.utils.column_index_from_string(col_letter)
            col_indices_with_data.append((col_idx, col_letter))

        # Group into sequences
        current_seq_start = 1
        summary_parts = []

        i = 0
        while i < len(col_indices_with_data):
            col_idx, col_letter = col_indices_with_data[i]

            # Check if there's a gap before this column
            if col_idx > current_seq_start:
                # There's a gap
                gap_start = current_seq_start
                gap_end = col_idx - 1
                gap_start_letter = get_column_letter(gap_start)
                gap_end_letter = get_column_letter(gap_end)

                if gap_start == gap_end:
                    gap_label = gap_start_letter
                else:
                    gap_label = f"{gap_start_letter}-{gap_end_letter}"

                column_sequences.append({
                    "sequence_id": len(column_sequences) + 1,
                    "columns": [get_column_letter(c) for c in range(gap_start, gap_end + 1)],
                    "start_col": gap_start_letter,
                    "end_col": gap_end_letter,
                    "has_data": False,
                    "gap_type": "sequence_gap"
                })
                summary_parts.append(f"GAP ({gap_label} empty)")
                gap_count += 1

            # Find sequence of consecutive columns with data
            seq_start = col_idx
            seq_end = col_idx

            # Group consecutive columns with data
            while i + 1 < len(col_indices_with_data) and col_indices_with_data[i + 1][0] == seq_end + 1:
                i += 1
                seq_end = col_indices_with_data[i][0]

            seq_start_letter = get_column_letter(seq_start)
            seq_end_letter = get_column_letter(seq_end)

            # Get all column letters in this sequence
            seq_columns = [get_column_letter(c) for c in range(seq_start, seq_end + 1) if get_column_letter(c) in columns_with_data]

            column_sequences.append({
                "sequence_id": len(column_sequences) + 1,
                "columns": seq_columns,
                "start_col": seq_start_letter,
                "end_col": seq_end_letter,
                "has_data": True
            })

            if seq_start == seq_end:
                summary_parts.append(f"column {seq_start_letter} used")
            elif len(seq_columns) <= 3:
                # For short sequences, list individual columns
                summary_parts.append(f"columns {','.join(seq_columns)} used")
            else:
                # For longer sequences, show range
                summary_parts.append(f"columns {seq_start_letter}-{seq_end_letter} used")

            current_seq_start = seq_end + 1
            i += 1

        # Check if there's a gap after the last column with data
        if col_indices_with_data:
            last_col_idx = col_indices_with_data[-1][0]
            if last_col_idx < max_cols:
                gap_start = last_col_idx + 1
                gap_end = max_cols
                gap_start_letter = get_column_letter(gap_start)
                gap_end_letter = get_column_letter(gap_end)

                if gap_start == gap_end:
                    gap_label = gap_start_letter
                else:
                    gap_label = f"{gap_start_letter}-{gap_end_letter}"

                column_sequences.append({
                    "sequence_id": len(column_sequences) + 1,
                    "columns": [get_column_letter(c) for c in range(gap_start, gap_end + 1)],
                    "start_col": gap_start_letter,
                    "end_col": gap_end_letter,
                    "has_data": False,
                    "gap_type": "sequence_gap"
                })
                summary_parts.append(f"GAP ({gap_label} empty)")
                gap_count += 1

        # Generate gap summary
        gap_summary = " → ".join(summary_parts)

        result = {
            "sheet_name": sheet_name,
            "total_columns_in_sheet": max_cols,
            "columns_with_data": columns_with_data,
            "column_sequences": column_sequences,
            "gap_summary": gap_summary,
            "total_gaps": gap_count,
            "confidence": 1.0,
            "method": "deterministic_openpyxl"
        }

        logger.info(f"Column analysis complete for '{sheet_name}': {gap_count} gaps, {len(columns_with_data)} columns with data")
        return result

    except Exception as e:
        logger.error(f"Error analyzing column usage for sheet '{sheet_name}': {e}", exc_info=True)
        return {
            "sheet_name": sheet_name,
            "error": str(e),
            "total_columns_in_sheet": 0,
            "columns_with_data": [],
            "column_sequences": [],
            "gap_summary": f"Analysis failed: {str(e)}",
            "total_gaps": 0,
            "confidence": 0.0,
            "method": "deterministic_openpyxl"
        }


def extract_columns_with_gap(column_sequences: List[Dict]) -> List[str]:
    """
    Extract columns that contain no data (gaps) from column sequences.

    Args:
        column_sequences: List of sequence dicts with 'has_data' and 'columns' keys

    Returns:
        Flat list of column letters that are gaps (has_data=False)
    """
    gap_columns = []
    for sequence in column_sequences:
        if not sequence.get("has_data", False):
            gap_columns.extend(sequence.get("columns", []))
    return gap_columns
