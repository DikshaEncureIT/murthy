import os
import json
import shutil
import asyncio
from pathlib import Path
from typing import Dict, Any, List, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

from dotenv import load_dotenv
from landingai_ade import LandingAIADE
from openai import OpenAI
import pandas as pd
from logger import AppLogger
from vision_processor import process_excel_with_vision

# Load environment variables
load_dotenv(".env")

# Initialize logger
logger = AppLogger.get_logger(__file__)

LANDINGAI_API_KEY = os.getenv("LANDINGAI_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY is not set in .env")


def sanitize_filename(name: str, fallback_prefix: str = "sheet") -> str:
    """Sanitize sheet name for use as filename."""
    safe_name = "".join(c for c in name if c.isalnum() or c in (' ', '-', '_')).strip()
    safe_name = safe_name.replace(' ', '_')

    if not safe_name:
        safe_name = f"{fallback_prefix}_{hash(name) % 10000}"

    return safe_name


def export_sheet_to_single_excel(excel_path: Path, sheet_name: str, output_path: Path) -> Path:
    """
    Export a single sheet to a new Excel file.

    Uses openpyxl to preserve exact structure including:
    - Empty columns (critical for gap detection)
    - Cell formatting
    - Merged cells
    """
    try:
        import openpyxl
        from openpyxl import Workbook

        # Load source workbook
        source_wb = openpyxl.load_workbook(excel_path, data_only=True)

        if sheet_name not in source_wb.sheetnames:
            raise ValueError(f"Sheet '{sheet_name}' not found in {excel_path.name}")

        source_sheet = source_wb[sheet_name]

        # Create new workbook and copy sheet
        target_wb = Workbook()
        target_sheet = target_wb.active
        target_sheet.title = sheet_name

        # Copy all cells (including empty ones to preserve column structure)
        for row in source_sheet.iter_rows():
            for cell in row:
                target_cell = target_sheet[cell.coordinate]
                target_cell.value = cell.value

                # Copy formatting
                if cell.has_style:
                    target_cell.font = cell.font.copy()
                    target_cell.border = cell.border.copy()
                    target_cell.fill = cell.fill.copy()
                    target_cell.number_format = cell.number_format
                    target_cell.protection = cell.protection.copy()
                    target_cell.alignment = cell.alignment.copy()

        # Copy column dimensions
        for col_letter, col_dim in source_sheet.column_dimensions.items():
            target_sheet.column_dimensions[col_letter].width = col_dim.width

        # Copy row dimensions
        for row_num, row_dim in source_sheet.row_dimensions.items():
            target_sheet.row_dimensions[row_num].height = row_dim.height

        # Copy merged cells
        for merged_cell_range in source_sheet.merged_cells.ranges:
            target_sheet.merge_cells(str(merged_cell_range))

        # Save to output
        target_wb.save(output_path)
        source_wb.close()
        target_wb.close()

        logger.debug(f"Exported sheet '{sheet_name}' preserving all columns and formatting")
        return output_path

    except Exception as e:
        raise RuntimeError(f"Error exporting sheet '{sheet_name}': {e}")


def remove_gap_columns_from_excel(excel_path: Path, columns_to_remove: List[str]) -> Path:
    """
    Remove specified gap columns from an Excel file.

    Used when vision analysis identifies a single table with gap columns
    that need to be removed for cleaner markdown extraction.

    Args:
        excel_path: Path to Excel file
        columns_to_remove: List of column letters to remove (e.g., ["C", "F", "I"])

    Returns:
        Path to the modified Excel file (same as input)
    """
    try:
        import openpyxl
        from openpyxl.utils import column_index_from_string

        if not columns_to_remove:
            logger.debug(f"No columns to remove from {excel_path.name}")
            return excel_path

        logger.info(f"Removing {len(columns_to_remove)} gap columns from {excel_path.name}: {columns_to_remove}")

        # Load workbook
        wb = openpyxl.load_workbook(excel_path)
        ws = wb.active

        # Convert column letters to indices and sort in descending order
        # (delete from right to left to avoid index shifting issues)
        column_indices = sorted(
            [column_index_from_string(col) for col in columns_to_remove],
            reverse=True
        )

        # Delete columns
        for col_idx in column_indices:
            logger.debug(f"  Deleting column {openpyxl.utils.get_column_letter(col_idx)} (index {col_idx})")
            ws.delete_cols(col_idx, 1)

        # Save modified workbook
        wb.save(excel_path)
        wb.close()

        logger.info(f"Successfully removed gap columns from {excel_path.name}")
        return excel_path

    except Exception as e:
        logger.error(f"Error removing columns from {excel_path.name}: {e}", exc_info=True)
        # Don't raise - just return original file if column removal fails
        return excel_path


