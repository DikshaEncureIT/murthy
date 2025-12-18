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

# Load environment variables
load_dotenv(".env")

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
    """Export a single sheet to a new Excel file."""
    try:
        df = pd.read_excel(excel_path, sheet_name=sheet_name)
        df.to_excel(output_path, index=False, sheet_name=sheet_name)
        return output_path
    except Exception as e:
        raise RuntimeError(f"Error exporting sheet '{sheet_name}': {e}")


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

CRITICAL: Return ONLY valid JSON with NO explanations, NO markdown formatting, NO additional text before or after the JSON.

Extract the table in this exact structure:

{{
  "sheet_name": "{sheet_name}",
  "table_index": {table_index},
  "title": "<optional table title or empty string>",
  "headers": ["col1", "col2", ...],
  "rows": [
    ["row1_col1", "row1_col2", ...],
    ["row2_col1", "row2_col2", ...]
  ]
}}

IMPORTANT: Your response must start with {{ and end with }}. Do not include any text before or after the JSON object.

Table markdown:
\"\"\"
{table_markdown}
\"\"\"
"""

    # OpenAI Chat Completion API
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a helpful assistant that extracts table data into JSON format. Always respond with valid JSON only."},
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
        print(f"Warning: JSON parsing failed at position {e.pos}. Attempting to extract valid JSON...")

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
            print(f"Successfully extracted JSON from position {start_idx} to {end_idx}")

        except (ValueError, json.JSONDecodeError) as extraction_error:
            print("LLM output is not pure JSON and extraction failed:")
            print(f"Original error: {e}")
            print(f"Extraction error: {extraction_error}")
            print(f"Output (first 1000 chars):\n{llm_output[:1000]}")
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


async def process_excel_to_json() -> Dict[str, Any]:
    """
    Main async function to process all Excel files in the input folder and convert them to JSON.
    Uses 3-phase parallel processing:
    - Phase 1: Sync sheet splitting (create all temp files)
    - Phase 2: Parallel Landing AI processing (all sheets at once)
    - Phase 3: Parallel OpenAI processing (all tables at once)

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

    # Get all Excel files from input folder
    excel_files = list(input_folder.glob("*.xlsx")) + list(input_folder.glob("*.xls"))
    if not excel_files:
        raise FileNotFoundError(f"No Excel file found in {input_folder}")

    print(f"Found {len(excel_files)} Excel file(s) in {input_folder}")

    try:
        # =================================================================
        # PHASE 1: SYNC SHEET SPLITTING - Create ALL temp files at once
        # =================================================================
        print(f"\n{'='*70}")
        print(f"PHASE 1: CREATING ALL TEMP SHEET FILES")
        print(f"{'='*70}\n")

        sheet_metadata = []  # List of (temp_excel, safe_name, sheet_name, excel_file_name, file_index)

        for file_idx, input_excel in enumerate(excel_files, 1):
            print(f"Processing Excel file {file_idx}/{len(excel_files)}: {input_excel.name}")

            try:
                # Get all sheet names from the Excel file
                with pd.ExcelFile(input_excel) as xls:
                    sheet_names = xls.sheet_names

                print(f"  Found {len(sheet_names)} sheet(s): {', '.join(sheet_names)}")

                # Create temp file for each sheet
                for idx, sheet_name in enumerate(sheet_names, 1):
                    excel_basename = input_excel.stem
                    safe_excel_name = sanitize_filename(excel_basename)
                    safe_sheet_name = sanitize_filename(sheet_name, f"sheet_{idx}")
                    safe_name = f"{safe_excel_name}_{safe_sheet_name}"
                    temp_excel = temp_folder / f"{safe_name}.xlsx"

                    # Export sheet to temp Excel file
                    export_sheet_to_single_excel(input_excel, sheet_name, temp_excel)
                    print(f"    Created: {temp_excel.name}")

                    # Store metadata for Phase 2
                    sheet_metadata.append({
                        'temp_excel': temp_excel,
                        'safe_name': safe_name,
                        'sheet_name': sheet_name,
                        'excel_file_name': input_excel.name,
                        'file_index': file_idx
                    })

            except Exception as e:
                print(f"  ERROR processing Excel file '{input_excel.name}': {e}")
                continue

        print(f"\nPhase 1 Complete: Created {len(sheet_metadata)} temp sheet files")

        # =================================================================
        # PHASE 2: PARALLEL LANDING AI - Process ALL sheets at once
        # =================================================================
        print(f"\n{'='*70}")
        print(f"PHASE 2: PARALLEL LANDING AI PROCESSING")
        print(f"{'='*70}\n")
        print(f"Processing {len(sheet_metadata)} sheets in parallel...")

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
                print(f"  [ERROR] Sheet {sheet_metadata[idx]['safe_name']}: {result}")
                continue

            safe_name, markdown_content, markdown_file = result
            metadata = sheet_metadata[idx]

            print(f"  [SUCCESS] {safe_name} ({len(markdown_content)} chars)")

            markdown_data.append({
                'safe_name': safe_name,
                'markdown_content': markdown_content,
                'sheet_name': metadata['sheet_name'],
                'excel_file_name': metadata['excel_file_name'],
                'file_index': metadata['file_index']
            })

        print(f"\nPhase 2 Complete:")
        print(f"  Success: {len(markdown_data)} markdown files")
        print(f"  Errors: {phase2_errors}")

        # =================================================================
        # PHASE 3.1: SPLIT ALL MARKDOWN INTO TABLES
        # =================================================================
        print(f"\n{'='*70}")
        print(f"PHASE 3.1: SPLITTING ALL MARKDOWN INTO TABLES")
        print(f"{'='*70}\n")

        table_tasks = []  # List of table processing tasks

        for md_data in markdown_data:
            markdown_content = md_data['markdown_content']

            if markdown_content.strip():
                tables = split_markdown_tables(markdown_content)
                print(f"  {md_data['safe_name']}: Found {len(tables)} table(s)")

                for table_idx, table_markdown in enumerate(tables, start=1):
                    table_tasks.append({
                        'table_markdown': table_markdown,
                        'sheet_name': md_data['sheet_name'],
                        'table_index': table_idx,
                        'excel_file_name': md_data['excel_file_name'],
                        'file_index': md_data['file_index'],
                        'safe_name': md_data['safe_name']
                    })

        print(f"\nPhase 3.1 Complete: Found {len(table_tasks)} tables total")

        # =================================================================
        # PHASE 3.2: PARALLEL OPENAI - Process ALL tables at once
        # =================================================================
        print(f"\n{'='*70}")
        print(f"PHASE 3.2: PARALLEL OPENAI PROCESSING")
        print(f"{'='*70}\n")
        print(f"Processing {len(table_tasks)} tables in parallel...")

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
                    print(f"  [ERROR] Table {idx+1}/{len(table_tasks)}: {result}")
                    continue

                all_results.append(result)
                if (idx + 1) % 10 == 0 or (idx + 1) == len(openai_results):
                    print(f"  [PROGRESS] Processed {idx+1}/{len(table_tasks)} tables")

        print(f"\nPhase 3.2 Complete:")
        print(f"  Success: {len(all_results)} tables")
        print(f"  Errors: {phase3_errors}")

        # =================================================================
        # SAVE CONSOLIDATED RESULTS
        # =================================================================
        print(f"\n{'='*70}")
        print(f"SAVING CONSOLIDATED RESULTS")
        print(f"{'='*70}\n")

        # Save consolidated JSON file
        if all_results:
            consolidated_json_file = output_folder / "all_tables_consolidated.json"
            with open(consolidated_json_file, "w", encoding="utf-8") as f:
                json.dump(all_results, f, indent=2, ensure_ascii=False)
            print(f"* CONSOLIDATED JSON SAVED: {consolidated_json_file.name}")
            print(f"* Total tables extracted: {len(all_results)}")

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
                print(f"\n* PER-EXCEL JSON SAVED: {per_excel_json_file.name}")
                print(f"  Excel file: {excel_name}")
                print(f"  Tables: {len(tables)}")

        print(f"\n{'='*70}")
        print(f"PROCESSING COMPLETE!")
        print(f"{'='*70}")
        print(f"Total Excel files processed: {len(excel_files)}")
        print(f"Total sheets processed: {len(sheet_metadata)}")
        print(f"Total tables extracted: {len(all_results)}")
        print(f"Output folder: {output_folder.absolute()}")
        print(f"{'='*70}\n")

        return {
            "files_processed": len(excel_files),
            "sheets_processed": len(sheet_metadata),
            "tables_extracted": len(all_results),
            "output_folder": str(output_folder.absolute()),
            "results": all_results,
            "per_excel_files": per_excel_files
        }

    finally:
        # Cleanup temporary files
        if temp_folder.exists():
            try:
                shutil.rmtree(temp_folder)
                print(f"Cleaned up temporary files")
            except Exception as e:
                print(f"Warning: Could not clean up temp folder: {e}")
