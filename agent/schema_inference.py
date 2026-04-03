"""
Schema Inference Module
=======================
Detects column data types, identifies columns to ignore, and builds a
complete data dictionary for every column in the DataFrame.
"""

from __future__ import annotations

import logging
import re
from typing import Any

import numpy as np
import pandas as pd
from dateutil import parser as dateutil_parser

logger = logging.getLogger(__name__)

# Inferred type labels
TYPE_NUMERIC = "numeric"
TYPE_CATEGORICAL = "categorical"
TYPE_DATETIME = "datetime"
TYPE_BOOLEAN = "boolean"
TYPE_TEXT = "text"
TYPE_IDENTIFIER = "identifier"
TYPE_EMPTY = "empty"
TYPE_CONSTANT = "constant"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def infer_schema(df: pd.DataFrame, config: dict | None = None) -> dict[str, Any]:
    """
    Infer the schema of every column in the DataFrame.

    Returns
    -------
    dict with keys:
        - ``data_dictionary``  : list[dict] — one entry per column
        - ``ignored_columns``  : list[str]  — columns flagged for exclusion
        - ``column_types``     : dict[str, str] — col → inferred type
        - ``analysis_columns`` : list[str]  — columns to include in analysis
    """
    cfg = (config or {}).get("schema_inference", {})
    dt_thresh: float = cfg.get("datetime_threshold", 0.85)
    num_thresh: float = cfg.get("numeric_threshold", 0.90)
    cat_ratio: float = cfg.get("categorical_max_unique_ratio", 0.20)
    id_ratio: float = cfg.get("id_min_unique_ratio", 0.95)
    bool_vals: dict = cfg.get("boolean_values", {
        "true": ["true", "yes", "1", "y", "t"],
        "false": ["false", "no", "0", "n", "f"],
    })

    data_dict: list[dict] = []
    ignored: list[str] = []
    col_types: dict[str, str] = {}

    for col in df.columns:
        series = df[col]
        entry = _build_column_entry(
            series, col, dt_thresh, num_thresh, cat_ratio, id_ratio, bool_vals
        )
        data_dict.append(entry)
        col_types[col] = entry["inferred_type"]

        if entry["ignore"]:
            ignored.append(col)
            logger.debug("Column '%s' flagged for exclusion: %s", col, entry["ignore_reason"])

    analysis_cols = [c for c in df.columns if c not in ignored]
    logger.info(
        "Schema inference complete. %d columns analysed, %d ignored.",
        len(df.columns), len(ignored)
    )

    return {
        "data_dictionary": data_dict,
        "ignored_columns": ignored,
        "column_types": col_types,
        "analysis_columns": analysis_cols,
    }


# ---------------------------------------------------------------------------
# Column-level analysis
# ---------------------------------------------------------------------------

def _build_column_entry(
    series: pd.Series,
    col_name: str,
    dt_thresh: float,
    num_thresh: float,
    cat_ratio: float,
    id_ratio: float,
    bool_vals: dict,
) -> dict:
    """Build a complete data-dictionary entry for a single column."""
    total = len(series)
    null_count = int(series.isna().sum())
    non_null_count = total - null_count
    null_pct = round(null_count / total * 100, 2) if total else 0
    non_null_pct = round(100 - null_pct, 2)

    non_null = series.dropna()
    unique_count = int(non_null.nunique())
    unique_ratio = unique_count / non_null_count if non_null_count else 0

    sample_values = _get_sample_values(non_null)
    anomalies: list[str] = []

    # ---- Type inference ------------------------------------------------
    inferred_type = _infer_type(
        series, non_null, unique_ratio, dt_thresh, num_thresh,
        cat_ratio, id_ratio, bool_vals, anomalies
    )

    # ---- Ignore flags --------------------------------------------------
    ignore = False
    ignore_reason = ""

    if inferred_type == TYPE_EMPTY:
        ignore = True
        ignore_reason = "Column is fully empty"
    elif inferred_type == TYPE_CONSTANT:
        ignore = True
        ignore_reason = f"Column has only one unique value: {sample_values[0] if sample_values else 'N/A'}"
    elif inferred_type == TYPE_IDENTIFIER:
        ignore = True
        ignore_reason = f"High-cardinality identifier column (unique ratio={unique_ratio:.2%})"

    return {
        "column_name": col_name,
        "inferred_type": inferred_type,
        "total_rows": total,
        "null_count": null_count,
        "non_null_count": non_null_count,
        "null_pct": null_pct,
        "non_null_pct": non_null_pct,
        "unique_count": unique_count,
        "unique_ratio": round(unique_ratio, 4),
        "sample_values": sample_values,
        "anomalies": anomalies,
        "ignore": ignore,
        "ignore_reason": ignore_reason,
    }