def extract_markdown_with_landingai(excel_file: Path, api_key: str = None) -> str:
    """Extract markdown content from Excel file using Landing AI ADE."""
    client = LandingAIADE(apikey=api_key or LANDINGAI_API_KEY)

    try:
        parse_response = client.parse(
            document=excel_file,
            model="dpt-2",
        )

        # Get markdown / html / text
        if hasattr(parse_response, "markdown") and parse_response.markdown:
            return parse_response.markdown
        elif hasattr(parse_response, "html") and parse_response.html:
            return parse_response.html
        elif hasattr(parse_response, "text") and parse_response.text:
            return parse_response.text
        else:
            return str(parse_response)
    except Exception as e:
        raise RuntimeError(f"Error parsing with Landing AI ADE: {e}")


def split_markdown_tables(markdown_text: str) -> List[str]:
    """
    Split markdown content into individual tables.
    Supports both HTML tables (<table>) and Markdown tables (|).
    Returns a list of table strings.
    """
    tables = []
    lines = markdown_text.split('\n')
    current_table = []
    in_table = False
    table_format = None  # 'html' or 'markdown'

    for line in lines:
        line_stripped = line.strip()

        # Check for HTML table start
        if '<table' in line_stripped.lower():
            in_table = True
            table_format = 'html'
            current_table.append(line)
        # Check for HTML table end
        elif '</table>' in line_stripped.lower():
            if in_table and table_format == 'html':
                current_table.append(line)
                tables.append('\n'.join(current_table))
                current_table = []
                in_table = False
                table_format = None
        # Check for Markdown table (line with |)
        elif '|' in line and not in_table:
            in_table = True
            table_format = 'markdown'
            current_table.append(line)
        # Continue collecting table content
        elif in_table:
            if table_format == 'html':
                current_table.append(line)
            elif table_format == 'markdown':
                if '|' in line:
                    current_table.append(line)
                else:
                    # Markdown table ended
                    tables.append('\n'.join(current_table))
                    current_table = []
                    in_table = False
                    table_format = None

    # Don't forget the last table if content ends with a table
    if current_table:
        tables.append('\n'.join(current_table))

    return tables


