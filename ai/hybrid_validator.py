"""
Hybrid Validator Module
Cross-validates vision and CSV analysis results to improve accuracy.

This module implements:
- Agreement/disagreement detection between vision and CSV results
- Reconciliation rules for handling disagreements
- Confidence scoring based on cross-validation
- Result merging into unified output
"""

from typing import Dict, Any, List, Tuple
from logger import AppLogger

logger = AppLogger.get_logger(__file__)


def compare_gap_detections(
    vision_gaps: List[Dict[str, Any]],
    csv_gaps: List[Dict[str, Any]],
    sheet_name: str
) -> Dict[str, Any]:
    """
    Compare gap detections from vision and CSV analysis.

    Args:
        vision_gaps: Column gaps detected by vision analysis
        csv_gaps: Column gaps detected by deterministic CSV analysis
        sheet_name: Name of the sheet being compared

    Returns:
        Dictionary containing:
        - agreements: Gaps both methods agree on
        - disagreements: Gaps only one method detected
        - vision_only: Gaps only vision detected
        - csv_only: Gaps only CSV detected
    """
    try:
        logger.info(f"Comparing gap detections for sheet '{sheet_name}'")

        # Extract column letters/indices from vision results
        vision_columns = set()
        for gap in vision_gaps:
            col_letter = gap.get("column_letter", "")
            if col_letter:
                vision_columns.add(col_letter)

        # Extract column indices from CSV results
        csv_indices = set()
        csv_gap_map = {}
        for gap in csv_gaps:
            col_idx = gap.get("column_index")
            if col_idx is not None:
                csv_indices.add(col_idx)
                csv_gap_map[col_idx] = gap

        # Find agreements and disagreements
        # Note: We need to map column letters to indices for comparison
        agreements = []
        vision_only = []
        csv_only = []

        # Check vision gaps
        for gap in vision_gaps:
            col_letter = gap.get("column_letter", "")
            # Try to convert column letter to index (A=0, B=1, C=2, etc.)
            if col_letter and len(col_letter) == 1:
                col_idx = ord(col_letter.upper()) - ord('A')
            elif col_letter and len(col_letter) == 2:
                # Handle AA, AB, etc.
                col_idx = (ord(col_letter[0].upper()) - ord('A') + 1) * 26 + (ord(col_letter[1].upper()) - ord('A'))
            else:
                col_idx = None

            if col_idx is not None and col_idx in csv_indices:
                # Agreement: both detected this gap
                agreements.append({
                    "column_letter": col_letter,
                    "column_index": col_idx,
                    "vision_gap": gap,
                    "csv_gap": csv_gap_map[col_idx],
                    "agreement_type": "both_detected"
                })
            else:
                # Vision only detected this gap
                vision_only.append({
                    "column_letter": col_letter,
                    "column_index": col_idx,
                    "vision_gap": gap,
                    "disagreement_type": "vision_only"
                })

        # Check CSV gaps
        for col_idx, csv_gap in csv_gap_map.items():
            # Convert index to column letter
            if col_idx < 26:
                col_letter = chr(ord('A') + col_idx)
            else:
                # Handle columns beyond Z (AA, AB, etc.)
                first_letter = chr(ord('A') + (col_idx // 26) - 1)
                second_letter = chr(ord('A') + (col_idx % 26))
                col_letter = first_letter + second_letter

            # Check if vision also detected this
            already_in_agreements = any(a["column_index"] == col_idx for a in agreements)

            if not already_in_agreements:
                # CSV only detected this gap
                csv_only.append({
                    "column_letter": col_letter,
                    "column_index": col_idx,
                    "csv_gap": csv_gap,
                    "disagreement_type": "csv_only"
                })

        logger.info(
            f"Comparison complete for '{sheet_name}': "
            f"{len(agreements)} agreements, {len(vision_only)} vision-only, {len(csv_only)} CSV-only"
        )

        return {
            "sheet_name": sheet_name,
            "agreements": agreements,
            "disagreements": vision_only + csv_only,
            "vision_only": vision_only,
            "csv_only": csv_only,
            "agreement_count": len(agreements),
            "disagreement_count": len(vision_only) + len(csv_only)
        }

    except Exception as e:
        logger.error(f"Error comparing gap detections for '{sheet_name}': {e}", exc_info=True)
        return {
            "sheet_name": sheet_name,
            "agreements": [],
            "disagreements": [],
            "vision_only": [],
            "csv_only": [],
            "error": str(e)
        }


def reconcile_disagreements(
    comparison_result: Dict[str, Any],
    reconciliation_mode: str = "balanced"
) -> List[Dict[str, Any]]:
    """
    Reconcile disagreements between vision and CSV analysis.

    Args:
        comparison_result: Result from compare_gap_detections()
        reconciliation_mode: How to handle disagreements
            - strict: Only include agreements
            - balanced: Include agreements + high-confidence disagreements
            - permissive: Include all detections

    Returns:
        List of reconciled gap detections with confidence scores
    """
    try:
        logger.info(f"Reconciling disagreements using '{reconciliation_mode}' mode")

        reconciled_gaps = []

        # Process agreements (always include these)
        for agreement in comparison_result.get("agreements", []):
            vision_gap = agreement.get("vision_gap", {})
            csv_gap = agreement.get("csv_gap", {})

            # Calculate hybrid confidence (both agree = high confidence)
            vision_conf = vision_gap.get("confidence", 0.5)
            csv_conf = csv_gap.get("confidence", 0.5)
            empty_pct = csv_gap.get("empty_percentage", 0)

            hybrid_conf = calculate_hybrid_confidence(
                vision_conf, csv_conf, agreement=True, empty_percentage=empty_pct
            )

            reconciled_gaps.append({
                "column_letter": agreement.get("column_letter"),
                "column_index": agreement.get("column_index"),
                "gap_type": csv_gap.get("gap_type", "detected_gap"),
                "empty_percentage": empty_pct,
                "confidence": hybrid_conf,
                "validation_status": "agreement",
                "vision_detected": True,
                "csv_detected": True,
                "vision_confidence": vision_conf,
                "csv_confidence": csv_conf,
                "reasoning": f"Both vision and CSV analysis agree on this gap ({empty_pct}% empty)"
            })

        # Process disagreements based on reconciliation mode
        if reconciliation_mode != "strict":
            # Handle vision-only detections
            for vision_only in comparison_result.get("vision_only", []):
                vision_gap = vision_only.get("vision_gap", {})
                vision_conf = vision_gap.get("confidence", 0.5)

                # In balanced mode, only include if vision confidence is high
                if reconciliation_mode == "permissive" or vision_conf >= 0.8:
                    hybrid_conf = calculate_hybrid_confidence(
                        vision_conf, 0.0, agreement=False, empty_percentage=0
                    )

                    reconciled_gaps.append({
                        "column_letter": vision_only.get("column_letter"),
                        "column_index": vision_only.get("column_index"),
                        "gap_type": "visual_gap",
                        "empty_percentage": 0,
                        "confidence": hybrid_conf,
                        "validation_status": "vision_only",
                        "vision_detected": True,
                        "csv_detected": False,
                        "vision_confidence": vision_conf,
                        "csv_confidence": 0.0,
                        "reasoning": "Only vision analysis detected this gap - may be visual separator or false positive"
                    })

            # Handle CSV-only detections
            for csv_only in comparison_result.get("csv_only", []):
                csv_gap = csv_only.get("csv_gap", {})
                csv_conf = csv_gap.get("confidence", 0.5)
                empty_pct = csv_gap.get("empty_percentage", 0)

                # CSV is deterministic, so trust it (especially if high empty %)
                if reconciliation_mode == "permissive" or empty_pct >= 95:
                    hybrid_conf = calculate_hybrid_confidence(
                        0.0, csv_conf, agreement=False, empty_percentage=empty_pct
                    )

                    reconciled_gaps.append({
                        "column_letter": csv_only.get("column_letter"),
                        "column_index": csv_only.get("column_index"),
                        "gap_type": csv_gap.get("gap_type", "data_gap"),
                        "empty_percentage": empty_pct,
                        "confidence": hybrid_conf,
                        "validation_status": "csv_only",
                        "vision_detected": False,
                        "csv_detected": True,
                        "vision_confidence": 0.0,
                        "csv_confidence": csv_conf,
                        "reasoning": f"CSV analysis detected {empty_pct}% empty column, but vision may have missed it"
                    })

        logger.info(f"Reconciliation complete: {len(reconciled_gaps)} total gaps after reconciliation")

        return reconciled_gaps

    except Exception as e:
        logger.error(f"Error reconciling disagreements: {e}", exc_info=True)
        return []


def calculate_hybrid_confidence(
    vision_confidence: float,
    csv_confidence: float,
    agreement: bool,
    empty_percentage: float
) -> float:
    """
    Calculate hybrid confidence score based on agreement and evidence.

    Args:
        vision_confidence: Confidence from vision analysis (0-1)
        csv_confidence: Confidence from CSV analysis (0-1)
        agreement: Whether both methods agree
        empty_percentage: Percentage of empty cells in column (0-100)

    Returns:
        Hybrid confidence score (0-1)
    """
    if agreement:
        # Both agree - high confidence
        # Average the confidences and boost slightly
        base_confidence = (vision_confidence + csv_confidence) / 2
        boost = 0.1  # Boost for agreement
        return min(1.0, base_confidence + boost)

    else:
        # Disagreement - use evidence to determine confidence
        # CSV is deterministic, so trust empty_percentage
        if empty_percentage >= 95:
            # Very strong evidence from CSV
            return 0.9
        elif empty_percentage >= 80:
            # Moderate evidence from CSV
            return 0.7
        elif vision_confidence >= 0.8:
            # High vision confidence but no CSV confirmation
            return 0.6
        else:
            # Low confidence overall
            return 0.4


def merge_results(
    vision_result: Dict[str, Any],
    csv_result: Dict[str, Any],
    validation_metadata: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Merge vision and CSV results into unified hybrid result.

    Args:
        vision_result: Complete vision analysis result
        csv_result: Complete CSV analysis result
        validation_metadata: Validation information from cross-validation

    Returns:
        Unified hybrid analysis result
    """
    try:
        logger.info("Merging vision and CSV results into hybrid result")

        hybrid_result = {
            "analysis_type": "hybrid_vision_csv",
            "excel_file": vision_result.get("excel_file", csv_result.get("excel_file", "unknown")),
            "sheets_analyzed": vision_result.get("sheets_analyzed", csv_result.get("sheets_analyzed", 0)),
            "timestamp": vision_result.get("timestamp", csv_result.get("timestamp")),

            # Hybrid validated gaps
            "validated_gaps": validation_metadata.get("reconciled_gaps", []),

            # Validation statistics
            "validation_summary": {
                "total_agreements": validation_metadata.get("total_agreements", 0),
                "total_disagreements": validation_metadata.get("total_disagreements", 0),
                "vision_only_detections": validation_metadata.get("vision_only_count", 0),
                "csv_only_detections": validation_metadata.get("csv_only_count", 0),
                "reconciliation_mode": validation_metadata.get("reconciliation_mode", "balanced"),
                "agreement_rate": validation_metadata.get("agreement_rate", 0.0)
            },

            # Raw results for reference
            "vision_analysis": vision_result,
            "csv_analysis": csv_result,

            # Processing metadata
            "processing_time_ms": (
                vision_result.get("processing_time_ms", 0) +
                csv_result.get("processing_time_ms", 0)
            ),

            # Output files
            "output_files": {
                **vision_result.get("output_files", {}),
                **csv_result.get("output_files", {})
            }
        }

        logger.info("Results merged successfully")
        return hybrid_result

    except Exception as e:
        logger.error(f"Error merging results: {e}", exc_info=True)
        return {
            "analysis_type": "hybrid_vision_csv_error",
            "error": str(e),
            "vision_result": vision_result,
            "csv_result": csv_result
        }


def generate_validation_report(
    all_sheet_comparisons: List[Dict[str, Any]],
    reconciliation_mode: str
) -> Dict[str, Any]:
    """
    Generate comprehensive validation report across all sheets.

    Args:
        all_sheet_comparisons: List of comparison results from all sheets
        reconciliation_mode: Reconciliation mode used

    Returns:
        Validation report with statistics and insights
    """
    try:
        total_agreements = sum(c.get("agreement_count", 0) for c in all_sheet_comparisons)
        total_disagreements = sum(c.get("disagreement_count", 0) for c in all_sheet_comparisons)
        vision_only_count = sum(len(c.get("vision_only", [])) for c in all_sheet_comparisons)
        csv_only_count = sum(len(c.get("csv_only", [])) for c in all_sheet_comparisons)

        total_detections = total_agreements + total_disagreements
        agreement_rate = (total_agreements / total_detections * 100) if total_detections > 0 else 0

        report = {
            "reconciliation_mode": reconciliation_mode,
            "total_agreements": total_agreements,
            "total_disagreements": total_disagreements,
            "vision_only_count": vision_only_count,
            "csv_only_count": csv_only_count,
            "agreement_rate": round(agreement_rate, 2),
            "by_sheet": all_sheet_comparisons
        }

        logger.info(
            f"Validation report: {total_agreements} agreements ({agreement_rate:.1f}% agreement rate), "
            f"{total_disagreements} disagreements"
        )

        return report

    except Exception as e:
        logger.error(f"Error generating validation report: {e}", exc_info=True)
        return {
            "error": str(e),
            "by_sheet": all_sheet_comparisons
        }
