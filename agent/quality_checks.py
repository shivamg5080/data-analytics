"""
Quality Checks Module
=====================
Runs comprehensive data quality analysis: null counts, outlier detection,
mixed types, skewness, inconsistent labels, impossible dates, and more.
Never crashes on bad data.
"""

from __future__ import annotations

import logging
import re
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats as scipy_stats

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_quality_checks(
    df: pd.DataFrame,
    column_types: dict[str, str],
    analysis_columns: list[str],
    config: dict | None = None,
) -> dict[str, Any]:
    """
    Run full data quality analysis on the DataFrame.

    Returns
    -------
    dict with keys:
        - ``per_column``    : list[dict] — detailed quality result per column
        - ``overall``       : dict       — dataset-level summary
        - ``issues``        : list[dict] — all detected issues (severity, column, message)
        - ``quality_score`` : float      — 0-100 dataset quality score
    """
    cfg = (config or {}).get("quality", {})
    iqr_mult: float = cfg.get("outlier_iqr_multiplier", 1.5)
    z_thresh: float = cfg.get("outlier_zscore_threshold", 3.0)
    high_null: float = cfg.get("high_null_threshold", 0.50)
    skew_thresh: float = cfg.get("skewness_threshold", 1.0)

    issues: list[dict] = []
    per_column: list[dict] = []

    for col in analysis_columns:
        col_type = column_types.get(col, "unknown")
        series = df[col]
        result = _analyse_column(
            series, col, col_type, iqr_mult, z_thresh, high_null, skew_thresh, issues
        )
        per_column.append(result)

    overall = _dataset_overview(df, issues)
    quality_score = _compute_quality_score(df, issues)

    logger.info(
        "Quality checks complete. %d issue(s) found. Quality score: %.1f/100",
        len(issues), quality_score
    )

    return {
        "per_column": per_column,
        "overall": overall,
        "issues": issues,
        "quality_score": round(quality_score, 1),
    }


# ---------------------------------------------------------------------------
# Column-level analysis
# ---------------------------------------------------------------------------

def _analyse_column(
    series: pd.Series,
    col: str,
    col_type: str,
    iqr_mult: float,
    z_thresh: float,
    high_null: float,
    skew_thresh: float,
    issues: list[dict],
) -> dict:
    total = len(series)
    null_count = int(series.isna().sum())
    non_null_count = total - null_count
    null_pct = round(null_count / total * 100, 2) if total else 0
    non_null = series.dropna()
    unique_count = int(non_null.nunique())

    col_issues: list[str] = []

    # High null warning
    if null_pct / 100 >= high_null:
        msg = f"High null rate: {null_pct:.1f}%"
        col_issues.append(msg)
        _add_issue(issues, col, "warning", msg)

    # Mixed types
    if col_type == "text" or col_type == "categorical":
        mixed = _check_mixed_types(non_null)
        if mixed:
            col_issues.append(mixed)
            _add_issue(issues, col, "warning", mixed)

    # Leading/trailing whitespace in strings
    if pd.api.types.is_object_dtype(series):
        ws_count = _check_whitespace(non_null)
        if ws_count > 0:
            msg = f"{ws_count} value(s) have leading/trailing whitespace"
            col_issues.append(msg)
            _add_issue(issues, col, "info", msg)

    # Numeric-specific checks
    numeric_stats: dict = {}
    outliers_info: dict = {}
    if col_type == "numeric":
        numeric_series = _coerce_numeric(non_null)
        numeric_stats = _numeric_stats(numeric_series)

        # Outliers
        outliers_info = _detect_outliers(numeric_series, iqr_mult, z_thresh)
        if outliers_info["iqr_outlier_count"]:
            msg = (
                f"{outliers_info['iqr_outlier_count']} outlier(s) detected "
                f"(IQR method, range: [{outliers_info['iqr_lower']:.2f}, {outliers_info['iqr_upper']:.2f}])"
            )
            col_issues.append(msg)
            _add_issue(issues, col, "warning", msg)

        # Skewness
        if abs(numeric_stats.get("skewness", 0)) > skew_thresh:
            msg = f"Skewed distribution (skewness={numeric_stats['skewness']:.2f})"
            col_issues.append(msg)
            _add_issue(issues, col, "info", msg)

    # Datetime-specific checks
    datetime_issues: list[str] = []
    if col_type == "datetime":
        datetime_issues = _check_dates(non_null)
        for di in datetime_issues:
            col_issues.append(di)
            _add_issue(issues, col, "warning", di)

    # Categorical inconsistency
    cat_issues: list[str] = []
    if col_type == "categorical":
        cat_issues = _check_categorical_consistency(non_null)
        for ci in cat_issues:
            col_issues.append(ci)
            _add_issue(issues, col, "info", ci)

    return {
        "column": col,
        "type": col_type,
        "total_rows": total,
        "null_count": null_count,
        "non_null_count": non_null_count,
        "null_pct": null_pct,
        "non_null_pct": round(100 - null_pct, 2),
        "unique_count": unique_count,
        "issues": col_issues,
        "numeric_stats": numeric_stats,
        "outliers": outliers_info,
    }