def extract_single_table_with_openai(table_markdown: str, sheet_name: str, table_index: int) -> Dict[str, Any]:
    """
    Send a single markdown table to OpenAI and extract table entities as structured JSON.
    """
    client = OpenAI(api_key=OPENAI_API_KEY)

    # Prompt for single table extraction
    user_instruction = f"""
You will receive a single table from Excel sheet: "{sheet_name}" in Markdown format.

CRITICAL RULES:
1. Return ONLY valid JSON with NO explanations, NO markdown formatting, NO additional text before or after the JSON
2. DO NOT skip ANY rows - extract EVERY single row from the table, including:
   - Header rows
   - Sub-header rows
   - Category label rows
   - Data rows
   - ALL rows without exception
3. Preserve exact cell values - do not summarize, skip, or merge any content

Extract the table in this exact structure:

{{
  "sheet_name": "{sheet_name}",
  "table_index": {table_index},
  "title": "<optional table title or empty string>",
  "headers": ["col1", "col2", ...],
  "rows": [
    ["row1_col1", "row1_col2", ...],
    ["row2_col1", "row2_col2", ...],
    ... (include ALL rows from the table)
  ]
}}

IMPORTANT:
- Your response must start with {{ and end with }}
- Do not skip intermediate header rows or category rows
- Include EVERY row present in the markdown table
- If a cell is empty, use empty string ""

Table markdown:
\"\"\"
{table_markdown}
\"\"\"
"""

    # OpenAI Chat Completion API
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a precise table extraction assistant. Extract ALL rows from tables without skipping any content. Include headers, sub-headers, category rows, and data rows. Always respond with valid JSON only."},
            {"role": "user", "content": user_instruction}
        ],
        temperature=0.0,
    )

    llm_output = response.choices[0].message.content
    

    # Clean markdown code blocks if present
    llm_output = llm_output.strip()
    if llm_output.startswith("```json"):
        llm_output = llm_output[7:]  # Remove ```json
    if llm_output.startswith("```"):
        llm_output = llm_output[3:]  # Remove ```
    if llm_output.endswith("```"):
        llm_output = llm_output[:-3]  # Remove trailing ```
    llm_output = llm_output.strip()

    # Parse JSON from model output
    try:
        table_json = json.loads(llm_output)
    except json.JSONDecodeError as e:
        # If model adds extra text after JSON, try to extract just the JSON part
        logger.warning(f"JSON parsing failed at position {e.pos}. Attempting to extract valid JSON...")

        try:
            # Try to find the JSON object by looking for matching braces
            start_idx = llm_output.find('{')
            if start_idx == -1:
                raise ValueError("No JSON object found in output")

            # Count braces to find the end of the JSON object
            brace_count = 0
            end_idx = start_idx
            for i in range(start_idx, len(llm_output)):
                if llm_output[i] == '{':
                    brace_count += 1
                elif llm_output[i] == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        end_idx = i + 1
                        break

            json_str = llm_output[start_idx:end_idx]
            table_json = json.loads(json_str)
            logger.info(f"Successfully extracted JSON from position {start_idx} to {end_idx}")

        except (ValueError, json.JSONDecodeError) as extraction_error:
            logger.error(f"LLM output is not pure JSON and extraction failed. Original error: {e}, Extraction error: {extraction_error}. Output (first 1000 chars): {llm_output[:1000]}", exc_info=True)
            raise

    return table_json


async def process_landingai_async(temp_excel: Path, safe_name: str, output_folder: Path) -> Tuple[str, str, Path]:
    """
    Async wrapper for Landing AI processing.
    Returns: (safe_name, markdown_content, markdown_file_path)
    """
    loop = asyncio.get_event_loop()

    # Run Landing AI in thread pool to avoid blocking
    markdown_content = await loop.run_in_executor(
        None,
        extract_markdown_with_landingai,
        temp_excel
    )

    # Save markdown file
    markdown_file = output_folder / f"{safe_name}.md"
    with open(markdown_file, "w", encoding="utf-8") as f:
        f.write(markdown_content)

    return safe_name, markdown_content, markdown_file


async def process_openai_async(
    table_markdown: str,
    sheet_name: str,
    table_index: int,
    excel_file_name: str,
    file_index: int,
    safe_name: str,
    output_folder: Path
) -> Dict[str, Any]:
    """
    Async wrapper for OpenAI table processing.
    Returns: table_json
    """
    loop = asyncio.get_event_loop()

    # Run OpenAI in thread pool to avoid blocking
    table_json = await loop.run_in_executor(
        None,
        extract_single_table_with_openai,
        table_markdown,
        sheet_name,
        table_index
    )

    # Add metadata
    table_json["excel_file"] = excel_file_name
    table_json["file_index"] = file_index

    # Save JSON file
    json_file = output_folder / f"{safe_name}_table_{table_index}.json"
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(table_json, f, indent=2, ensure_ascii=False)

    return table_json


