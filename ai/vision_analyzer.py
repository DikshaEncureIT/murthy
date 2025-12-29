"""
Lightweight Vision-Based Excel Analysis
Focuses on visual structure analysis without data extraction:
- Column gap detection
- Table relationship understanding (same vs different tables)
"""

import json
from pathlib import Path
from typing import Dict, Any, List
from openai import AsyncOpenAI
from logger import AppLogger
from vision_utils import encode_image_to_base64

logger = AppLogger.get_logger(__file__)


def build_vision_prompt() -> str:
    """
    Build ENHANCED prompt for accurate vision-based Excel analysis.

    Focus areas:
    - Column-wise gap detection with high precision
    - Table relationship understanding with clear reasoning

    Returns:
        Enhanced prompt with examples and detailed instructions
    """
    #     prompt = """You are analyzing an Excel spreadsheet image. Your goal is to provide ACCURATE, PRECISE structural analysis.
    #     You want the tables to be extracted accurately. Since multiple structured tables exist on the same page, the requirement is to correctly identify each table’s headers and use them as keys, with all corresponding rows captured as arrays under those keys.

    # ═══════════════════════════════════════════════════════════════════
    # ANALYSIS FRAMEWORK - Follow this step-by-step:
    # ═══════════════════════════════════════════════════════════════════

    # STEP 1: VISUAL SCAN
    # • Scan the entire spreadsheet from left to right, top to bottom
    # • Identify all visible grid lines and cell boundaries
    # • Note any completely empty columns (no content, no headers, blank throughout)
    # • Observe color patterns, borders, and spacing patterns

    # STEP 2: COLUMN GAP DETECTION (BE VERY PRECISE)
    # What is a column gap?
    # - A completely EMPTY column with NO data in any row
    # - Acts as a visual separator between different sections or tables
    # - Usually appears as a blank vertical space

    # What is NOT a column gap?
    # - Regular columns with data
    # - Columns with just whitespace cells that are part of a table
    # - The space between cell borders (that's just normal grid)

    # Detection Rules:
    # 1. Count from left to right (A, B, C, D...)
    # 2. If column has ANY content in ANY row → NOT a gap
    # 3. If column is completely blank throughout → IS a gap
    # 4. Note the exact column letter (e.g., "Column D")

    # Example Gap Pattern:
    # | A: Name | B: Age | C: (empty) | D: City | E: State |
    #                       ↑ This is a column gap at C

    # STEP 3: TABLE IDENTIFICATION 
    # Count tables by:
    # 1. Looking for groups of cells with similar structure
    # 2. Tables are separated by empty rows OR empty columns
    # 3. Each table has consistent column structure
    # 4. Headers usually appear in first row (often bold or colored)

    # For each table, record:
    # - Starting row (where table begins)
    # - Ending row (where table ends)
    # - Starting column letter (leftmost column)
    # - Ending column letter (rightmost column)
    # - Total columns in the table
    # - Total rows in the table

    # STEP 4: TABLE RELATIONSHIP CLASSIFICATION (CRITICAL)

    # Classification Options:
    # A) "different_tables" - Use when:
    #    • Tables have DIFFERENT number of columns
    #    • Tables have DIFFERENT headers or structure
    #    • Tables serve completely DIFFERENT purposes
    #    • Example: Employee table (5 cols) + Budget summary (3 cols)

    # B) "single_table" - Use when:
    #    • Multiple tables have IDENTICAL column structure (same number of columns)
    #    • Headers appear to be the SAME across tables
    #    • Tables look like duplicates or continuation of same structure
    #    • Example: Sales data for different regions, all with same columns

    # Confidence Scoring:
    # • 1.0 = Absolutely certain, clear visual evidence
    # • 0.9 = Very confident, strong indicators
    # • 0.8 = Confident, good evidence
    # • 0.7 = Moderately confident, some ambiguity
    # • 0.6 or less = Uncertain, conflicting signals

    # ═══════════════════════════════════════════════════════════════════
    # EXAMPLES FOR REFERENCE:
    # ═══════════════════════════════════════════════════════════════════

    # Example 1: Different Tables
    # Visual: Employee table + separate summary table
    # | EmpID | Name | Dept | Role | (gap) | Metric | Value |
    # Result: "different_tables" with confidence 0.95

    # Example 2: Single Table
    # Visual: One table spanning the entire sheet or Two tables side-by-side with identical headers
    # | Product | Price | (gap) | Stock | Category |
    # Result: "single_table" with confidence 1.0

    # ═══════════════════════════════════════════════════════════════════
    # OUTPUT FORMAT:
    # ═══════════════════════════════════════════════════════════════════

    # Return ONLY valid JSON with this EXACT structure:

    # {
    #   "column_gaps": [
    #     {
    #       "column_letter": "C",
    #       "location": "between columns B and D",
    #       "purpose": "visual separator between two tables",
    #       "confidence": 0.95,
    #       "type": "same table/diffrent table"
    #     }
    #   ],
    #   "tables_detected": [
    #     {
    #       "table_id": 1,
    #       "location": {
    #         "start_row": 1,
    #         "end_row": 15,
    #         "start_col": "A",
    #         "end_col": "D"
    #       },
    #       "column_count": 4,
    #       "row_count": 15,
    #       "visual_structure": "data table with header row"
    #     }
    #   ],
    #   "table_relationship": {
    #     "total_tables": 2,
    #     "classification": "same_table_repeated",
    #     "reasoning": "Both tables have identical 4-column structure with matching headers (ID, Name, Age, City). They appear to be the same table format repeated twice, possibly for different data sets.",
    #     "confidence": 0.95
    #   }
    # }

    # CRITICAL REMINDERS:
    # ✓ Be PRECISE with column letters and row numbers
    # ✓ Only report ACTUAL empty columns as gaps, not just spacing
    # ✓ Count ALL rows and columns ACCURATELY
    # ✓ Give SPECIFIC reasoning, not vague statements
    # ✓ Use HIGH confidence (0.9-1.0) only when very certain
    # ✓ Focus on STRUCTURE, ignore actual data values"""

    prompt = """You want the tables to be extracted accurately. Since multiple structured tables exist on the same page, the requirement is to correctly identify each table’s headers and use them as keys, with all corresponding rows captured as arrays under those keys."""
    return prompt

