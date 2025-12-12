"""Utility functions - Pure helpers without external dependencies."""
from typing import Optional, List, Dict, Any


def normalize_intent_for_case_insensitive(intent: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize string values in intent JSON to lowercase for case-insensitive matching."""
    string_columns = ["Company Name", "Model Name", "Processor"]

    # Normalize constraints
    if "constraints" in intent:
        for constraint in intent["constraints"]:
            col = constraint.get("column", "")
            value = constraint.get("value")
            if col in string_columns and isinstance(value, str):
                constraint["value"] = value.lower()

    # Normalize models_to_compare
    if "models_to_compare" in intent:
        intent["models_to_compare"] = [
            model.lower() if isinstance(model, str) else model
            for model in intent["models_to_compare"]
        ]

    return intent


def filters_to_constraints(
    company_filter: Optional[str] = None,
    price_min: Optional[int] = None,
    price_max: Optional[int] = None,
    camera_min: Optional[int] = None,
    camera_max: Optional[int] = None,
    battery_min: Optional[int] = None,
    battery_max: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Convert filter values to constraints format for SQL generation."""
    constraints = []

    if company_filter:
        constraints.append({
            "column": "Company Name",
            "operator": "==",
            "value": company_filter.lower() if isinstance(company_filter, str) else company_filter,
        })

    if price_min is not None:
        constraints.append({
            "column": "Launched Price (INR)",
            "operator": ">=",
            "value": price_min,
        })

    if price_max is not None:
        constraints.append({
            "column": "Launched Price (INR)",
            "operator": "<=",
            "value": price_max,
        })

    if camera_min is not None:
        constraints.append({
            "column": "Back Camera (MP)",
            "operator": ">=",
            "value": camera_min,
        })

    if camera_max is not None:
        constraints.append({
            "column": "Back Camera (MP)",
            "operator": "<=",
            "value": camera_max,
        })

    if battery_min is not None:
        constraints.append({
            "column": "Battery Capacity (mAh)",
            "operator": ">=",
            "value": battery_min,
        })

    if battery_max is not None:
        constraints.append({
            "column": "Battery Capacity (mAh)",
            "operator": "<=",
            "value": battery_max,
        })

    return constraints