async def process_vision_analysis_async(
    temp_excel: Path,
    safe_name: str,
    sheet_name: str,
    excel_file_name: str,
    file_index: int,
    openai_api_key: str,
    analyze_gaps: bool = True,
    analyze_similarity: bool = True
) -> Dict[str, Any]:
    """
    Async wrapper for vision-based gap analysis of a single temp sheet.

    Calls process_excel_with_vision() to:
    - Convert sheet to image
    - Analyze with GPT-4 Vision
    - Detect column gaps and table relationships
    - Save results to gap_analysis folder

    Args:
        temp_excel: Path to temp Excel file (single sheet)
        safe_name: Sanitized sheet name for filenames
        sheet_name: Original sheet name
        excel_file_name: Original Excel filename
        file_index: Index of the Excel file being processed
        openai_api_key: OpenAI API key
        analyze_gaps: Enable column gap detection (default: True)
        analyze_similarity: Enable table relationship analysis (default: True)

    Returns:
        Dict with vision analysis results or error information
    """
    try:
        # Call vision processing function
        # Disable file saving in pipeline - we'll save consolidated format later
        result = await process_excel_with_vision(
            excel_path=temp_excel,
            analyze_gaps=analyze_gaps,
            analyze_similarity=analyze_similarity,
            openai_api_key=openai_api_key,
            save_to_file=False
        )

        # Add metadata to result
        result['excel_file'] = excel_file_name
        result['file_index'] = file_index
        result['safe_name'] = safe_name
        from datetime import datetime
        result['processed_at'] = datetime.now().isoformat()

        return result

    except Exception as e:
        logger.error(f"Vision analysis failed for {safe_name}: {e}", exc_info=True)
        return {
            'safe_name': safe_name,
            'sheet_name': sheet_name,
            'excel_file': excel_file_name,
            'file_index': file_index,
            'error': str(e),
            'status': 'failed'
        }