def _numeric_stats(series: pd.Series) -> dict:
    """Return descriptive statistics for a numeric series."""
    if len(series) == 0:
        return {}
    try:
        return {
            "mean": round(float(series.mean()), 4),
            "median": round(float(series.median()), 4),
            "std": round(float(series.std()), 4),
            "min": round(float(series.min()), 4),
            "max": round(float(series.max()), 4),
            "q1": round(float(series.quantile(0.25)), 4),
            "q3": round(float(series.quantile(0.75)), 4),
            "skewness": round(float(scipy_stats.skew(series.dropna())), 4),
            "kurtosis": round(float(scipy_stats.kurtosis(series.dropna())), 4),
        }
    except Exception:
        return {}


def _detect_outliers(series: pd.Series, iqr_mult: float, z_thresh: float) -> dict:
    """Detect outliers using IQR and Z-score methods."""
    result = {
        "iqr_outlier_count": 0,
        "zscore_outlier_count": 0,
        "iqr_lower": None,
        "iqr_upper": None,
    }
    if len(series) < 4:
        return result
    try:
        q1, q3 = series.quantile(0.25), series.quantile(0.75)
        iqr = q3 - q1
        lower = q1 - iqr_mult * iqr
        upper = q3 + iqr_mult * iqr
        result["iqr_outlier_count"] = int(((series < lower) | (series > upper)).sum())
        result["iqr_lower"] = round(float(lower), 4)
        result["iqr_upper"] = round(float(upper), 4)

        z_scores = np.abs(scipy_stats.zscore(series.dropna()))
        result["zscore_outlier_count"] = int((z_scores > z_thresh).sum())
    except Exception:
        pass
    return result


def _check_mixed_types(non_null: pd.Series) -> str:
    """Check if a column has mixed Python types."""
    if not pd.api.types.is_object_dtype(non_null):
        return ""
    types_found = set(type(v).__name__ for v in non_null.head(500))
    types_found.discard("str")
    if len(types_found) > 1:
        return f"Mixed value types detected: {types_found}"
    if types_found and "float" in types_found or "int" in types_found:
        return f"Non-string values mixed with strings: {types_found}"
    return ""


def _check_whitespace(non_null: pd.Series) -> int:
    """Count string values with leading/trailing whitespace."""
    if not pd.api.types.is_object_dtype(non_null):
        return 0
    try:
        str_series = non_null.astype(str)
        return int((str_series != str_series.str.strip()).sum())
    except Exception:
        return 0


def _check_dates(non_null: pd.Series) -> list[str]:
    """Check for impossible or suspicious dates."""
    issues: list[str] = []
    try:
        if pd.api.types.is_datetime64_any_dtype(non_null):
            parsed = non_null
        else:
            parsed = pd.to_datetime(non_null, errors="coerce", infer_datetime_format=True)

        future = int((parsed > pd.Timestamp.now()).sum())
        past = int((parsed < pd.Timestamp("1900-01-01")).sum())
        if future:
            issues.append(f"{future} date(s) are in the future")
        if past:
            issues.append(f"{past} date(s) are before 1900 (possibly erroneous)")
    except Exception:
        pass
    return issues


def _check_categorical_consistency(non_null: pd.Series) -> list[str]:
    """
    Detect inconsistent labels in categorical columns:
    e.g., 'Yes' vs 'yes' vs 'YES', or extra whitespace variants.
    """
    issues: list[str] = []
    if not pd.api.types.is_object_dtype(non_null):
        return issues
    try:
        vals = non_null.astype(str)
        normalized = vals.str.strip().str.lower()
        if normalized.nunique() < vals.nunique():
            diff = vals.nunique() - normalized.nunique()
            issues.append(
                f"{diff} inconsistent label variant(s) found "
                f"(e.g. case/whitespace differences)"
            )
    except Exception:
        pass
    return issues


def _coerce_numeric(series: pd.Series) -> pd.Series:
    """Attempt to coerce object series to numeric."""
    if pd.api.types.is_numeric_dtype(series):
        return series.astype(float).dropna()
    try:
        return pd.to_numeric(
            series.astype(str).str.replace(",", "").str.strip(), errors="coerce"
        ).dropna()
    except Exception:
        return pd.Series(dtype=float)


# ---------------------------------------------------------------------------
# Dataset-level summary
# ---------------------------------------------------------------------------

def _dataset_overview(df: pd.DataFrame, issues: list[dict]) -> dict:
    total_cells = df.shape[0] * df.shape[1]
    total_nulls = int(df.isna().sum().sum())
    return {
        "total_rows": len(df),
        "total_columns": len(df.columns),
        "total_cells": total_cells,
        "total_nulls": total_nulls,
        "overall_null_pct": round(total_nulls / total_cells * 100, 2) if total_cells else 0,
        "total_issues": len(issues),
        "warnings": sum(1 for i in issues if i["severity"] == "warning"),
        "infos": sum(1 for i in issues if i["severity"] == "info"),
        "errors": sum(1 for i in issues if i["severity"] == "error"),
    }


def _compute_quality_score(df: pd.DataFrame, issues: list[dict]) -> float:
    """
    Compute a 0–100 quality score.
    Penalise for nulls, errors, and warnings.
    """
    score = 100.0
    total_cells = df.shape[0] * df.shape[1]
    if total_cells:
        null_pct = df.isna().sum().sum() / total_cells
        score -= null_pct * 40  # up to -40 for nulls

    for issue in issues:
        if issue["severity"] == "error":
            score -= 5
        elif issue["severity"] == "warning":
            score -= 2
        elif issue["severity"] == "info":
            score -= 0.5

    return max(0.0, min(100.0, score))


def _add_issue(issues: list[dict], column: str, severity: str, message: str) -> None:
    issues.append({"column": column, "severity": severity, "message": message})