async def analyze_sheet_with_vision(
    client: AsyncOpenAI,
    image_path: Path,
    sheet_name: str,
    excel_path: Path,
) -> Dict[str, Any]:
    """
    Analyze a single sheet image using vision model for lightweight analysis.

    Args:
        client: AsyncOpenAI client
        image_path: Path to sheet image
        sheet_name: Name of the sheet
        excel_path: Path to Excel file

    Returns:
        Dictionary with lightweight visual analysis results containing:
        - column_gaps: List of detected column gaps
        - tables_detected: List of detected tables with locations
        - table_relationship: Classification of table relationships
    """
    try:
        logger.info(f"Analyzing sheet '{sheet_name}' with vision model (lightweight analysis)")

        # Validate image exists
        if not image_path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")

        # Encode image to base64
        base64_image = encode_image_to_base64(image_path)

        # Build prompt
        prompt = build_vision_prompt()

        # Call vision API
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert at visual analysis of Excel spreadsheets. Perform detailed, accurate structural analysis focusing on column gaps and table relationships. Provide your insights naturally and include a JSON structure with your findings. Prioritize accuracy and clarity in your analysis."
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ],
            max_completion_tokens=8192,
            temperature=0.0
        )

        # Get response
        llm_output = response.choices[0].message.content
        print(llm_output)
        # Log the raw output for debugging
        if llm_output:
            logger.info(f"LLM output received: {len(llm_output)} characters")
            logger.debug(f"First 500 chars: {llm_output[:500]}")
        else:
            logger.error(f"LLM returned None/empty for sheet '{sheet_name}'")
            raise ValueError("LLM returned empty response")

        # Clean markdown code blocks if present
        llm_output = llm_output.strip()
        if llm_output.startswith("```json"):
            llm_output = llm_output[7:]
        if llm_output.startswith("```"):
            llm_output = llm_output[3:]
        if llm_output.endswith("```"):
            llm_output = llm_output[:-3]
        llm_output = llm_output.strip()

        # Parse JSON
        try:
            analysis_result = json.loads(llm_output)
        except json.JSONDecodeError as e:
            logger.warning(f"JSON parsing failed at position {e.pos}")
            logger.warning(f"Problematic content: {llm_output[max(0, e.pos-50):e.pos+50]}")

            # Try to extract JSON object
            start_idx = llm_output.find('{')
            if start_idx == -1:
                logger.error(f"No JSON in output. Full response: {llm_output[:500]}")
                raise ValueError(f"No JSON object found. Response starts with: {llm_output[:100]}")

            # Count braces to find the end
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
            analysis_result = json.loads(json_str)
            logger.info(f"Successfully extracted JSON from position {start_idx} to {end_idx}")

        # Add metadata
        analysis_result["sheet_name"] = sheet_name
        analysis_result["image_path"] = str(image_path)

        logger.info(f"Vision analysis complete for sheet '{sheet_name}'")
        return analysis_result

    except Exception as e:
        logger.error(f"Error analyzing sheet '{sheet_name}' with vision: {e}", exc_info=True)
        return {
            "sheet_name": sheet_name,
            "error": str(e),
            "column_gaps": [],
            "tables_detected": [],
            "table_relationship": {
                "total_tables": 0,
                "classification": "error",
                "reasoning": f"Analysis failed: {str(e)}",
                "confidence": 0.0
            }
        }