async def process_excel_to_json(
    enable_vision_analysis: bool = True,
    max_sheets_for_vision: int = 10,
    analyze_gaps: bool = True,
    analyze_similarity: bool = True
) -> Dict[str, Any]:
    """
    Main async function to process all Excel files in the input folder and convert them to JSON.
    Uses multi-phase parallel processing:
    - Phase 1: Sync sheet splitting (create all temp files)
    - Phase 1.5: Vision-based gap analysis (optional, enabled by default)
    - Phase 1.6: Intelligent gap column removal (for single tables)
    - Phase 2: Parallel Landing AI processing (all sheets at once)
    - Phase 3: Parallel OpenAI processing (all tables at once)

    Args:
        enable_vision_analysis: Enable GPT-4 Vision analysis for gap detection (default: True)
        max_sheets_for_vision: Maximum number of sheets to analyze with vision (default: 10)
        analyze_gaps: Enable column gap detection (default: True)
        analyze_similarity: Enable table relationship analysis (default: True)

    Returns:
        Dictionary containing processing results
    """
    # Input and output directories
    input_folder = Path("input")
    output_folder = Path("markdown")
    temp_folder = Path("temp_sheets")

    # Create folders if they don't exist
    output_folder.mkdir(parents=True, exist_ok=True)
    temp_folder.mkdir(parents=True, exist_ok=True)

    # Create vision analysis folders if enabled
    gap_analysis_folder = Path("gap_analysis")
    screenshots_folder = Path("screenshots")
    if enable_vision_analysis:
        gap_analysis_folder.mkdir(parents=True, exist_ok=True)
        screenshots_folder.mkdir(parents=True, exist_ok=True)

    # Get all Excel files from input folder
    excel_files = list(input_folder.glob("*.xlsx")) + list(input_folder.glob("*.xls"))
    if not excel_files:
        raise FileNotFoundError(f"No Excel file found in {input_folder}")

    logger.info(f"Found {len(excel_files)} Excel file(s) in {input_folder}")

    try:
        # =================================================================
        # PHASE 1: SYNC SHEET SPLITTING - Create ALL temp files at once
        # =================================================================
        logger.info(f"\n{'='*70}\nPHASE 1: CREATING ALL TEMP SHEET FILES\n{'='*70}\n")

        sheet_metadata = []  # List of (temp_excel, safe_name, sheet_name, excel_file_name, file_index)

        for file_idx, input_excel in enumerate(excel_files, 1):
            logger.info(f"Processing Excel file {file_idx}/{len(excel_files)}: {input_excel.name}")

            try:
                # Get all sheet names from the Excel file
                with pd.ExcelFile(input_excel) as xls:
                    sheet_names = xls.sheet_names

                logger.info(f"  Found {len(sheet_names)} sheet(s): {', '.join(sheet_names)}")

                # Create temp file for each sheet
                for idx, sheet_name in enumerate(sheet_names, 1):
                    excel_basename = input_excel.stem
                    safe_excel_name = sanitize_filename(excel_basename)
                    safe_sheet_name = sanitize_filename(sheet_name, f"sheet_{idx}")
                    safe_name = f"{safe_excel_name}_{safe_sheet_name}"
                    temp_excel = temp_folder / f"{safe_name}.xlsx"

                    # Export sheet to temp Excel file
                    export_sheet_to_single_excel(input_excel, sheet_name, temp_excel)
                    logger.debug(f"    Created: {temp_excel.name}")

                    # Store metadata for Phase 2
                    sheet_metadata.append({
                        'temp_excel': temp_excel,
                        'safe_name': safe_name,
                        'sheet_name': sheet_name,
                        'excel_file_name': input_excel.name,
                        'file_index': file_idx
                    })

            except Exception as e:
                logger.error(f"  ERROR processing Excel file '{input_excel.name}': {e}", exc_info=True)
                continue

        logger.info(f"\nPhase 1 Complete: Created {len(sheet_metadata)} temp sheet files")

        # =================================================================
        # PHASE 1.5: VISION-BASED GAP ANALYSIS (OPTIONAL)
        # =================================================================
        vision_analyses = []
        phase1_5_errors = 0

        if enable_vision_analysis:
            logger.info(f"\n{'='*70}\nPHASE 1.5: VISION-BASED GAP ANALYSIS\n{'='*70}\n")

            # Limit sheets (max 10)
            sheets_to_analyze = sheet_metadata[:max_sheets_for_vision]
            if len(sheet_metadata) > max_sheets_for_vision:
                logger.warning(
                    f"Limiting vision analysis to first {max_sheets_for_vision} sheets "
                    f"(file has {len(sheet_metadata)} sheets)"
                )

            logger.info(f"Analyzing {len(sheets_to_analyze)} sheets with vision...")

            # Track start time for performance monitoring
            import time
            vision_start_time = time.time()

            # Create parallel vision analysis tasks
            vision_tasks = [
                process_vision_analysis_async(
                    temp_excel=metadata['temp_excel'],
                    safe_name=metadata['safe_name'],
                    sheet_name=metadata['sheet_name'],
                    excel_file_name=metadata['excel_file_name'],
                    file_index=metadata['file_index'],
                    openai_api_key=OPENAI_API_KEY,
                    analyze_gaps=analyze_gaps,
                    analyze_similarity=analyze_similarity
                )
                for metadata in sheets_to_analyze
            ]

            # Execute in parallel with error handling
            vision_results = await asyncio.gather(*vision_tasks, return_exceptions=True)

            # Process results (non-blocking - continue even on errors)
            for idx, result in enumerate(vision_results):
                if isinstance(result, Exception):
                    phase1_5_errors += 1
                    logger.error(f"  [ERROR] Vision analysis {idx+1}: {result}")
                    continue

                if result.get('error'):
                    phase1_5_errors += 1
                    logger.error(f"  [ERROR] {result.get('safe_name', 'Unknown')}: {result.get('error')}")
                    continue

                vision_analyses.append(result)
                logger.info(
                    f"  [SUCCESS] {result.get('safe_name', 'Unknown')} - "
                    f"Gaps: {len(result.get('columns_with_gap', []))}, "
                    f"Classification: {result.get('classification', 'unknown')}"
                )

            # Calculate processing time
            vision_duration_ms = int((time.time() - vision_start_time) * 1000)

            logger.info(f"\nPhase 1.5 Complete:")
            logger.info(f"  Success: {len(vision_analyses)} sheets analyzed")
            logger.info(f"  Errors: {phase1_5_errors}")
            logger.info(f"  Processing time: {vision_duration_ms}ms ({vision_duration_ms/1000:.1f}s)")

            # Save consolidated vision analysis per Excel file
            if vision_analyses:
                try:
                    # Group by Excel file
                    per_excel_vision = {}
                    for analysis in vision_analyses:
                        excel_name = analysis.get('excel_file', 'unknown')
                        if excel_name not in per_excel_vision:
                            per_excel_vision[excel_name] = []
                        per_excel_vision[excel_name].append(analysis)

                    # Save consolidated file for each Excel
                    for excel_name, analyses in per_excel_vision.items():
                        safe_excel_name = sanitize_filename(Path(excel_name).stem)
                        consolidated_vision_file = gap_analysis_folder / f"{safe_excel_name}_all_vision.json"

                        # Calculate per-Excel metrics
                        excel_total_sheets = sum(1 for m in sheet_metadata if m['excel_file_name'] == excel_name)
                        excel_failed = sum(1 for a in analyses if a.get('error') or a.get('status') == 'failed')

                        consolidated_data = {
                            "excel_file": excel_name,
                            "total_sheets": excel_total_sheets,
                            "sheets_analyzed": len(analyses),
                            "sheets_failed": excel_failed,
                            "processing_time_ms": vision_duration_ms,
                            "analyses": analyses
                        }

                        with open(consolidated_vision_file, "w", encoding="utf-8") as f:
                            json.dump(consolidated_data, f, indent=2, ensure_ascii=False)

                        logger.info(f"  Consolidated vision analysis saved: {consolidated_vision_file.name}")

                        # Also save lightweight format (matching direct endpoint format) for first sheet
                        if analyses:
                            first_analysis = analyses[0]
                            lightweight_data = {
                                "sheet_name": first_analysis.get("sheet_name", "Unknown"),
                                "gap_summary": first_analysis.get("gap_summary", ""),
                                "columns_with_data": first_analysis.get("columns_with_data", []),
                                "columns_with_gap": first_analysis.get("columns_with_gap", []),
                                "classification": first_analysis.get("classification", "unknown"),
                                "reasoning": first_analysis.get("reasoning", "")
                            }

                            lightweight_file = gap_analysis_folder / f"{safe_excel_name}_lightweight_analysis.json"
                            with open(lightweight_file, "w", encoding="utf-8") as f:
                                json.dump(lightweight_data, f, indent=2, ensure_ascii=False)

                            logger.info(f"  Lightweight analysis saved: {lightweight_file.name}")

                except Exception as e:
                    logger.error(f"Failed to save consolidated vision analysis: {e}", exc_info=True)

        else:
            logger.info(f"\nPhase 1.5 Skipped: Vision analysis disabled")

        # =================================================================
        # PHASE 1.6: INTELLIGENT GAP COLUMN REMOVAL (FOR SINGLE TABLES)
        # =================================================================
        if enable_vision_analysis and vision_analyses:
            logger.info(f"\n{'='*70}\nPHASE 1.6: INTELLIGENT GAP COLUMN REMOVAL\n{'='*70}\n")

            cleaned_count = 0
            skipped_count = 0

            for analysis in vision_analyses:
                classification = analysis.get('classification', '')
                columns_with_gap = analysis.get('columns_with_gap', [])
                safe_name = analysis.get('safe_name', '')

                # Only remove gaps for single tables
                if classification == 'single_table' and columns_with_gap:
                    logger.info(f"Processing single table: {safe_name}")
                    logger.info(f"  Found {len(columns_with_gap)} gap columns: {columns_with_gap}")

                    # Skip first gap, remove the rest
                    if len(columns_with_gap) > 1:
                        gaps_to_remove = columns_with_gap[1:]  # Skip first gap
                        logger.info(f"  Removing gaps (keeping first): {gaps_to_remove}")

                        # Find the corresponding temp Excel file
                        temp_excel_path = None
                        for metadata in sheet_metadata:
                            if metadata['safe_name'] == safe_name:
                                temp_excel_path = metadata['temp_excel']
                                break

                        if temp_excel_path and temp_excel_path.exists():
                            remove_gap_columns_from_excel(temp_excel_path, gaps_to_remove)
                            cleaned_count += 1
                        else:
                            logger.warning(f"  Temp Excel file not found for {safe_name}")
                    else:
                        logger.info(f"  Only 1 gap column, keeping as-is")
                        skipped_count += 1
                else:
                    if classification != 'single_table':
                        logger.debug(f"Skipping {safe_name}: classification is '{classification}' (not single_table)")
                    skipped_count += 1

            logger.info(f"\nPhase 1.6 Complete:")
            logger.info(f"  Cleaned: {cleaned_count} sheets")
            logger.info(f"  Skipped: {skipped_count} sheets")

        # =================================================================
        # PHASE 2: PARALLEL LANDING AI - Process ALL sheets at once
        # =================================================================
        logger.info(f"\n{'='*70}\nPHASE 2: PARALLEL LANDING AI PROCESSING\n{'='*70}\n")
        logger.info(f"Processing {len(sheet_metadata)} sheets in parallel...")

        # Create all Landing AI tasks
        tasks = []
        for metadata in sheet_metadata:
            task = process_landingai_async(
                metadata['temp_excel'],
                metadata['safe_name'],
                output_folder
            )
            tasks.append(task)

        # Run Phase 2 - Wait for all Landing AI tasks to complete
        landingai_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results and prepare for Phase 3
        markdown_data = []  # List of (safe_name, markdown_content, sheet_name, excel_file_name, file_index)
        phase2_errors = 0

        for idx, result in enumerate(landingai_results):
            if isinstance(result, Exception):
                phase2_errors += 1
                logger.error(f"  [ERROR] Sheet {sheet_metadata[idx]['safe_name']}: {result}")
                continue

            safe_name, markdown_content, markdown_file = result
            metadata = sheet_metadata[idx]

            logger.info(f"  [SUCCESS] {safe_name} ({len(markdown_content)} chars)")

            markdown_data.append({
                'safe_name': safe_name,
                'markdown_content': markdown_content,
                'sheet_name': metadata['sheet_name'],
                'excel_file_name': metadata['excel_file_name'],
                'file_index': metadata['file_index']
            })

        logger.info(f"\nPhase 2 Complete:")
        logger.info(f"  Success: {len(markdown_data)} markdown files")
        logger.info(f"  Errors: {phase2_errors}")

        # =================================================================
        # PHASE 3.1: SPLIT ALL MARKDOWN INTO TABLES
        # =================================================================
        logger.info(f"\n{'='*70}\nPHASE 3.1: SPLITTING ALL MARKDOWN INTO TABLES\n{'='*70}\n")

        table_tasks = []  # List of table processing tasks

        for md_data in markdown_data:
            markdown_content = md_data['markdown_content']

            if markdown_content.strip():
                tables = split_markdown_tables(markdown_content)
                logger.info(f"  {md_data['safe_name']}: Found {len(tables)} table(s)")

                for table_idx, table_markdown in enumerate(tables, start=1):
                    table_tasks.append({
                        'table_markdown': table_markdown,
                        'sheet_name': md_data['sheet_name'],
                        'table_index': table_idx,
                        'excel_file_name': md_data['excel_file_name'],
                        'file_index': md_data['file_index'],
                        'safe_name': md_data['safe_name']
                    })

        logger.info(f"\nPhase 3.1 Complete: Found {len(table_tasks)} tables total")

        # =================================================================
        # PHASE 3.2: PARALLEL OPENAI - Process ALL tables at once
        # =================================================================
        logger.info(f"\n{'='*70}\nPHASE 3.2: PARALLEL OPENAI PROCESSING\n{'='*70}\n")
        logger.info(f"Processing {len(table_tasks)} tables in parallel...")

        # Run Phase 3.2
        all_results = []
        phase3_errors = 0

        if table_tasks:
            # Create all OpenAI tasks
            tasks = []
            for task_data in table_tasks:
                task = process_openai_async(
                    task_data['table_markdown'],
                    task_data['sheet_name'],
                    task_data['table_index'],
                    task_data['excel_file_name'],
                    task_data['file_index'],
                    task_data['safe_name'],
                    output_folder
                )
                tasks.append(task)

            # Wait for all OpenAI tasks to complete
            openai_results = await asyncio.gather(*tasks, return_exceptions=True)

            for idx, result in enumerate(openai_results):
                if isinstance(result, Exception):
                    phase3_errors += 1
                    logger.error(f"  [ERROR] Table {idx+1}/{len(table_tasks)}: {result}")
                    continue

                all_results.append(result)
                if (idx + 1) % 10 == 0 or (idx + 1) == len(openai_results):
                    logger.info(f"  [PROGRESS] Processed {idx+1}/{len(table_tasks)} tables")

        logger.info(f"\nPhase 3.2 Complete:")
        logger.info(f"  Success: {len(all_results)} tables")
        logger.info(f"  Errors: {phase3_errors}")

        # =================================================================
        # SAVE CONSOLIDATED RESULTS
        # =================================================================
        logger.info(f"\n{'='*70}\nSAVING CONSOLIDATED RESULTS\n{'='*70}\n")

        # Save consolidated JSON file
        if all_results:
            consolidated_json_file = output_folder / "all_tables_consolidated.json"
            with open(consolidated_json_file, "w", encoding="utf-8") as f:
                json.dump(all_results, f, indent=2, ensure_ascii=False)
            logger.info(f"* CONSOLIDATED JSON SAVED: {consolidated_json_file.name}")
            logger.info(f"* Total tables extracted: {len(all_results)}")

        # Group results by Excel file for per-file JSON
        per_excel_results = {}
        for result in all_results:
            excel_name = result.get('excel_file', 'unknown')
            if excel_name not in per_excel_results:
                per_excel_results[excel_name] = []
            per_excel_results[excel_name].append(result)

        # Save per-Excel JSON files
        per_excel_files = []
        for excel_name, tables in per_excel_results.items():
            if tables:
                safe_excel_name = sanitize_filename(Path(excel_name).stem)
                per_excel_json_file = output_folder / f"{safe_excel_name}_complete.json"

                with open(per_excel_json_file, "w", encoding="utf-8") as f:
                    json.dump(tables, f, indent=2, ensure_ascii=False)

                per_excel_files.append(per_excel_json_file.name)
                logger.info(f"\n* PER-EXCEL JSON SAVED: {per_excel_json_file.name}")
                logger.info(f"  Excel file: {excel_name}")
                logger.info(f"  Tables: {len(tables)}")

        logger.info(f"\n{'='*70}\nPROCESSING COMPLETE!\n{'='*70}")
        logger.info(f"Total Excel files processed: {len(excel_files)}")
        logger.info(f"Total sheets processed: {len(sheet_metadata)}")
        logger.info(f"Total tables extracted: {len(all_results)}")
        logger.info(f"Output folder: {output_folder.absolute()}")
        logger.info(f"{'='*70}\n")

        return {
            "files_processed": len(excel_files),
            "sheets_processed": len(sheet_metadata),
            "tables_extracted": len(all_results),
            "vision_analyses_count": len(vision_analyses) if enable_vision_analysis else 0,
            "vision_analyses": vision_analyses if enable_vision_analysis else [],
            "output_folder": str(output_folder.absolute()),
            "results": all_results,
            "per_excel_files": per_excel_files
        }

    finally:
        # Cleanup temporary files
        #! remove this
        # if temp_folder.exists():
        #     try:
        #         shutil.rmtree(temp_folder)
        #         logger.info(f"Cleaned up temporary sheet files")
        #     except Exception as e:
        #         logger.warning(f"Could not clean up temp folder: {e}")

        # Cleanup screenshots folder (vision analysis artifacts)
        screenshots_folder = Path("screenshots")
        if screenshots_folder.exists():
            try:
                shutil.rmtree(screenshots_folder)
                logger.info(f"Cleaned up screenshot files")
            except Exception as e:
                logger.warning(f"Could not clean up screenshots folder: {e}")
