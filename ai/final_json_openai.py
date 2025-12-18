# Install first (if not done already):
# pip install landingai-ade openai python-dotenv pandas openpyxl

import os
import json
import shutil
from pathlib import Path

from dotenv import load_dotenv
from landingai_ade import LandingAIADE
from openai import OpenAI
import pandas as pd
from logger import AppLogger

# ----------------- Load secrets from .env -----------------
# .env example:
# LANDINGAI_API_KEY=xxxxxx  (optional, defaults to hardcoded key)
# OPENAI_API_KEY=yyyyyy
INPUT_FOLDER = Path("input")

load_dotenv(".env")

# Initialize logger
logger = AppLogger.get_logger(__file__)

LANDINGAI_API_KEY = os.getenv("LANDINGAI_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY is not set in .env")

# ----------------- LandingAI ADE: get markdown -----------------

client = LandingAIADE(
    apikey=LANDINGAI_API_KEY,
)

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

logger.info(f"Found {len(excel_files)} Excel file(s) in {input_folder}")

# ----------------- Helper Functions -----------------

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


def extract_markdown_with_landingai(excel_file: Path) -> str:
    """Extract markdown content from Excel file using Landing AI ADE."""
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


# ----------------- OpenAI LLM: extract table entities -----------------

def split_markdown_tables(markdown_text: str) -> list:
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


def extract_single_table_with_openai(table_markdown: str, sheet_name: str, table_index: int) -> dict:
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
        logger.warning(f"JSON parsing failed at position {e.pos}. Attempting to extract valid JSON...")

        try:
            # Try to find the JSON object by looking for matching braces
            # Find the first '{' and try to extract a valid JSON object
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
            # If extraction also fails, show the error and output
            logger.error(f"LLM output is not pure JSON and extraction failed. Original error: {e}, Extraction error: {extraction_error}. Output (first 1000 chars): {llm_output[:1000]}", exc_info=True)
            raise

    return table_json


# ----------------- Process all Excel files -----------------

try:
    all_results = []
    total_files = len(excel_files)

    # Process each Excel file
    for file_idx, input_excel in enumerate(excel_files, 1):
        logger.info(f"\n{'#'*70}\n# Processing Excel File {file_idx}/{total_files}: {input_excel.name}\n{'#'*70}")

        try:
            # Get all sheet names from the Excel file
            with pd.ExcelFile(input_excel) as xls:
                sheet_names = xls.sheet_names

            logger.info(f"Found {len(sheet_names)} sheet(s): {', '.join(sheet_names)}\n")

            # Process each sheet in the Excel file
            for idx, sheet_name in enumerate(sheet_names, 1):
                logger.info(f"\n{'='*60}\nProcessing Sheet {idx}/{len(sheet_names)}: {sheet_name}\n{'='*60}")

                try:
                    # Step 1: Export sheet to single Excel file
                    excel_basename = input_excel.stem
                    safe_excel_name = sanitize_filename(excel_basename)
                    safe_sheet_name = sanitize_filename(sheet_name, f"sheet_{idx}")
                    safe_name = f"{safe_excel_name}_{safe_sheet_name}"
                    temp_excel = temp_folder / f"{safe_name}.xlsx"

                    logger.debug(f"  -> Exporting sheet to temporary Excel file...")
                    export_sheet_to_single_excel(input_excel, sheet_name, temp_excel)
                    logger.debug(f"     Created: {temp_excel.name}")

                    # Step 2: Extract markdown with Landing AI
                    logger.info(f"  -> Sending to Landing AI ADE...")
                    markdown_content = extract_markdown_with_landingai(temp_excel)
                    logger.info(f"     Received markdown ({len(markdown_content)} chars)")

                    # Step 3: Save markdown to markdown_json folder
                    markdown_file = output_folder / f"{safe_name}.md"
                    with open(markdown_file, "w", encoding="utf-8") as f:
                        f.write(markdown_content)
                    logger.debug(f"     Markdown saved to: {markdown_file}")

                    # Step 4: Split markdown into individual tables
                    if markdown_content.strip():
                        logger.info(f"  -> Splitting markdown into individual tables...")
                        tables = split_markdown_tables(markdown_content)
                        logger.info(f"     Found {len(tables)} table(s)")

                        # Step 5: Extract each table separately with OpenAI
                        if tables:
                            logger.info(f"  -> Extracting tables with OpenAI...")
                            for table_idx, table_markdown in enumerate(tables, start=1):
                                try:
                                    logger.info(f"     Processing table {table_idx}/{len(tables)}...")

                                    # Extract table with LLM
                                    table_json = extract_single_table_with_openai(
                                        table_markdown,
                                        sheet_name,
                                        table_idx
                                    )

                                    # Add metadata about the source Excel file
                                    table_json["excel_file"] = input_excel.name
                                    table_json["file_index"] = file_idx

                                    # Save each table as a separate JSON file
                                    json_file = output_folder / f"{safe_name}_table_{table_idx}.json"
                                    with open(json_file, "w", encoding="utf-8") as f:
                                        json.dump(table_json, f, indent=2, ensure_ascii=False)
                                    logger.debug(f"       JSON saved to: {json_file.name}")

                                    # Add to consolidated results
                                    all_results.append(table_json)

                                except Exception as e:
                                    logger.error(f"       ERROR processing table {table_idx}: {e}", exc_info=True)
                                    continue

                            logger.info(f"     Successfully extracted {len(tables)} table(s)")
                        else:
                            logger.info(f"     No tables found in markdown")
                    else:
                        logger.info(f"     No content to process for this sheet")

                except Exception as e:
                    logger.error(f"  ERROR processing sheet '{sheet_name}': {e}", exc_info=True)
                    continue

        except Exception as e:
            logger.error(f"ERROR processing Excel file '{input_excel.name}': {e}", exc_info=True)
            continue

    # Save consolidated JSON file with all tables from all sheets from all Excel files
    if all_results:
        consolidated_json_file = output_folder / "all_tables_consolidated.json"
        with open(consolidated_json_file, "w", encoding="utf-8") as f:
            json.dump(all_results, f, indent=2, ensure_ascii=False)
        logger.info(f"\n{'*'*70}\n* CONSOLIDATED JSON SAVED: {consolidated_json_file.name}\n* Total tables extracted: {len(all_results)}\n{'*'*70}")

    logger.info(f"\n{'='*60}\nProcessing Complete!\n{'='*60}")
    logger.info(f"Total Excel files processed: {total_files}")
    logger.info(f"Total tables extracted: {len(all_results)}")
    logger.info(f"Output folder: {output_folder.absolute()}")
    logger.info(f"{'='*60}\n")

finally:
    # Cleanup temporary files
    if temp_folder.exists():
        try:
            shutil.rmtree(temp_folder)
            logger.info(f"Cleaned up temporary files")
        except Exception as e:
            logger.warning(f"Could not clean up temp folder: {e}")