async def analyze_table_similarity(
    all_sheet_analyses: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Aggregate table relationship information across all sheets.

    Args:
        all_sheet_analyses: List of vision analysis results

    Returns:
        Aggregated table relationship analysis across all sheets
    """
    try:
        logger.info("Aggregating table relationships across sheets")

        # Collect table relationship info from each sheet
        total_tables = 0
        sheet_classifications = []

        for sheet_analysis in all_sheet_analyses:
            sheet_name = sheet_analysis.get("sheet_name", "Unknown")
            table_relationship = sheet_analysis.get("table_relationship", {})
            tables_detected = sheet_analysis.get("tables_detected", [])

            sheet_table_count = table_relationship.get("total_tables", len(tables_detected))
            total_tables += sheet_table_count

            sheet_classifications.append({
                "sheet_name": sheet_name,
                "table_count": sheet_table_count,
                "classification": table_relationship.get("classification", "unknown"),
                "reasoning": table_relationship.get("reasoning", ""),
                "confidence": table_relationship.get("confidence", 0.0)
            })

        # Determine overall classification
        # If any sheet has different_tables, overall is different_tables
        # If all sheets have same_table_repeated or single_table, overall is same_table_repeated
        classifications = [s["classification"] for s in sheet_classifications]

        if "different_tables" in classifications:
            overall_classification = "different_tables"
            overall_reasoning = "At least one sheet contains different/distinct tables"
        elif all(c in ["same_table_repeated", "single_table"] for c in classifications):
            overall_classification = "same_table_repeated"
            overall_reasoning = "All sheets contain the same table structure (possibly repeated)"
        else:
            overall_classification = "mixed"
            overall_reasoning = "Mixed table structures across sheets"

        result = {
            "total_tables_across_all_sheets": total_tables,
            "overall_classification": overall_classification,
            "overall_reasoning": overall_reasoning,
            "by_sheet": sheet_classifications
        }

        logger.info(f"Table relationship analysis complete: {overall_classification} - {total_tables} total tables")
        return result

    except Exception as e:
        logger.error(f"Error analyzing table relationships: {e}", exc_info=True)
        return {
            "total_tables_across_all_sheets": 0,
            "overall_classification": "error",
            "overall_reasoning": str(e),
            "by_sheet": [],
            "error": str(e)
        }


async def generate_gap_report(
    all_sheet_analyses: List[Dict[str, Any]],
    excel_data_analyses: List[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Generate column gap detection report combining deterministic and vision analysis.

    Focus: Column-wise gaps that separate tables or sections.

    Args:
        all_sheet_analyses: List of vision analysis results
        excel_data_analyses: List of deterministic Excel column usage analyses

    Returns:
        Column gap detection report with both deterministic and vision-based results
    """
    try:
        logger.info("Generating column gap detection report")

        # ============================================
        # VISION-BASED GAP DETECTION (Original)
        # ============================================
        all_column_gaps = []
        total_vision_gaps = 0

        for sheet_analysis in all_sheet_analyses:
            sheet_name = sheet_analysis.get("sheet_name", "Unknown")
            column_gaps = sheet_analysis.get("column_gaps", [])

            total_vision_gaps += len(column_gaps)

            # Process column gaps
            for gap in column_gaps:
                all_column_gaps.append({
                    "sheet_name": sheet_name,
                    "column_letter": gap.get("column_letter", ""),
                    "location": gap.get("location", ""),
                    "purpose": gap.get("purpose", "Unknown"),
                    "confidence": gap.get("confidence", 0.0)
                })

        vision_result = {
            "total_column_gaps": total_vision_gaps,
            "details": all_column_gaps
        }

        # ============================================
        # DETERMINISTIC GAP DETECTION (New)
        # ============================================
        deterministic_result = {}
        total_deterministic_gaps = 0

        if excel_data_analyses:
            logger.info("Processing deterministic Excel column usage analysis")

            by_sheet = []
            for analysis in excel_data_analyses:
                sheet_name = analysis.get("sheet_name", "Unknown")
                gap_count = analysis.get("total_gaps", 0)
                total_deterministic_gaps += gap_count

                by_sheet.append({
                    "sheet_name": sheet_name,
                    "gap_summary": analysis.get("gap_summary", ""),
                    "columns_with_data": analysis.get("columns_with_data", []),
                    "column_sequences": analysis.get("column_sequences", []),
                    "total_gaps": gap_count,
                    "confidence": analysis.get("confidence", 1.0)
                })

            deterministic_result = {
                "total_gaps": total_deterministic_gaps,
                "by_sheet": by_sheet
            }
        else:
            logger.warning("No deterministic Excel analysis provided, using vision-only mode")

        # ============================================
        # GENERATE COMBINED RECOMMENDATIONS
        # ============================================
        recommendations = []

        if excel_data_analyses:
            # Prioritize deterministic analysis
            if total_deterministic_gaps > 0:
                recommendations.append(
                    f"Deterministic analysis found {total_deterministic_gaps} column gap(s) across sheets. "
                    "These are verified empty column sequences between columns with data."
                )
            else:
                recommendations.append(
                    "Deterministic analysis found no column gaps. All columns with data are contiguous."
                )

            # Add vision analysis as validation
            if total_vision_gaps > 0:
                if total_vision_gaps != total_deterministic_gaps:
                    recommendations.append(
                        f"Vision analysis detected {total_vision_gaps} gap(s), which differs from deterministic analysis. "
                        "Deterministic analysis is authoritative for column usage."
                    )
                else:
                    recommendations.append(
                        f"Vision analysis confirms the {total_vision_gaps} gap(s) found by deterministic analysis."
                    )
        else:
            # Fall back to vision-only recommendations
            if total_vision_gaps > 0:
                recommendations.append(
                    f"Found {total_vision_gaps} column gap(s) across sheets. "
                    "These gaps may indicate separate tables or formatting sections."
                )
            else:
                recommendations.append(
                    "No significant column gaps detected. Tables appear to be contiguous."
                )

        # ============================================
        # BUILD FINAL RESULT
        # ============================================
        result = {
            "deterministic_column_usage": deterministic_result if excel_data_analyses else None,
            "vision_detected_gaps": vision_result,
            "recommendations": recommendations
        }

        logger.info(f"Column gap report generated: {total_deterministic_gaps} deterministic gaps, {total_vision_gaps} vision gaps")
        return result

    except Exception as e:
        logger.error(f"Error generating gap report: {e}", exc_info=True)
        return {
            "deterministic_column_usage": None,
            "vision_detected_gaps": {
                "total_column_gaps": 0,
                "details": []
            },
            "recommendations": [],
            "error": str(e)
        }
