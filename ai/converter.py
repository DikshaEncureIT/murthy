import os
import json
import shutil
from pathlib import Path
from typing import Dict, Any, List

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


def process_excel_to_json() -> Dict[str, Any]:
    """
    Main function to process all Excel files in the input folder and convert them to JSON.

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
        all_results = []
        total_files = len(excel_files)
        per_excel_results = {}  # Dictionary to store results per Excel file

        # Process each Excel file
        for file_idx, input_excel in enumerate(excel_files, 1):
            print(f"\n{'#'*70}")
            print(f"# Processing Excel File {file_idx}/{total_files}: {input_excel.name}")
            print(f"{'#'*70}")

            # Initialize results list for this Excel file
            per_excel_results[input_excel.name] = []

            try:
                # Get all sheet names from the Excel file
                with pd.ExcelFile(input_excel) as xls:
                    sheet_names = xls.sheet_names

                print(f"Found {len(sheet_names)} sheet(s): {', '.join(sheet_names)}\n")

                # Process each sheet in the Excel file
                for idx, sheet_name in enumerate(sheet_names, 1):
                    print(f"\n{'='*60}")
                    print(f"Processing Sheet {idx}/{len(sheet_names)}: {sheet_name}")
                    print(f"{'='*60}")

                    try:
                        # Step 1: Export sheet to single Excel file
                        excel_basename = input_excel.stem
                        safe_excel_name = sanitize_filename(excel_basename)
                        safe_sheet_name = sanitize_filename(sheet_name, f"sheet_{idx}")
                        safe_name = f"{safe_excel_name}_{safe_sheet_name}"
                        temp_excel = temp_folder / f"{safe_name}.xlsx"

                        print(f"  -> Exporting sheet to temporary Excel file...")
                        export_sheet_to_single_excel(input_excel, sheet_name, temp_excel)
                        print(f"     Created: {temp_excel.name}")

                        # Step 2: Extract markdown with Landing AI
                        print(f"  -> Sending to Landing AI ADE...")
                        markdown_content = extract_markdown_with_landingai(temp_excel)
                        print(f"     Received markdown ({len(markdown_content)} chars)")

                        # Step 3: Save markdown to markdown folder
                        markdown_file = output_folder / f"{safe_name}.md"
                        with open(markdown_file, "w", encoding="utf-8") as f:
                            f.write(markdown_content)
                        print(f"     Markdown saved to: {markdown_file}")

                        # Step 4: Split markdown into individual tables
                        if markdown_content.strip():
                            print(f"  -> Splitting markdown into individual tables...")
                            tables = split_markdown_tables(markdown_content)
                            print(f"     Found {len(tables)} table(s)")

                            # Step 5: Extract each table separately with OpenAI
                            if tables:
                                print(f"  -> Extracting tables with OpenAI...")
                                for table_idx, table_markdown in enumerate(tables, start=1):
                                    try:
                                        print(f"     Processing table {table_idx}/{len(tables)}...")

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
                                        print(f"       JSON saved to: {json_file.name}")

                                        # Add to consolidated results
                                        all_results.append(table_json)
                                        # Add to per-Excel results
                                        per_excel_results[input_excel.name].append(table_json)

                                    except Exception as e:
                                        print(f"       ERROR processing table {table_idx}: {e}")
                                        continue

                                print(f"     Successfully extracted {len(tables)} table(s)")
                            else:
                                print(f"     No tables found in markdown")
                        else:
                            print(f"     No content to process for this sheet")

                    except Exception as e:
                        print(f"  ERROR processing sheet '{sheet_name}': {e}")
                        continue

            except Exception as e:
                print(f"ERROR processing Excel file '{input_excel.name}': {e}")
                continue

        # Save consolidated JSON file with all tables from all sheets from all Excel files
        if all_results:
            consolidated_json_file = output_folder / "all_tables_consolidated.json"
            with open(consolidated_json_file, "w", encoding="utf-8") as f:
                json.dump(all_results, f, indent=2, ensure_ascii=False)
            print(f"\n{'*'*70}")
            print(f"* CONSOLIDATED JSON SAVED: {consolidated_json_file.name}")
            print(f"* Total tables extracted: {len(all_results)}")
            print(f"{'*'*70}")

        # Save per-Excel JSON files
        per_excel_files = []
        for excel_name, tables in per_excel_results.items():
            if tables:
                # Create safe filename from Excel name
                safe_excel_name = sanitize_filename(Path(excel_name).stem)
                per_excel_json_file = output_folder / f"{safe_excel_name}_complete.json"

                with open(per_excel_json_file, "w", encoding="utf-8") as f:
                    json.dump(tables, f, indent=2, ensure_ascii=False)

                per_excel_files.append(per_excel_json_file.name)
                print(f"\n{'*'*70}")
                print(f"* PER-EXCEL JSON SAVED: {per_excel_json_file.name}")
                print(f"* Excel file: {excel_name}")
                print(f"* Tables in this file: {len(tables)}")
                print(f"{'*'*70}")

        print(f"\n{'='*60}")
        print(f"Processing Complete!")
        print(f"{'='*60}")
        print(f"Total Excel files processed: {total_files}")
        print(f"Total tables extracted: {len(all_results)}")
        print(f"Output folder: {output_folder.absolute()}")
        print(f"{'='*60}\n")

        return {
            "files_processed": total_files,
            "tables_extracted": len(all_results),
            "output_folder": str(output_folder.absolute()),
            "results": all_results,
            "per_excel_files": per_excel_files if 'per_excel_files' in locals() else []
        }

    finally:
        # Cleanup temporary files
        if temp_folder.exists():
            try:
                shutil.rmtree(temp_folder)
                print(f"Cleaned up temporary files")
            except Exception as e:
                print(f"Warning: Could not clean up temp folder: {e}")
