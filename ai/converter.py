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

# Load environment variables
load_dotenv(".env")

# Initialize logger
logger = AppLogger.get_logger(__file__)

LANDINGAI_API_KEY = os.getenv("LANDINGAI_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY is not set in .env")


def cleanup_previous_data():
    """
    Clean up all previous conversion data before starting a new conversion.
    Removes:
    - markdown/ folder (output JSON files)
    - temp_sheets/ folder (temporary Excel files)
    """
    import time

    folders_to_clean = [
        Path("markdown"),
        Path("temp_sheets"),
    ]

    for folder in folders_to_clean:
        if folder.exists():
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    shutil.rmtree(folder)
                    logger.info(f"Cleaned up previous data: {folder}/")
                    break
                except Exception as e:
                    if attempt < max_retries - 1:
                        logger.debug(f"Retry {attempt + 1}/{max_retries} cleaning {folder}/: {e}")
                        time.sleep(1)  # Wait before retry
                    else:
                        logger.warning(f"Could not clean up {folder}/ after {max_retries} attempts: {e}")

    logger.info("Previous conversion data cleanup completed")


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

    user_instruction = f"""
You will receive one or more tables from an Excel sheet "{sheet_name}" in Markdown format.

TASK:
Extract ALL tables with 100% accuracy and return ONLY valid JSON.

RULES (STRICT):
1. Output ONLY JSON — no explanations, no markdown, no extra text.
2. Extract EVERY row exactly as shown:
   - headers
   - sub-headers
   - category rows
   - data rows
3. Preserve exact cell values. Do NOT infer, merge, rename, or skip anything.
4. Empty cells must be returned as empty strings "".
5. If multiple tables exist, extract EACH table separately.
6. Maintain correct table boundaries and row alignment.
7. Headers must be detected accurately and aligned with their rows.
8. Do NOT combine multiple tables into one.
9. Do NOT include sheet_name or table_index in the output.

OUTPUT FORMAT:
Return a nested JSON structure that represents the table data naturally.

Follow the examples below strictly.

════════════════════════════════════
EXAMPLE 1
════════════════════════════════════

INPUT (HTML/MARKDOWN):
<a id='Borrower -B2:E6-chunk'></a>

<table id='Borrower -B2:E6'>
  <tr>
    <td id='Borrower -B2'>Referrer</td>
    <td id='Borrower -C2'>Name </td>
    <td id='Borrower -D2'>Richard Woodhead</td>
    <td id='Borrower -E2'></td>
  </tr>
  <tr>
    <td id='Borrower -B3'></td>
    <td id='Borrower -C3'>Company Name </td>
    <td id='Borrower -D3'>GPS Investment Fund Limited</td>
    <td id='Borrower -E3'> </td>
  </tr>
  <tr>
    <td id='Borrower -B4'></td>
    <td id='Borrower -C4'>ACN</td>
    <td id='Borrower -D4'></td>
    <td id='Borrower -E4'></td>
  </tr>
  <tr>
    <td id='Borrower -B5'></td>
    <td id='Borrower -C5'>Tel</td>
    <td id='Borrower -D5'></td>
    <td id='Borrower -E5'></td>
  </tr>
  <tr>
    <td id='Borrower -B6'></td>
    <td id='Borrower -C6'>Email </td>
    <td id='Borrower -D6'>Richard@gpsinvest.com.au</td>
    <td id='Borrower -E6'></td>
  </tr>
</table>

<a id='Borrower -B9:D24-chunk'></a>

<table id='Borrower -B9:D24'>
  <tr>
    <td id='Borrower -B9'>Company Borrower</td>
    <td id='Borrower -C9'>Company Name </td>
    <td id='Borrower -D9'>GLENAURA HOLDINGS PTY LTD</td>
  </tr>
  <tr>
    <td id='Borrower -B10'></td>
    <td id='Borrower -C10'>ACN </td>
    <td id='Borrower -D10'>620 269 294</td>
  </tr>
  <tr>
    <td id='Borrower -B11'></td>
    <td id='Borrower -C11'>ABN</td>
    <td id='Borrower -D11'>56 620 269 294</td>
  </tr>
  <tr>
    <td id='Borrower -B12'></td>
    <td id='Borrower -C12'>Date of ABN</td>
    <td id='Borrower -D12'>2017-07-05 00:00:00</td>
  </tr>
  <tr>
    <td id='Borrower -B13'></td>
    <td id='Borrower -C13'>Date of GST </td>
    <td id='Borrower -D13'>2017-07-05 00:00:00</td>
  </tr>
  <tr>
    <td id='Borrower -B14'></td>
    <td id='Borrower -C14'>Registered Office</td>
    <td id='Borrower -D14'>QLD 4213</td>
  </tr>
  <tr>
    <td id='Borrower -B15'></td>
    <td id='Borrower -C15'>Director 1</td>
    <td id='Borrower -D15'>Giuseppe Augello</td>
  </tr>
  <tr>
    <td id='Borrower -B16'></td>
    <td id='Borrower -C16'>Director 2</td>
    <td id='Borrower -D16'>Director 2</td>
  </tr>
  <tr>
    <td id='Borrower -B17'></td>
    <td id='Borrower -C17'>Director 3</td>
    <td id='Borrower -D17'>Director 3</td>
  </tr>
  <tr>
    <td id='Borrower -B18'></td>
    <td id='Borrower -C18'>Director 4</td>
    <td id='Borrower -D18'>Director 4</td>
  </tr>
  <tr>
    <td id='Borrower -B19'></td>
    <td id='Borrower -C19'>Shareholder 1</td>
    <td id='Borrower -D19'></td>
  </tr>
  <tr>
    <td id='Borrower -B20'></td>
    <td id='Borrower -C20'>Shareholder 2</td>
    <td id='Borrower -D20'></td>
  </tr>
  <tr>
    <td id='Borrower -B21'></td>
    <td id='Borrower -C21'>Shareholder 3</td>
    <td id='Borrower -D21'></td>
  </tr>
  <tr>
    <td id='Borrower -B22'></td>
    <td id='Borrower -C22'>Shareholder 4</td>
    <td id='Borrower -D22'></td>
  </tr>
  <tr>
    <td id='Borrower -B23'></td>
    <td id='Borrower -C23'>Proof of Income</td>
    <td id='Borrower -D23'></td>
  </tr>
  <tr>
    <td id='Borrower -B24'></td>
    <td id='Borrower -C24'>Credit History </td>
    <td id='Borrower -D24'></td>
  </tr>
</table>

OUTPUT (JSON):
{{{{
  "Referrer": {{{{
    "Name": "Richard Woodhead",
    "Company Name": "GPS Investment Fund Limited",
    "ACN": "",
    "Tel": "",
    "Email": "Richard@gpsinvest.com.au"
  }}}},
  "Company Borrower": {{{{
    "Company Name": "GLENAURA HOLDINGS PTY LTD",
    "ACN": "620 269 294",
    "ABN": "56 620 269 294",
    "Date of ABN": "5-Jul-17",
    "Date of GST": "5-Jul-17",
    "Registered Office": "QLD 4213",
    "Director 1": "Giuseppe Augello",
    "Director 2": "Director 2",
    "Director 3": "Director 3",
    "Director 4": "Director 4",
    "Shareholder 1": "",
    "Shareholder 2": "",
    "Shareholder 3": "",
    "Shareholder 4": "",
    "Proof of Income": "",
    "Credit History": ""
  }}}}
}}}}

════════════════════════════════════
EXAMPLE 2
════════════════════════════════════

INPUT (HTML/MARKDOWN):

<a id='Feasibility-B34:B34-chunk'></a>

<table id='Feasibility-B34:B34'>
  <tr>
    <td id='Feasibility-B34'>Feasibility </td>
  </tr>
</table>

<a id='Feasibility-H36:I43-chunk'></a>

<table id='Feasibility-H36:I43'>
  <tr>
    <td id='Feasibility-H36'>Presales/ Exit</td>
    <td id='Feasibility-I36'></td>
  </tr>
  <tr>
    <td id='Feasibility-H37'>Stock Destription </td>
    <td id='Feasibility-I37'>Lots Sold</td>
  </tr>
  <tr>
    <td id='Feasibility-H38'>1 Br </td>
    <td id='Feasibility-I38'>1</td>
  </tr>
  <tr>
    <td id='Feasibility-H39'>3 bed</td>
    <td id='Feasibility-I39'>0</td>
  </tr>
  <tr>
    <td id='Feasibility-H40'>2 bed</td>
    <td id='Feasibility-I40'>0</td>
  </tr>
  <tr>
    <td id='Feasibility-H41'>2 bed</td>
    <td id='Feasibility-I41'>0</td>
  </tr>
  <tr>
    <td id='Feasibility-H42'>MANAGE RIGHTS</td>
    <td id='Feasibility-I42'>0</td>
  </tr>
  <tr>
    <td id='Feasibility-H43'></td>
    <td id='Feasibility-I43'>1</td>
  </tr>
</table>

<a id='Feasibility-B37:F43-chunk'></a>

<table id='Feasibility-B37:F43'>
  <tr>
    <td id='Feasibility-B37'>Stock Description </td>
    <td id='Feasibility-C37'></td>
    <td id='Feasibility-D37'>No. Lots </td>
    <td id='Feasibility-E37'>Gross Revenue</td>
    <td id='Feasibility-F37'>Per Lot </td>
  </tr>
  <tr>
    <td id='Feasibility-B38'>1 Br </td>
    <td id='Feasibility-C38'></td>
    <td id='Feasibility-D38'>3</td>
    <td id='Feasibility-E38'>795000</td>
    <td id='Feasibility-F38'>265000</td>
  </tr>
  <tr>
    <td id='Feasibility-B39'>3 bed</td>
    <td id='Feasibility-C39'></td>
    <td id='Feasibility-D39'>3</td>
    <td id='Feasibility-E39'>1005000</td>
    <td id='Feasibility-F39'>335000</td>
  </tr>
  <tr>
    <td id='Feasibility-B40'>2 bed</td>
    <td id='Feasibility-C40'></td>
    <td id='Feasibility-D40'>11</td>
    <td id='Feasibility-E40'>3289000</td>
    <td id='Feasibility-F40'>299000</td>
  </tr>
  <tr>
    <td id='Feasibility-B41'>2 bed</td>
    <td id='Feasibility-C41'></td>
    <td id='Feasibility-D41'>11</td>
    <td id='Feasibility-E41'>3377000</td>
    <td id='Feasibility-F41'>307000</td>
  </tr>
  <tr>
    <td id='Feasibility-B42'>MANAGE RIGHTS</td>
    <td id='Feasibility-C42'>1 X 202K</td>
    <td id='Feasibility-D42'>0</td>
    <td id='Feasibility-E42'>0</td>
    <td id='Feasibility-F42'>#DIV/0!</td>
  </tr>
  <tr>
    <td id='Feasibility-B43'>Gross Realisation </td>
    <td id='Feasibility-C43'></td>
    <td id='Feasibility-D43'>28</td>
    <td id='Feasibility-E43'>8466000</td>
    <td id='Feasibility-F43'>302357.1428571428</td>
  </tr>
</table>

<a id='Feasibility-K37:L43-chunk'></a>

<table id='Feasibility-K37:L43'>
  <tr>
    <td id='Feasibility-K37'>Value </td>
    <td id='Feasibility-L37'>% Sold</td>
  </tr>
  <tr>
    <td id='Feasibility-K38'>0</td>
    <td id='Feasibility-L38'>0</td>
  </tr>
  <tr>
    <td id='Feasibility-K39'>0</td>
    <td id='Feasibility-L39'>0</td>
  </tr>
  <tr>
    <td id='Feasibility-K40'>0</td>
    <td id='Feasibility-L40'>0</td>
  </tr>
  <tr>
    <td id='Feasibility-K41'>0</td>
    <td id='Feasibility-L41'>0</td>
  </tr>
  <tr>
    <td id='Feasibility-K42'>0</td>
    <td id='Feasibility-L42'>0</td>
  </tr>
  <tr>
    <td id='Feasibility-K43'>0</td>
    <td id='Feasibility-L43'>0</td>
  </tr>
</table>


OUTPUT (JSON):
{{{{
  "Feasibility": {{{{
    "Stock Description": [
      {{{{
        "Type": "1 Br",
        "No. Lots": 3,
        "Gross Revenue": "$795,000",
        "Per Lot": "$265,000"
      }}}},
      {{{{
        "Type": "3 bed",
        "No. Lots": 3,
        "Gross Revenue": "$1,005,000",
        "Per Lot": "$335,000"
      }}}},
      {{{{
        "Type": "2 bed",
        "No. Lots": 11,
        "Gross Revenue": "$3,289,000",
        "Per Lot": "$299,000"
      }}}},
      {{{{
        "Type": "2 bed",
        "No. Lots": 11,
        "Gross Revenue": "$3,377,000",
        "Per Lot": "$307,000"
      }}}},
      {{{{
        "Type": "MANAGE RIGHTS",
        "No. Lots": "1 X 202K",
        "Gross Revenue": "$-",
        "Per Lot": "#DIV/0!"
      }}}}
    ],
    "Gross Realisation": {{{{
      "Total Lots": 28,
      "Total Gross Revenue": "$8,466,000",
      "Average Per Lot": "302,357"
    }}}}
  }}}},
  "Presales / Exit": {{{{
    "Stock Description": [
      {{{{
        "Type": "1 Br",
        "Lots Sold": 1,
        "Value": "$-",
        "% Sold": "0%"
      }}}},
      {{{{
        "Type": "3 bed",
        "Lots Sold": "-",
        "Value": "$-",
        "% Sold": "0%"
      }}}},
      {{{{
        "Type": "2 bed",
        "Lots Sold": "-",
        "Value": "$-",
        "% Sold": "0%"
      }}}},
      {{{{
        "Type": "2 bed",
        "Lots Sold": "-",
        "Value": "$-",
        "% Sold": "0%"
      }}}},
      {{{{
        "Type": "MANAGE RIGHTS",
        "Lots Sold": 1,
        "Value": "$-",
        "% Sold": "0%"
      }}}}
    ]
  }}}}
}}}}

════════════════════════════════════
EXAMPLE 3
════════════════════════════════════

INPUT (HTML/MARKDOWN):

<table id='Document List-B5:S53'>
  <tr>
    <td id='Document List-B5' colspan='2'>Internal</td>
    <td id='Document List-D5'>Date Rec'd</td>
    <td id='Document List-E5' colspan='2'>Property Details</td>
    <td id='Document List-G5'>Date Rec'd</td>
    <td id='Document List-H5' colspan='2'>Borrower &amp; Guarantor Details</td>
    <td id='Document List-J5'>Date Rec'd</td>
    <td id='Document List-K5' colspan='2'>Project Documents</td>
    <td id='Document List-M5'>Date Rec'd</td>
    <td id='Document List-N5' colspan='2'>Financial Info</td>
    <td id='Document List-P5'>Date Rec'd</td>
    <td id='Document List-Q5' colspan='2'>Loan Submission</td>
    <td id='Document List-S5'>Date Rec'd</td>
  </tr>
  <tr>
    <td id='Document List-B6'>Development Loan Summary - Eagleby</td>
    <td id='Document List-C6'></td>
    <td id='Document List-D6'>2017-08-18 00:00:00</td>
    <td id='Document List-E6'>COS - Acacia Waters</td>
    <td id='Document List-F6'></td>
    <td id='Document List-G6'>2017-08-16 00:00:00</td>
    <td id='Document List-H6'>ABN - Glenaura Holdings Pty Ltd</td>
    <td id='Document List-I6'></td>
    <td id='Document List-J6'>2017-08-22 00:00:00</td>
    <td id='Document List-K6'>A1-14009 - WD100 - Site Plans - BA ISSUE.14-07-31</td>
    <td id='Document List-L6'></td>
    <td id='Document List-M6'>2017-08-18 00:00:00</td>
    <td id='Document List-N6'>A&amp;L - Giuseppe Augello</td>
    <td id='Document List-O6'></td>
    <td id='Document List-P6'>2017-08-24 00:00:00</td>
    <td id='Document List-Q6'></td>
    <td id='Document List-R6'></td>
    <td id='Document List-S6'></td>
  </tr>
  <tr>
    <td id='Document List-B7'>Email - Richard Woodhead</td>
    <td id='Document List-C7'></td>
    <td id='Document List-D7'>2017-09-22 00:00:00</td>
    <td id='Document List-E7'>Disclosure Statement  (signed) - Eagleby</td>
    <td id='Document List-F7'></td>
    <td id='Document List-G7'>2017-08-16 00:00:00</td>
    <td id='Document List-H7'>CV - Giuseppe Augello</td>
    <td id='Document List-I7'></td>
    <td id='Document List-J7'>2017-10-03 00:00:00</td>
    <td id='Document List-K7'>A1-14009 - WD200 - Type G18 Building - BA ISSUE.14-07-31</td>
    <td id='Document List-L7'></td>
    <td id='Document List-M7'>2017-08-18 00:00:00</td>
    <td id='Document List-N7'></td>
    <td id='Document List-O7'></td>
    <td id='Document List-P7'></td>
    <td id='Document List-Q7'></td>
    <td id='Document List-R7'></td>
    <td id='Document List-S7'></td>
  </tr>
  <tr>
    <td id='Document List-B8'>GPS Development Finance - Loan Offer - Glenaura Holdings Pty Ltd</td>
    <td id='Document List-C8'></td>
    <td id='Document List-D8'>2017-09-22 00:00:00</td>
    <td id='Document List-E8'>RP - 155-163 Fryar Road Eagleby, QLD, 4207</td>
    <td id='Document List-F8'></td>
    <td id='Document List-G8'>2017-08-22 00:00:00</td>
    <td id='Document List-H8'>CV - Joe Augello</td>
    <td id='Document List-I8'></td>
    <td id='Document List-J8'>2017-10-03 00:00:00</td>
    <td id='Document List-K8'>A1-14009 - WD300 - Type H12 Building - BA ISSUE.14-07-31</td>
    <td id='Document List-L8'></td>
    <td id='Document List-M8'>2017-08-18 00:00:00</td>
    <td id='Document List-N8'></td>
    <td id='Document List-O8'></td>
    <td id='Document List-P8'></td>
    <td id='Document List-Q8'></td>
    <td id='Document List-R8'></td>
    <td id='Document List-S8'></td>
  </tr>
  <tr>
    <td id='Document List-B9'>Letter from Joe Augello</td>
    <td id='Document List-C9'></td>
    <td id='Document List-D9'>2017-08-04 00:00:00</td>
    <td id='Document List-E9'></td>
    <td id='Document List-F9'></td>
    <td id='Document List-G9'></td>
    <td id='Document List-H9'>ID CC - Giuseppe Augello</td>
    <td id='Document List-I9'></td>
    <td id='Document List-J9'>2017-08-16 00:00:00</td>
    <td id='Document List-K9'>A1-14009 - WD400 - Type I16 Building - BA ISSUE.14-07-31</td>
    <td id='Document List-L9'></td>
    <td id='Document List-M9'>2017-08-18 00:00:00</td>
    <td id='Document List-N9'></td>
    <td id='Document List-O9'></td>
    <td id='Document List-P9'></td>
    <td id='Document List-Q9'></td>
    <td id='Document List-R9'></td>
    <td id='Document List-S9'></td>
  </tr>
  <tr>
    <td id='Document List-B10'></td>
    <td id='Document List-C10'></td>
    <td id='Document List-D10'></td>
    <td id='Document List-E10'></td>
    <td id='Document List-F10'></td>
    <td id='Document List-G10'></td>
    <td id='Document List-H10'>ID DC - Giuseppe Augello</td>
    <td id='Document List-I10'></td>
    <td id='Document List-J10'>2017-08-16 00:00:00</td>
    <td id='Document List-K10'>Fryar Rd Eagleby Construction Costs</td>
    <td id='Document List-L10'></td>
    <td id='Document List-M10'>2017-08-18 00:00:00</td>
    <td id='Document List-N10'></td>
    <td id='Document List-O10'></td>
    <td id='Document List-P10'></td>
    <td id='Document List-Q10'></td>
    <td id='Document List-R10'></td>
    <td id='Document List-S10'></td>
  </tr>
  <tr>
    <td id='Document List-B11'></td>
    <td id='Document List-C11'></td>
    <td id='Document List-D11'></td>
    <td id='Document List-E11'></td>
    <td id='Document List-F11'></td>
    <td id='Document List-G11'></td>
    <td id='Document List-H11'>ID MC - Giuseppe Augello</td>
    <td id='Document List-I11'></td>
    <td id='Document List-J11'>2017-08-16 00:00:00</td>
    <td id='Document List-K11'>Approved Plans</td>
    <td id='Document List-L11'></td>
    <td id='Document List-M11'>2017-08-18 00:00:00</td>
    <td id='Document List-N11'></td>
    <td id='Document List-O11'></td>
    <td id='Document List-P11'></td>
    <td id='Document List-Q11'></td>
    <td id='Document List-R11'></td>
    <td id='Document List-S11'></td>
  </tr>
  <tr>
    <td id='Document List-B12'></td>
    <td id='Document List-C12'></td>
    <td id='Document List-D12'></td>
    <td id='Document List-E12'></td>
    <td id='Document List-F12'></td>
    <td id='Document List-G12'></td>
    <td id='Document List-H12'>ID PP - Giuseppe Augello</td>
    <td id='Document List-I12'></td>
    <td id='Document List-J12'>2017-08-16 00:00:00</td>
    <td id='Document List-K12'>Development Approval</td>
    <td id='Document List-L12'></td>
    <td id='Document List-M12'>2017-08-18 00:00:00</td>
    <td id='Document List-N12'></td>
    <td id='Document List-O12'></td>
    <td id='Document List-P12'></td>
    <td id='Document List-Q12'></td>
    <td id='Document List-R12'></td>
    <td id='Document List-S12'></td>
  </tr>
  <tr>
    <td id='Document List-B13'></td>
    <td id='Document List-C13'></td>
    <td id='Document List-D13'></td>
    <td id='Document List-E13'></td>
    <td id='Document List-F13'></td>
    <td id='Document List-G13'></td>
    <td id='Document List-H13'></td>
    <td id='Document List-I13'></td>
    <td id='Document List-J13'></td>
    <td id='Document List-K13'>Development Permit</td>
    <td id='Document List-L13'></td>
    <td id='Document List-M13'>2017-08-18 00:00:00</td>
    <td id='Document List-N13'></td>
    <td id='Document List-O13'></td>
    <td id='Document List-P13'></td>
    <td id='Document List-Q13'></td>
    <td id='Document List-R13'></td>
    <td id='Document List-S13'></td>
  </tr>
  <tr>
    <td id='Document List-B14'></td>
    <td id='Document List-C14'></td>
    <td id='Document List-D14'></td>
    <td id='Document List-E14'></td>
    <td id='Document List-F14'></td>
    <td id='Document List-G14'></td>
    <td id='Document List-H14'></td>
    <td id='Document List-I14'></td>
    <td id='Document List-J14'></td>
    <td id='Document List-K14'>Stage 4 Feasability</td>
    <td id='Document List-L14'></td>
    <td id='Document List-M14'>2017-08-18 00:00:00</td>
    <td id='Document List-N14'></td>
    <td id='Document List-O14'></td>
    <td id='Document List-P14'></td>
    <td id='Document List-Q14'></td>
    <td id='Document List-R14'></td>
    <td id='Document List-S14'></td>
  </tr>
  <tr>
    <td id='Document List-B15'></td>
    <td id='Document List-C15'></td>
    <td id='Document List-D15'></td>
    <td id='Document List-E15'></td>
    <td id='Document List-F15'></td>
    <td id='Document List-G15'></td>
    <td id='Document List-H15'></td>
    <td id='Document List-I15'></td>
    <td id='Document List-J15'></td>
    <td id='Document List-K15'>EL01 - Legend</td>
    <td id='Document List-L15'></td>
    <td id='Document List-M15'>2017-08-18 00:00:00</td>
    <td id='Document List-N15'></td>
    <td id='Document List-O15'></td>
    <td id='Document List-P15'></td>
    <td id='Document List-Q15'></td>
    <td id='Document List-R15'></td>
    <td id='Document List-S15'></td>
  </tr>
  <tr>
    <td id='Document List-B16'></td>
    <td id='Document List-C16'></td>
    <td id='Document List-D16'></td>
    <td id='Document List-E16'></td>
    <td id='Document List-F16'></td>
    <td id='Document List-G16'></td>
    <td id='Document List-H16'></td>
    <td id='Document List-I16'></td>
    <td id='Document List-J16'></td>
    <td id='Document List-K16'>EL02 - G18 Ground Floor</td>
    <td id='Document List-L16'></td>
    <td id='Document List-M16'>2017-08-18 00:00:00</td>
    <td id='Document List-N16'></td>
    <td id='Document List-O16'></td>
    <td id='Document List-P16'></td>
    <td id='Document List-Q16'></td>
    <td id='Document List-R16'></td>
    <td id='Document List-S16'></td>
  </tr>
  <tr>
    <td id='Document List-B17'></td>
    <td id='Document List-C17'></td>
    <td id='Document List-D17'></td>
    <td id='Document List-E17'></td>
    <td id='Document List-F17'></td>
    <td id='Document List-G17'></td>
    <td id='Document List-H17'></td>
    <td id='Document List-I17'></td>
    <td id='Document List-J17'></td>
    <td id='Document List-K17'>EL03 - G18 Level 2</td>
    <td id='Document List-L17'></td>
    <td id='Document List-M17'>2017-08-18 00:00:00</td>
    <td id='Document List-N17'></td>
    <td id='Document List-O17'></td>
    <td id='Document List-P17'></td>
    <td id='Document List-Q17'></td>
    <td id='Document List-R17'></td>
    <td id='Document List-S17'></td>
  </tr>
  <tr>
    <td id='Document List-B18'></td>
    <td id='Document List-C18'></td>
    <td id='Document List-D18'></td>
    <td id='Document List-E18'></td>
    <td id='Document List-F18'></td>
    <td id='Document List-G18'></td>
    <td id='Document List-H18'></td>
    <td id='Document List-I18'></td>
    <td id='Document List-J18'></td>
    <td id='Document List-K18'>EL04 - G18 Level 3</td>
    <td id='Document List-L18'></td>
    <td id='Document List-M18'>2017-08-18 00:00:00</td>
    <td id='Document List-N18'></td>
    <td id='Document List-O18'></td>
    <td id='Document List-P18'></td>
    <td id='Document List-Q18'></td>
    <td id='Document List-R18'></td>
    <td id='Document List-S18'></td>
  </tr>
  <tr>
    <td id='Document List-B19'></td>
    <td id='Document List-C19'></td>
    <td id='Document List-D19'></td>
    <td id='Document List-E19'></td>
    <td id='Document List-F19'></td>
    <td id='Document List-G19'></td>
    <td id='Document List-H19'></td>
    <td id='Document List-I19'></td>
    <td id='Document List-J19'></td>
    <td id='Document List-K19'>EL05 - H12 Ground Floor</td>
    <td id='Document List-L19'></td>
    <td id='Document List-M19'>2017-08-18 00:00:00</td>
    <td id='Document List-N19'></td>
    <td id='Document List-O19'></td>
    <td id='Document List-P19'></td>
    <td id='Document List-Q19'></td>
    <td id='Document List-R19'></td>
    <td id='Document List-S19'></td>
  </tr>
</table>

OUTPUT (JSON):
{{{{
[
  {{{{
    "Internal": "Development Loan Summary",
    "Date Rec'd": "8/18/2017",
    "Property Details": "COS - Acacia Waters",
    "Borrower & Guarantor Details": "ABN - Glenaura Holdings Pty Ltd",
    "Project Documents": "A1-14009 - WD100 - Site Plan",
    "Financial Info": "A&L - Giuseppe Augello",
    "Loan Submission": ""
  }}}},
  {{{{
    "Internal": "Email - Richard Woodhead",
    "Date Rec'd": "9/22/2017",
    "Property Details": "Disclosure Statement (signed)",
    "Borrower & Guarantor Details": "CV - Giuseppe Augello",
    "Project Documents": "A1-14009 - WD200 - Type G18",
    "Financial Info": "",
    "Loan Submission": ""
  }}}},
  {{{{
    "Internal": "GPS Development Finance",
    "Date Rec'd": "9/22/2017",
    "Property Details": "RP - 155-163 Fryar Road Eagleby",
    "Borrower & Guarantor Details": "CV - Joe Augello",
    "Project Documents": "A1-14009 - WD300 - Type H12",
    "Financial Info": "",
    "Loan Submission": ""
  }}}},
  {{{{
    "Internal": "Letter from Joe Augello",
    "Date Rec'd": "8/4/2017",
    "Property Details": "",
    "Borrower & Guarantor Details": "ID CC - Giuseppe Augello",
    "Project Documents": "A1-14009 - WD400 - Type H16",
    "Financial Info": "",
    "Loan Submission": ""
  }}}},
  {{{{
    "Internal": "",
    "Date Rec'd": "",
    "Property Details": "",
    "Borrower & Guarantor Details": "ID DC - Giuseppe Augello",
    "Project Documents": "Fryar Rd Eagleby Construction",
    "Financial Info": "",
    "Loan Submission": ""
  }}}},
  {{{{
    "Internal": "",
    "Date Rec'd": "",
    "Property Details": "",
    "Borrower & Guarantor Details": "ID MC - Giuseppe Augello",
    "Project Documents": "Approved Plans",
    "Financial Info": "",
    "Loan Submission": ""
  }}}},
  {{{{
    "Internal": "",
    "Date Rec'd": "",
    "Property Details": "",
    "Borrower & Guarantor Details": "ID PP - Giuseppe Augello",
    "Project Documents": "Development Approval",
    "Financial Info": "",
    "Loan Submission": ""
  }}}},
  {{{{
    "Internal": "",
    "Date Rec'd": "",
    "Property Details": "",
    "Borrower & Guarantor Details": "",
    "Project Documents": "Development Permit",
    "Financial Info": "",
    "Loan Submission": ""
  }}}},
  {{{{
    "Internal": "",
    "Date Rec'd": "",
    "Property Details": "",
    "Borrower & Guarantor Details": "",
    "Project Documents": "Stage 4 Feasibility",
    "Financial Info": "",
    "Loan Submission": ""
  }}}},
  {{{{
    "Internal": "",
    "Date Rec'd": "",
    "Property Details": "",
    "Borrower & Guarantor Details": "",
    "Project Documents": "EL01 - Legend",
    "Financial Info": "",
    "Loan Submission": ""
  }}}},
  {{{{
    "Internal": "",
    "Date Rec'd": "",
    "Property Details": "",
    "Borrower & Guarantor Details": "",
    "Project Documents": "EL02 - G18 Ground Floor",
    "Financial Info": "",
    "Loan Submission": ""
  }}}},
  {{{{
    "Internal": "",
    "Date Rec'd": "",
    "Property Details": "",
    "Borrower & Guarantor Details": "",
    "Project Documents": "EL03 - G18 Level 2",
    "Financial Info": "",
    "Loan Submission": ""
  }}}},
  {{{{
    "Internal": "",
    "Date Rec'd": "",
    "Property Details": "",
    "Borrower & Guarantor Details": "",
    "Project Documents": "EL04 - G18 Level 3",
    "Financial Info": "",
    "Loan Submission": ""
  }}}},
  {{{{
    "Internal": "",
    "Date Rec'd": "",
    "Property Details": "",
    "Borrower & Guarantor Details": "",
    "Project Documents": "EL05 - H12 Ground Floor",
    "Financial Info": "",
    "Loan Submission": ""
  }}}}
]
}}}}

════════════════════════════════════
EXAMPLE 4
════════════════════════════════════

INPUT (HTML/MARKDOWN):

<table id='Key Statements-B32:I38'>
  <tr>
    <td id='Key Statements-B32'></td>
    <td id='Key Statements-C32'>Land LVR</td>
    <td id='Key Statements-D32'>TDC</td>
    <td id='Key Statements-E32'>GRV</td>
    <td id='Key Statements-F32'>Rate</td>
    <td id='Key Statements-G32'>Fees</td>
    <td id='Key Statements-H32'>Max</td>
    <td id='Key Statements-I32'>Presales</td>
  </tr>
  <tr>
    <td id='Key Statements-B33'>Development</td>
    <td id='Key Statements-C33'>50% - 70%</td>
    <td id='Key Statements-D33'>80% - 100%</td>
    <td id='Key Statements-E33'>55% - 70%</td>
    <td id='Key Statements-F33'>8% - 12%</td>
    <td id='Key Statements-G33'>1% - 2%</td>
    <td id='Key Statements-H33'>20M</td>
    <td id='Key Statements-I33'>0% - 70%</td>
  </tr>
  <tr>
    <td id='Key Statements-B34'></td>
    <td id='Key Statements-C34'>LVR</td>
    <td id='Key Statements-D34'></td>
    <td id='Key Statements-E34'></td>
    <td id='Key Statements-F34'></td>
    <td id='Key Statements-G34'></td>
    <td id='Key Statements-H34'></td>
    <td id='Key Statements-I34'></td>
  </tr>
  <tr>
    <td id='Key Statements-B35'>Commercial &amp; Industrial</td>
    <td id='Key Statements-C35'>50% - 75%</td>
    <td id='Key Statements-D35'></td>
    <td id='Key Statements-E35'></td>
    <td id='Key Statements-F35'>6% - 12%</td>
    <td id='Key Statements-G35'>.5% - 2%</td>
    <td id='Key Statements-H35'>25M</td>
    <td id='Key Statements-I35'></td>
  </tr>
  <tr>
    <td id='Key Statements-B36'>Landbank/Vacant Land</td>
    <td id='Key Statements-C36'>40% - 70%</td>
    <td id='Key Statements-D36'></td>
    <td id='Key Statements-E36'></td>
    <td id='Key Statements-F36'>7% - 14%</td>
    <td id='Key Statements-G36'>1% - 2%</td>
    <td id='Key Statements-H36'>25M</td>
    <td id='Key Statements-I36'></td>
  </tr>
  <tr>
    <td id='Key Statements-B37'>Residential </td>
    <td id='Key Statements-C37'>0.7</td>
    <td id='Key Statements-D37'></td>
    <td id='Key Statements-E37'></td>
    <td id='Key Statements-F37'>6% - 10%</td>
    <td id='Key Statements-G37'>1% - 2%</td>
    <td id='Key Statements-H37'>25M</td>
    <td id='Key Statements-I37'></td>
  </tr>
  <tr>
    <td id='Key Statements-B38'>Mezzanine</td>
    <td id='Key Statements-C38'>0.75</td>
    <td id='Key Statements-D38'></td>
    <td id='Key Statements-E38'>0.75</td>
    <td id='Key Statements-F38'>16% - 20%</td>
    <td id='Key Statements-G38'>1.75% - 2%</td>
    <td id='Key Statements-H38'>2M</td>
    <td id='Key Statements-I38'></td>
  </tr>
</table>

OUTPUT (JSON):
{{{{
  "Development": {{{{
    "Land_LVR": "50% - 70%",
    "TDC": "80% - 100%",
    "GRV": "55% - 70%",
    "Rate": "8% - 12%",
    "Fees": "1% - 2%",
    "Max": "20M",
    "Presales": "0% - 70%"
  }}}},
  "Blank_Row": {{{{
    "Land_LVR": "LVR",
    "TDC": "",
    "GRV": "",
    "Rate": "",
    "Fees": "",
    "Max": "",
    "Presales": ""
  }}}},
  "Commercial_Industrial": {{{{
    "Land_LVR": "50% - 75%",
    "TDC": "",
    "GRV": "",
    "Rate": "6% - 12%",
    "Fees": "0.5% - 2%",
    "Max": "25M",
    "Presales": ""
  }}}},
  "Landbank_Vacant_Land": {{{{
    "Land_LVR": "40% - 70%",
    "TDC": "",
    "GRV": "",
    "Rate": "7% - 14%",
    "Fees": "1% - 2%",
    "Max": "25M",
    "Presales": ""
  }}}},
  "Residential": {{{{
    "Land_LVR": "0.7",
    "TDC": "",
    "GRV": "",
    "Rate": "6% - 10%",
    "Fees": "1% - 2%",
    "Max": "25M",
    "Presales": ""
  }}}},
  "Mezzanine": {{{{
    "Land_LVR": "0.75",
    "TDC": "",
    "GRV": "0.75",
    "Rate": "16% - 20%",
    "Fees": "1.75% - 2%",
    "Max": "2M",
    "Presales": ""
  }}}}
}}}}

════════════════════════════════════

IMPORTANT:
- Response MUST start with {{ and end with }}.
- ALL tables must be returned inside the JSON.
- No data loss is allowed.

Table Markdown:
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
    logger.debug(f"LLM output: {llm_output}")

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
            # Try to find the JSON object or array by looking for matching braces/brackets
            start_char = None
            start_idx = -1

            # Check for both { and [ as valid JSON starts
            obj_idx = llm_output.find('{')
            arr_idx = llm_output.find('[')

            if obj_idx == -1 and arr_idx == -1:
                raise ValueError("No JSON object or array found in output")
            elif obj_idx == -1:
                start_idx = arr_idx
                start_char = '['
            elif arr_idx == -1:
                start_idx = obj_idx
                start_char = '{'
            else:
                # Both found, use whichever comes first
                if obj_idx < arr_idx:
                    start_idx = obj_idx
                    start_char = '{'
                else:
                    start_idx = arr_idx
                    start_char = '['

            # Count braces/brackets to find the end of the JSON
            close_char = '}' if start_char == '{' else ']'
            count = 0
            end_idx = start_idx

            for i in range(start_idx, len(llm_output)):
                if llm_output[i] == start_char:
                    count += 1
                elif llm_output[i] == close_char:
                    count -= 1
                    if count == 0:
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
    Returns: table data directly from LLM (already in nested dict format)
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

    # LLM already returns data in the desired nested format (see prompt examples)
    # No transformation needed - use the data directly
    return {
        "excel_file": excel_file_name,
        # "file_index": file_index,
        "sheet_name": sheet_name,
        # "table_index": table_index,
        "data": table_json  # Use LLM output directly
    }


async def process_excel_to_json() -> Dict[str, Any]:
    """
    Main async function to process all Excel files in the input folder and convert them to JSON.

    Processing Flow:
    - Phase 1: Sync sheet splitting (create all temp files from input folder)
    - Phase 2: Async batch Landing AI processing (all files at once)
    - Phase 3: Async batch OpenAI processing (all tables at once)

    Returns:
        Dictionary containing processing results
    """
    # Clean up previous conversion data
    logger.info("Starting new conversion - cleaning previous data...")
    cleanup_previous_data()

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
        # PHASE 2: ASYNC BATCH LANDING AI PROCESSING
        # =================================================================
        logger.info(f"\n{'='*70}\nPHASE 2: LANDING AI PROCESSING (Async Batch)\n{'='*70}\n")
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

        # ASYNC BATCH PROCESSING: Wait for all Landing AI tasks to complete
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
        # PHASE 3.2: ASYNC BATCH OPENAI PROCESSING
        # =================================================================
        logger.info(f"\n{'='*70}\nPHASE 3.2: OPENAI PROCESSING (Async Batch)\n{'='*70}\n")
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

            # ASYNC BATCH PROCESSING: Wait for all OpenAI tasks to complete
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

        # Initialize list for per-Excel files
        per_excel_files_saved = []

        # Save only one consolidated JSON file in key-value format
        if all_results:
            consolidated_json_file = output_folder / "all_tables_consolidated.json"
            with open(consolidated_json_file, "w", encoding="utf-8") as f:
                json.dump(all_results, f, indent=2, ensure_ascii=False)

            logger.info(f"* CONSOLIDATED JSON SAVED: {consolidated_json_file.name}")
            logger.info(f"* Total tables extracted: {len(all_results)}")
            logger.info(f"* Format: Key-Value (each row is a dictionary)")

            # Log summary by Excel file
            per_excel_count = {}
            for result in all_results:
                excel_name = result.get('excel_file', 'unknown')
                per_excel_count[excel_name] = per_excel_count.get(excel_name, 0) + 1

            logger.info(f"\n* Tables per Excel file:")
            for excel_name, count in per_excel_count.items():
                logger.info(f"  - {excel_name}: {count} tables")

            # =================================================================
            # SAVE PER-EXCEL JSON FILES (Key-Value Format)
            # =================================================================
            logger.info(f"\n{'='*70}\nSAVING PER-EXCEL JSON FILES\n{'='*70}\n")

            # Group results by Excel file
            per_excel_data = {}
            for result in all_results:
                excel_name = result.get('excel_file', 'unknown')
                if excel_name not in per_excel_data:
                    per_excel_data[excel_name] = []
                per_excel_data[excel_name].append(result)

            # Save individual JSON file for each Excel file
            for excel_name, excel_results in per_excel_data.items():
                # Create sanitized filename
                excel_basename = Path(excel_name).stem  # Remove extension
                safe_excel_name = sanitize_filename(excel_basename)
                per_excel_json_file = output_folder / f"{safe_excel_name}_complete.json"

                # Save JSON file
                with open(per_excel_json_file, "w", encoding="utf-8") as f:
                    json.dump(excel_results, f, indent=2, ensure_ascii=False)

                per_excel_files_saved.append(per_excel_json_file.name)
                logger.info(f"  ✓ Saved: {per_excel_json_file.name} ({len(excel_results)} tables)")

            logger.info(f"\n* Per-Excel JSON files saved: {len(per_excel_files_saved)}")
            logger.info(f"* Format: Key-Value (same as consolidated)")

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
            "output_folder": str(output_folder.absolute()),
            "consolidated_file": "all_tables_consolidated.json",
            "per_excel_files": per_excel_files_saved,
            "results": all_results
        }

    finally:
        # Cleanup all temporary folders after processing
        import time
        folders_to_cleanup = [
            Path("temp_sheets"),
        ]

        # Small delay to ensure all file handles are released
        time.sleep(0.5)

        for folder in folders_to_cleanup:
            if folder.exists():
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        shutil.rmtree(folder)
                        logger.info(f"Cleaned up temporary folder: {folder}/")
                        break
                    except Exception as e:
                        if attempt < max_retries - 1:
                            logger.debug(f"Retry {attempt + 1}/{max_retries} for {folder}/: {e}")
                            time.sleep(1)  # Wait before retry
                        else:
                            logger.warning(f"Could not clean up {folder}/ after {max_retries} attempts: {e}")