def _infer_type(
    series: pd.Series,
    non_null: pd.Series,
    unique_ratio: float,
    dt_thresh: float,
    num_thresh: float,
    cat_ratio: float,
    id_ratio: float,
    bool_vals: dict,
    anomalies: list[str],
) -> str:
    """Core type inference logic."""
    if len(non_null) == 0:
        return TYPE_EMPTY

    if non_null.nunique() <= 1:
        return TYPE_CONSTANT

    # Already numeric dtype
    if pd.api.types.is_numeric_dtype(series):
        if unique_ratio >= id_ratio and non_null.nunique() > 50:
            return TYPE_IDENTIFIER
        if non_null.nunique() <= 2:
            vals = set(non_null.unique())
            if vals <= {0, 1}:
                return TYPE_BOOLEAN
        if unique_ratio <= cat_ratio and non_null.nunique() <= 30:
            return TYPE_CATEGORICAL
        return TYPE_NUMERIC

    # Already datetime dtype
    if pd.api.types.is_datetime64_any_dtype(series):
        return TYPE_DATETIME

    # Boolean check on object columns
    if _is_boolean(non_null, bool_vals):
        return TYPE_BOOLEAN

    # Datetime check on string columns
    if _is_datetime(non_null, dt_thresh, anomalies):
        return TYPE_DATETIME

    # Numeric check on string columns (numbers stored as text)
    if _is_numeric_string(non_null, num_thresh, anomalies):
        if unique_ratio >= id_ratio and non_null.nunique() > 50:
            return TYPE_IDENTIFIER
        if unique_ratio <= cat_ratio and non_null.nunique() <= 30:
            return TYPE_CATEGORICAL
        return TYPE_NUMERIC

    # Identifier check
    if unique_ratio >= id_ratio and len(non_null) > 100:
        return TYPE_IDENTIFIER

    # Categorical vs text
    if unique_ratio <= cat_ratio:
        return TYPE_CATEGORICAL

    return TYPE_TEXT


def _is_boolean(non_null: pd.Series, bool_vals: dict) -> bool:
    """Check if a column contains only boolean-like string values."""
    all_true = set(str(v).strip().lower() for v in bool_vals.get("true", []))
    all_false = set(str(v).strip().lower() for v in bool_vals.get("false", []))
    valid = all_true | all_false
    sample_lower = {str(v).strip().lower() for v in non_null.unique()}
    return sample_lower <= valid


def _is_datetime(non_null: pd.Series, threshold: float, anomalies: list[str]) -> bool:
    """Try parsing values as dates; return True if >= threshold succeed."""
    if not pd.api.types.is_object_dtype(non_null):
        return False
    sample = non_null.head(200)
    parsed = 0
    for val in sample:
        try:
            dateutil_parser.parse(str(val), fuzzy=False)
            parsed += 1
        except Exception:
            pass
    ratio = parsed / len(sample) if len(sample) else 0
    if 0 < ratio < threshold:
        anomalies.append(f"Mixed datetime parsing success ({ratio:.0%}); may be noisy dates.")
    return ratio >= threshold


def _is_numeric_string(non_null: pd.Series, threshold: float, anomalies: list[str]) -> bool:
    """Check if string column contains numbers stored as text."""
    if not pd.api.types.is_object_dtype(non_null):
        return False
    sample = non_null.head(200)
    converted = pd.to_numeric(sample.astype(str).str.replace(",", "").str.strip(), errors="coerce")
    ratio = converted.notna().sum() / len(sample) if len(sample) else 0
    if ratio >= threshold:
        anomalies.append("Numeric values stored as text; will be coerced during analysis.")
    return ratio >= threshold


def _get_sample_values(non_null: pd.Series, n: int = 5) -> list:
    """Return up to n representative sample values."""
    if len(non_null) == 0:
        return []
    uniq = non_null.unique()
    sample = uniq[:n]
    return [str(v) for v in sample]
