"""
Lightweight HTML-Based Excel Analysis Pipeline
Orchestrates Excel analysis workflow using HTML conversion:
- Column gap detection
- Table relationship understanding
"""

import asyncio
import os
import time
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime
import json
from openai import AsyncOpenAI
from logger import AppLogger
from vision_utils import analyze_column_usage_sequences, extract_columns_with_gap
from vision_analyzer import (
    analyze_sheet_with_vision,
    analyze_table_similarity,
    generate_gap_report
)
from request_context import get_request_id
import openpyxl

logger = AppLogger.get_logger(__file__)

#* 2) we are defining the function to process the excel with HTML-based analysis
async def process_excel_with_vision(
    excel_path: Path,
    analyze_gaps: bool = True,
    analyze_similarity: bool = True,
    openai_api_key: str = None,
    save_to_file: bool = True
) -> Dict[str, Any]:
    """
    HTML-based Excel analysis pipeline using GPT-4o.

    NEW APPROACH: Converts Excel sheets to HTML with full formatting preservation,
    then uses GPT-4o to analyze structure. More accurate than image-based analysis.

    Phases:
    1. Read sheet names from Excel file
    1.5. Deterministic column usage analysis
    2. Convert sheets to HTML and analyze with GPT-4o (parallel)
    3. Aggregate cross-sheet analysis (column gaps, table relationships)
    4. Generate consolidated report

    Focus:
    - Column gap detection (deterministic + HTML-based)
    - Table relationship understanding (same vs different tables)
    - Structure analysis without data extraction

    Args:
        excel_path: Path to Excel file
        analyze_gaps: Enable column gap detection (default: True)
        analyze_similarity: Enable table relationship analysis (default: True)
        openai_api_key: OpenAI API key
        save_to_file: Save analysis to JSON file (default: True)

    Returns:
        Analysis results with gap detection and table relationships
    """
    start_time = time.time()
    request_id = get_request_id()

    try:
        logger.info(f"Starting HTML-based analysis for {excel_path.name}")

        # Validate API key
        if not openai_api_key:
            raise ValueError("OpenAI API key is required for HTML-based analysis")

        # Initialize OpenAI client with extended timeout for processing
        client = AsyncOpenAI(
            api_key=openai_api_key,
            timeout=300.0  # 5 minutes per request
        )

        # Define output folders
        gap_analysis_folder = Path("gap_analysis")
        gap_analysis_folder.mkdir(parents=True, exist_ok=True)

        # Log enabled analysis types
        enabled_analyses = []
        if analyze_gaps:
            enabled_analyses.append('column_gaps')
        if analyze_similarity:
            enabled_analyses.append('table_relationships')

        logger.info(f"Analysis enabled: {', '.join(enabled_analyses) if enabled_analyses else 'none'}")

        # =================================================================
        # PHASE 1: GET SHEET NAMES FROM EXCEL
        # =================================================================
        logger.info(f"\n{'='*70}\nPHASE 1: READING EXCEL SHEETS\n{'='*70}\n")

        # Load workbook to get sheet names
        wb = openpyxl.load_workbook(excel_path, read_only=True)
        sheet_names = wb.sheetnames
        wb.close()

        if not sheet_names:
            raise ValueError(f"No sheets found in {excel_path.name}")

        logger.info(f"Found {len(sheet_names)} sheet(s): {', '.join(sheet_names)}")

        # Build sheet metadata
        successful_sheets = []
        for sheet_name in sheet_names:
            successful_sheets.append({
                "sheet_name": sheet_name,
                "excel_file": excel_path.name
            })

        logger.info(f"Phase 1 Complete: {len(successful_sheets)} sheets ready for analysis")

        # =================================================================
        # PHASE 1.5: EXCEL DATA ANALYSIS (DETERMINISTIC)
        # =================================================================
        logger.info(f"\n{'='*70}\nPHASE 1.5: EXCEL DATA ANALYSIS\n{'='*70}\n")
        logger.info(f"Analyzing column usage for {len(successful_sheets)} sheets...")

        excel_data_analyses = []
        for sheet_info in successful_sheets:
            sheet_name = sheet_info["sheet_name"]

            try:
                # Analyze column usage sequences
                column_usage = analyze_column_usage_sequences(
                    excel_path=excel_path,
                    sheet_name=sheet_name
                )
                excel_data_analyses.append(column_usage)
                gap_count = column_usage.get('total_gaps', 0)
                logger.info(f"Sheet '{sheet_name}': {gap_count} column gap(s) detected")
            except Exception as e:
                logger.error(f"Column analysis failed for sheet '{sheet_name}': {e}")
                # Add error result
                excel_data_analyses.append({
                    "sheet_name": sheet_name,
                    "error": str(e),
                    "total_gaps": 0,
                    "gap_summary": f"Analysis failed: {str(e)}",
                    "confidence": 0.0
                })

        logger.info(f"Phase 1.5 Complete: {len(excel_data_analyses)} sheets analyzed")

        # =================================================================
        # PHASE 2: HTML-BASED ANALYSIS (PARALLEL WITH CONCURRENCY CONTROL)
        # =================================================================
        logger.info(f"\n{'='*70}\nPHASE 2: HTML-BASED ANALYSIS\n{'='*70}\n")
        logger.info(f"Analyzing {len(successful_sheets)} sheets with controlled concurrency...")

        # Create semaphore to limit concurrent API calls (max 3 at a time)
        # This prevents overwhelming the OpenAI API and reduces timeouts
        MAX_CONCURRENT_REQUESTS = 3
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

        async def analyze_with_semaphore(sheet_info):
            """Wrapper to limit concurrent API calls using semaphore"""
            async with semaphore:
                sheet_name = sheet_info["sheet_name"]
                logger.info(f"Starting HTML-based analysis for sheet: {sheet_name}")

                try:
                    result = await analyze_sheet_with_vision(
                        client=client,
                        sheet_name=sheet_name,
                        excel_path=excel_path,
                    )
                    logger.info(f"Completed HTML-based analysis for sheet: {sheet_name}")
                    return result
                except Exception as e:
                    logger.error(f"HTML-based analysis failed for {sheet_name}: {e}")
                    return e

        # Create analysis tasks for all sheets
        analysis_tasks = [
            analyze_with_semaphore(sheet_info)
            for sheet_info in successful_sheets
        ]

        # Run all analyses with controlled concurrency
        logger.info(f"Processing {len(analysis_tasks)} sheets with max {MAX_CONCURRENT_REQUESTS} concurrent requests")
        html_analyses = await asyncio.gather(*analysis_tasks, return_exceptions=True)

        # Process results
        successful_analyses = []
        failed_analyses = []

        for i, result in enumerate(html_analyses):
            if isinstance(result, Exception):
                failed_analyses.append({
                    "sheet_name": successful_sheets[i]["sheet_name"],
                    "error": str(result)
                })
                logger.error(f"HTML-based analysis failed for {successful_sheets[i]['sheet_name']}: {result}")
            else:
                successful_analyses.append(result)
                logger.info(f"HTML-based analysis complete for {result.get('sheet_name', 'Unknown')}")

        logger.info(f"\nPhase 2 Complete:")
        logger.info(f"  Success: {len(successful_analyses)} sheets analyzed")
        logger.info(f"  Errors: {len(failed_analyses)}")

        if not successful_analyses:
            raise ValueError("All HTML-based analyses failed")

        # =================================================================
        # PHASE 3: AGGREGATE ANALYSIS ACROSS SHEETS
        # =================================================================
        logger.info(f"\n{'='*70}\nPHASE 3: AGGREGATE ANALYSIS\n{'='*70}\n")

        # Initialize analysis results
        gap_detection_result = {}
        table_similarity_result = {}

        # Run aggregation analyses
        if analyze_gaps:
            logger.info("Aggregating column gap detection across sheets...")
            gap_detection_result = await generate_gap_report(
                successful_analyses,
                excel_data_analyses=excel_data_analyses
            )

        if analyze_similarity:
            logger.info("Aggregating table relationships across sheets...")
            table_similarity_result = await analyze_table_similarity(successful_analyses)

        logger.info(f"Phase 3 Complete: Aggregation finished")

        # =================================================================
        # GENERATE CONSOLIDATED REPORT
        # =================================================================
        logger.info(f"\n{'='*70}\nGENERATING LIGHTWEIGHT ANALYSIS REPORT\n{'='*70}\n")

        processing_time_ms = int((time.time() - start_time) * 1000)

        # Build simplified response - take first sheet only
        if successful_analyses:
            analysis = successful_analyses[0]  # First sheet
            excel_data = excel_data_analyses[0] if excel_data_analyses else {}

            # Log warning if multiple sheets exist
            if len(successful_analyses) > 1:
                logger.warning(
                    f"Multiple sheets detected ({len(successful_analyses)}), "
                    f"using first sheet only: {analysis.get('sheet_name')}"
                )

            response = {
                "sheet_name": analysis.get("sheet_name", "Unknown"),
                "gap_summary": excel_data.get("gap_summary", ""),
                "columns_with_data": excel_data.get("columns_with_data", []),
                "columns_with_gap": extract_columns_with_gap(
                    excel_data.get("column_sequences", [])
                ),
                "classification": analysis.get("table_relationship", {}).get(
                    "classification", "unknown"
                ),
                "reasoning": analysis.get("table_relationship", {}).get(
                    "reasoning", ""
                )
            }
        else:
            # No successful analyses - return error structure
            logger.error("No successful sheet analyses available")
            response = {
                "sheet_name": "Error",
                "gap_summary": "Analysis failed - no sheets analyzed",
                "columns_with_data": [],
                "columns_with_gap": [],
                "classification": "error",
                "reasoning": "No sheets were successfully analyzed"
            }

        # Save simplified analysis to JSON file (if enabled)
        if save_to_file:
            analysis_file = gap_analysis_folder / f"{excel_path.stem}_lightweight_analysis.json"
            with open(analysis_file, "w", encoding="utf-8") as f:
                json.dump(response, f, indent=2, ensure_ascii=False)

            logger.info(f"Simplified analysis saved: {analysis_file.name}")
        else:
            logger.debug(f"File saving disabled, returning analysis in memory only")
        logger.info(f"Sheet: {response.get('sheet_name')}")
        logger.info(f"Columns with data: {len(response.get('columns_with_data', []))}")
        logger.info(f"Columns with gaps: {len(response.get('columns_with_gap', []))}")
        logger.info(f"Classification: {response.get('classification')}")

        logger.info(f"\n{'='*70}\nHTML-BASED ANALYSIS COMPLETE!\n{'='*70}")
        logger.info(f"Total sheets analyzed: {len(successful_analyses)}")
        logger.info(f"Processing time: {processing_time_ms}ms ({processing_time_ms/1000:.1f}s)")
        logger.info(f"Analysis method: HTML-based (no image conversion)")
        logger.info(f"{'='*70}\n")

        return response

    except Exception as e:
        logger.error(f"Error in HTML-based analysis pipeline: {e}", exc_info=True)
        raise RuntimeError(f"HTML-based analysis failed: {e}")
