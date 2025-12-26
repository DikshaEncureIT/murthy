"""
Lightweight Vision Processing Pipeline
Orchestrates lightweight visual analysis workflow:
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
from vision_utils import convert_all_sheets_to_images, analyze_column_usage_sequences, extract_columns_with_gap
from vision_analyzer import (
    analyze_sheet_with_vision,
    analyze_table_similarity,
    generate_gap_report
)
from request_context import get_request_id

logger = AppLogger.get_logger(__file__)

#* 2) we are defining the function to process the excel with vision
async def process_excel_with_vision(
    excel_path: Path,
    analyze_gaps: bool = True,
    analyze_similarity: bool = True,
    openai_api_key: str = None,
    save_to_file: bool = True
) -> Dict[str, Any]:
    """
    Lightweight vision-based Excel analysis pipeline.

    Phases:
    1. Convert all sheets to images (parallel)
    2. Analyze each sheet with vision model (parallel)
    3. Aggregate cross-sheet analysis (column gaps, table relationships)
    4. Generate consolidated report

    Focus:
    - Column gap detection
    - Table relationship understanding (same vs different tables)
    - NO data extraction or quality metrics

    Args:
        excel_path: Path to Excel file
        analyze_gaps: Enable column gap detection (default: True)
        analyze_similarity: Enable table relationship analysis (default: True)
        openai_api_key: OpenAI API key
        save_to_file: Save analysis to JSON file (default: True)

    Returns:
        Lightweight visual analysis results
    """
    start_time = time.time()
    request_id = get_request_id()

    try:
        logger.info(f"Starting vision-based analysis for {excel_path.name}")

        # Validate API key
        if not openai_api_key:
            raise ValueError("OpenAI API key is required for vision analysis")

        # Initialize OpenAI client with extended timeout for vision processing
        client = AsyncOpenAI(
            api_key=openai_api_key,
            timeout=300.0  # 5 minutes per request (handles large images better)
        )

        # Define output folders
        screenshots_folder = Path("screenshots")
        gap_analysis_folder = Path("gap_analysis")
        screenshots_folder.mkdir(parents=True, exist_ok=True)
        gap_analysis_folder.mkdir(parents=True, exist_ok=True)

        # Log enabled analysis types
        enabled_analyses = []
        if analyze_gaps:
            enabled_analyses.append('column_gaps')
        if analyze_similarity:
            enabled_analyses.append('table_relationships')

        logger.info(f"Lightweight analysis enabled: {', '.join(enabled_analyses) if enabled_analyses else 'none'}")

        # =================================================================
        # PHASE 1: CONVERT ALL SHEETS TO IMAGES (PARALLEL)
        # =================================================================
        logger.info(f"\n{'='*70}\nPHASE 1: CONVERTING SHEETS TO IMAGES\n{'='*70}\n")

        #* 3) we are converting all sheets to images
        image_results = await convert_all_sheets_to_images(
            excel_path=excel_path,
            output_folder=screenshots_folder
        )

        if not image_results:
            raise ValueError(f"No sheets could be converted to images from {excel_path.name}")

        # Filter out failed conversions
        successful_images = [r for r in image_results if r.get("image_path") and not r.get("error")]
        failed_images = [r for r in image_results if r.get("error")]

        logger.info(f"Phase 1 Complete: {len(successful_images)} sheets converted, {len(failed_images)} failed")

        if not successful_images:
            raise ValueError("All sheet conversions failed")

        # =================================================================
        # PHASE 1.5: EXCEL DATA ANALYSIS (DETERMINISTIC)
        # =================================================================
        logger.info(f"\n{'='*70}\nPHASE 1.5: EXCEL DATA ANALYSIS\n{'='*70}\n")
        logger.info(f"Analyzing column usage for {len(successful_images)} sheets...")

        excel_data_analyses = []
        for image_result in successful_images:
            sheet_name = image_result["sheet_name"]

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
        # PHASE 2: LIGHTWEIGHT VISION ANALYSIS (PARALLEL WITH CONCURRENCY CONTROL)
        # =================================================================
        logger.info(f"\n{'='*70}\nPHASE 2: LIGHTWEIGHT VISION ANALYSIS\n{'='*70}\n")
        logger.info(f"Analyzing {len(successful_images)} sheets with controlled concurrency...")

        # Create semaphore to limit concurrent API calls (max 3 at a time)
        # This prevents overwhelming the OpenAI API and reduces timeouts
        MAX_CONCURRENT_REQUESTS = 3
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

        async def analyze_with_semaphore(image_result):
            """Wrapper to limit concurrent API calls using semaphore"""
            async with semaphore:
                sheet_name = image_result["sheet_name"]
                image_path = Path(image_result["image_path"])
                logger.info(f"Starting vision analysis for sheet: {sheet_name}")

                try:
                    result = await analyze_sheet_with_vision(
                        client=client,
                        image_path=image_path,
                        sheet_name=sheet_name
                    )
                    logger.info(f"Completed vision analysis for sheet: {sheet_name}")
                    return result
                except Exception as e:
                    logger.error(f"Vision analysis failed for {sheet_name}: {e}")
                    return e

        # Create analysis tasks for all sheets
        analysis_tasks = [
            analyze_with_semaphore(image_result)
            for image_result in successful_images
        ]

        # Run all vision analyses with controlled concurrency
        logger.info(f"Processing {len(analysis_tasks)} sheets with max {MAX_CONCURRENT_REQUESTS} concurrent requests")
        vision_analyses = await asyncio.gather(*analysis_tasks, return_exceptions=True)

        # Process results
        successful_analyses = []
        failed_analyses = []

        for i, result in enumerate(vision_analyses):
            if isinstance(result, Exception):
                failed_analyses.append({
                    "sheet_name": successful_images[i]["sheet_name"],
                    "error": str(result)
                })
                logger.error(f"Vision analysis failed for {successful_images[i]['sheet_name']}: {result}")
            else:
                successful_analyses.append(result)
                logger.info(f"Vision analysis complete for {result.get('sheet_name', 'Unknown')}")

        logger.info(f"\nPhase 2 Complete:")
        logger.info(f"  Success: {len(successful_analyses)} sheets analyzed")
        logger.info(f"  Errors: {len(failed_analyses)}")

        if not successful_analyses:
            raise ValueError("All vision analyses failed")

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

        logger.info(f"\n{'='*70}\nLIGHTWEIGHT VISION ANALYSIS COMPLETE!\n{'='*70}")
        logger.info(f"Total sheets analyzed: {len(successful_analyses)}")
        logger.info(f"Processing time: {processing_time_ms}ms ({processing_time_ms/1000:.1f}s)")
        logger.info(f"{'='*70}\n")

        return response

    except Exception as e:
        logger.error(f"Error in vision processing pipeline: {e}", exc_info=True)
        raise RuntimeError(f"Vision processing failed: {e}")
