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
from vision_utils import convert_excel_to_html

logger = AppLogger.get_logger(__file__)


def build_vision_prompt_for_html() -> str:
    """
    Build prompt for HTML-based Excel table analysis.

    The prompt instructs the model to analyze Excel tables represented as HTML
    with full styling, merged cells, and structure preservation.

    Returns:
        Prompt string for HTML analysis
    """
    # prompt = """You want the tables to be extracted accurately. Since multiple structured tables exist on the same page, the requirement is to correctly identify each table's headers and use them as keys, with all corresponding rows captured as arrays under those keys."""
    prompt="""You want the tables to be extracted accurately. Since multiple structured tables exist on the same page, the requirement is to correctly identify each table’s headers and use them as keys, with all corresponding rows captured as arrays under those keys. You have been provided with HTML data of the Excel sheet, which contains the complete structural representation of the tables, including headers, rows, merged cells, and cell values. IMPORTANT: Use the HTML data as the single source of truth for maximum accuracy. The HTML preserves table boundaries, row and column relationships, and hierarchical structure, enabling precise header detection and correct row mapping. Ensure that each table is independently identified, headers are correctly interpreted as keys, and all rows belonging to the same header are grouped accurately. If any ambiguity arises, rely strictly on the HTML structure and semantics to determine correct table organization and data relationships."""
    return prompt

async def analyze_sheet_with_vision(
    client: AsyncOpenAI,
    sheet_name: str,
    excel_path: Path,
) -> Dict[str, Any]:
    """
    Analyze a single Excel sheet using HTML-based analysis with GPT-4o.

    NEW APPROACH: Converts Excel to HTML with full formatting, then sends to GPT-4o
    for structural analysis. This provides better accuracy than image-based analysis.

    Args:
        client: AsyncOpenAI client
        sheet_name: Name of the sheet
        excel_path: Path to Excel file

    Returns:
        Dictionary with analysis results containing:
        - column_gaps: List of detected column gaps
        - tables_detected: List of detected tables with locations
        - table_relationship: Classification of table relationships
    """
    try:
        logger.info(f"Analyzing sheet '{sheet_name}' using HTML-based analysis")

        # Validate Excel file exists
        if not excel_path.exists():
            raise FileNotFoundError(f"Excel file not found: {excel_path}")

        # Convert Excel sheet to HTML with full styling
        html_content = convert_excel_to_html(
            excel_path=excel_path,
            sheet_name=sheet_name,
            max_rows=200,
            max_cols=50,
            include_styling=True
        )
        print("html_content",html_content)
        logger.info(f"HTML generated: {len(html_content)} characters")

        # Safety check: truncate only if extremely large (to stay within token limits)
        if len(html_content) > 300000:
            logger.warning(f"HTML content truncated from {len(html_content)} to 300000 characters")
            html_content = html_content[:300000] + "\n<!-- HTML TRUNCATED - first 300K characters shown -->"

        # Build prompt for HTML analysis
        prompt = build_vision_prompt_for_html()

        # Append HTML content to prompt
        full_prompt = f"{prompt}\n\n═══════════════════════════════════════════════════════════════════\nEXCEL HTML TABLE:\n═══════════════════════════════════════════════════════════════════\n\n{html_content}\n\n═══════════════════════════════════════════════════════════════════\nYour JSON analysis:\n═══════════════════════════════════════════════════════════════════"

        # Call GPT-4o (text-based, not vision)
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert at analyzing Excel spreadsheets represented as HTML tables. You understand HTML table structure including rowspan, colspan, CSS styling, and data-cell attributes. Perform detailed, accurate structural analysis focusing on column gaps and table relationships. Return ONLY valid JSON as specified in the prompt."
                },
                {
                    "role": "user",
                    "content": full_prompt
                }
            ],
            max_completion_tokens=8192,
            temperature=0.0
        )

        # Log token usage for monitoring
        if hasattr(response, 'usage') and response.usage:
            logger.debug(f"Token usage - Prompt: {response.usage.prompt_tokens}, "
                        f"Completion: {response.usage.completion_tokens}, "
                        f"Total: {response.usage.total_tokens}")

        # Get response
        llm_output = response.choices[0].message.content
        print("108llm_output",llm_output)

        # Parse and save LLM output (will be done after JSON parsing below)

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
        analysis_result["analysis_method"] = "html_based"
        analysis_result["html_size_chars"] = len(html_content)

        logger.info(f"HTML-based analysis complete for sheet '{sheet_name}'")

        # Save parsed LLM output to single JSON file (all Excel files in one file)
        try:
            output_dir = Path("llm_outputs")
            output_dir.mkdir(exist_ok=True)
            output_file = output_dir / "all_llm_outputs.json"

            # Read existing outputs if file exists
            all_outputs = []
            if output_file.exists():
                try:
                    with open(output_file, "r", encoding="utf-8") as f:
                        all_outputs = json.load(f)
                except:
                    all_outputs = []

            # Add new output with only required fields
            new_entry = {
                "excel_file": excel_path.name,
                "sheet_name": sheet_name,
                "data": analysis_result
            }
            all_outputs.append(new_entry)

            # Write back in pretty format
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(all_outputs, f, indent=2, ensure_ascii=False)

            logger.info(f"Saved to {output_file} (total entries: {len(all_outputs)})")
        except Exception as e:
            logger.warning(f"Could not save to file: {e}")

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
