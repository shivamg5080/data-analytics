"""
Ingestion Module
================
Handles loading Excel files (.xlsx, .xls), detecting the best sheet,
inferring actual table start rows, handling merged cells, duplicate headers,
hidden rows/columns, and multi-row headers.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

import numpy as np
import openpyxl
import pandas as pd
from openpyxl.utils import get_column_letter

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_excel(file_path: str | Path | Any, filename: str | None = None, config: dict | None = None) -> dict[str, Any]:
    """
    Load an Excel or CSV file and return a structured result.
    """
    cfg = config or {}
    sd_cfg = cfg.get("sheet_detection", {})
    prefer_largest: bool = sd_cfg.get("prefer_largest", True)
    skip_hidden: bool = sd_cfg.get("skip_hidden_sheets", True)
    max_scan_rows: int = sd_cfg.get("max_header_scan_rows", 20)

    warnings: list[str] = []

    # Handle bytesio or file
    if hasattr(file_path, "read"):
        file_to_open = file_path
        file_name_display = filename or "uploaded_file"
        file_suffix = Path(file_name_display).suffix.lower() if filename else ".xlsx"
    else:
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        file_to_open = str(file_path)
        file_name_display = str(file_path.name)
        file_suffix = file_path.suffix.lower()

    if file_suffix not in {".xlsx", ".xls", ".xlsm", ".csv"}:
        raise ValueError(f"Unsupported file type: {file_suffix}. Only .xlsx/.xls/.csv supported.")

    logger.info("Loading file: %s", file_name_display)

    if file_suffix == ".csv":
        all_sheets = ["CSV Data"]
        best_sheet = "CSV Data"
        try:
            if hasattr(file_to_open, "seek"):
                file_to_open.seek(0)
            raw_df = pd.read_csv(file_to_open)
            skipped_rows = 0
            sheet_warnings = []
        except Exception as exc:
            raise RuntimeError(f"Failed to read CSV: {exc}") from exc
    else:
        # ---- Read all sheet names -------------------------------------------
        try:
            all_sheets = _get_sheet_names(file_to_open, file_suffix, skip_hidden=skip_hidden)
        except Exception as exc:
            raise RuntimeError(f"Failed to open Excel file: {exc}") from exc

        if not all_sheets:
            raise ValueError("No readable sheets found in the Excel file.")

        logger.info("Sheets found: %s", all_sheets)

        # ---- Choose best sheet ----------------------------------------------
        best_sheet = _pick_best_sheet(file_to_open, all_sheets, prefer_largest)
        logger.info("Selected sheet: '%s'", best_sheet)

        # ---- Load the raw data ---------------------------------------------
        raw_df, skipped_rows, sheet_warnings = _load_sheet(
            file_to_open, file_suffix, best_sheet, max_scan_rows
        )
    warnings.extend(sheet_warnings)

    # ---- Post-process --------------------------------------------------
    raw_df = _resolve_duplicate_columns(raw_df, warnings)
    raw_df = _strip_whitespace_headers(raw_df)
    raw_df = _sanitize_column_names(raw_df)
    raw_df = _drop_fully_empty(raw_df, warnings)

    logger.info(
        "Loaded sheet '%s': %d rows x %d cols (skipped %d header rows)",
        best_sheet, len(raw_df), len(raw_df.columns), skipped_rows,
    )

    return {
        "df": raw_df,
        "dataframe": raw_df,  # Add dataframe key for tests/orchestrator
        "sheet_name": best_sheet,
        "all_sheets": all_sheets,
        "skipped_rows": skipped_rows,
        "warnings": warnings,
        "file_path": file_name_display,
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_sheet_names(file_to_open: Any, file_suffix: str, skip_hidden: bool) -> list[str]:
    """Return sheet names, optionally filtering hidden sheets."""
    if file_suffix in {".xlsx", ".xlsm"}:
        wb = openpyxl.load_workbook(file_to_open, read_only=True, data_only=True)
        names: list[str] = []
        for ws in wb.worksheets:
            if skip_hidden and ws.sheet_state != "visible":
                logger.debug("Skipping hidden sheet: %s", ws.title)
                continue
            names.append(ws.title)
        wb.close()
        return names
    else:
        # xlrd for .xls
        import xlrd  # type: ignore
        if hasattr(file_to_open, "read"):
            file_to_open.seek(0)
            wb = xlrd.open_workbook(file_contents=file_to_open.read())
        else:
            wb = xlrd.open_workbook(file_to_open)
        names = []
        for i, name in enumerate(wb.sheet_names()):
            if skip_hidden:
                sheet = wb.sheet_by_name(name)
                if sheet.visibility != 0:
                    continue
            names.append(name)
        return names


def _pick_best_sheet(
    file_to_open: Any, sheet_names: list[str], prefer_largest: bool
) -> str:
    """Pick the sheet most likely to contain the primary dataset."""
    if len(sheet_names) == 1:
        return sheet_names[0]

    # Score each sheet
    scores: dict[str, float] = {}
    for name in sheet_names:
        try:
            if hasattr(file_to_open, "seek"):
                file_to_open.seek(0)
            df = pd.read_excel(
                file_to_open, sheet_name=name, nrows=500, header=None
            )
            non_empty = df.notna().sum().sum()
            row_score = len(df)
            col_score = len(df.columns)
            scores[name] = non_empty + row_score + col_score
        except Exception:
            scores[name] = 0.0

    if prefer_largest:
        best = max(scores, key=lambda k: scores[k])
    else:
        # First non-empty sheet
        best = next((n for n in sheet_names if scores.get(n, 0) > 0), sheet_names[0])

    logger.debug("Sheet scores: %s → chosen '%s'", scores, best)
    return best


def _load_sheet(
    file_to_open: Any, file_suffix: str, sheet_name: str, max_scan_rows: int
) -> tuple[pd.DataFrame, int, list[str]]:
    """
    Load a single sheet, auto-detecting the header row.
    Returns (DataFrame, skipped_rows, warnings).
    """
    warnings: list[str] = []

    # Read raw without assuming any header so we can scan
    try:
        if hasattr(file_to_open, "seek"):
            file_to_open.seek(0)
        raw = pd.read_excel(
            file_to_open,
            sheet_name=sheet_name,
            header=None,
            nrows=max_scan_rows + 500,
        )
    except Exception as exc:
        raise RuntimeError(
            f"Failed to read sheet '{sheet_name}': {exc}"
        ) from exc

    if raw.empty:
        warnings.append(f"Sheet '{sheet_name}' appears to be empty.")
        return pd.DataFrame(), 0, warnings

    # Detect the actual header row
    header_row = _detect_header_row(raw, max_scan_rows)
    logger.debug("Detected header row index: %d", header_row)

    if header_row > 0:
        warnings.append(
            f"Sheet '{sheet_name}': skipped {header_row} metadata/title row(s) "
            f"before actual table header."
        )

    # Reload with proper header
    try:
        if hasattr(file_to_open, "seek"):
            file_to_open.seek(0)
        df = pd.read_excel(
            file_to_open,
            sheet_name=sheet_name,
            header=header_row,
            engine=_pick_engine(file_suffix),
        )
    except Exception as exc:
        # Fallback — use raw
        warnings.append(f"Re-read with header={header_row} failed; using raw. Error: {exc}")
        df = raw.iloc[header_row + 1 :].copy()
        df.columns = raw.iloc[header_row].tolist()

    return df, header_row, warnings


def _detect_header_row(raw: pd.DataFrame, max_scan_rows: int) -> int:
    """
    Heuristic: scan the first `max_scan_rows` rows and pick the row most
    likely to be the header (densest mix of string labels, low nulls).
    """
    scan = raw.iloc[: min(max_scan_rows, len(raw))]
    best_row = 0
    best_score = -1.0

    for idx in range(len(scan)):
        row = scan.iloc[idx]
        non_null = row.notna().sum()
        if non_null == 0:
            continue
        string_count = sum(1 for v in row if isinstance(v, str) and v.strip())
        # Headers tend to be all-string and dense
        score = string_count / max(len(row), 1)
        # Penalise rows that look like data (all numbers)
        numeric_count = sum(1 for v in row if isinstance(v, (int, float)) and not np.isnan(float(v) if isinstance(v, float) else v))
        if numeric_count > string_count:
            score *= 0.3
        if score > best_score:
            best_score = score
            best_row = idx

    return best_row


def _resolve_duplicate_columns(df: pd.DataFrame, warnings: list[str]) -> pd.DataFrame:
    """Rename duplicate column names by appending _1, _2, …"""
    cols = list(df.columns)
    seen: dict[str, int] = {}
    new_cols: list[str] = []
    for col in cols:
        col_str = str(col)
        if col_str in seen:
            seen[col_str] += 1
            new_name = f"{col_str}_{seen[col_str]}"
            warnings.append(f"Duplicate column '{col_str}' renamed to '{new_name}'.")
            new_cols.append(new_name)
        else:
            seen[col_str] = 0
            new_cols.append(col_str)
    df.columns = new_cols
    return df


def _strip_whitespace_headers(df: pd.DataFrame) -> pd.DataFrame:
    """Strip leading/trailing whitespace from column names."""
    df.columns = [str(c).strip() for c in df.columns]
    return df


def _sanitize_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """
    Sanitize column names:
    - Replace whitespace/special chars with underscores
    - Lower-case
    - Remove leading digits
    """
    new_cols = []
    for col in df.columns:
        sanitized = re.sub(r"[^\w]", "_", str(col))
        sanitized = re.sub(r"_+", "_", sanitized).strip("_").lower()
        if sanitized and sanitized[0].isdigit():
            sanitized = "col_" + sanitized
        if not sanitized:
            sanitized = "unnamed"
        new_cols.append(sanitized)
    # Resolve any new duplicates after sanitizing
    seen: dict[str, int] = {}
    final: list[str] = []
    for name in new_cols:
        if name in seen:
            seen[name] += 1
            final.append(f"{name}_{seen[name]}")
        else:
            seen[name] = 0
            final.append(name)
    df.columns = final
    return df


def _drop_fully_empty(df: pd.DataFrame, warnings: list[str]) -> pd.DataFrame:
    """Drop columns and rows that are 100% empty."""
    before_cols = len(df.columns)
    df = df.dropna(axis=1, how="all")
    dropped_cols = before_cols - len(df.columns)
    if dropped_cols:
        warnings.append(f"Dropped {dropped_cols} fully-empty column(s).")

    before_rows = len(df)
    df = df.dropna(axis=0, how="all")
    dropped_rows = before_rows - len(df)
    if dropped_rows:
        warnings.append(f"Dropped {dropped_rows} fully-empty row(s).")

    df = df.reset_index(drop=True)
    return df


def _pick_engine(file_suffix: str) -> str | None:
    """Return the appropriate openpyxl/xlrd engine for the file suffix."""
    return "openpyxl" if file_suffix in {".xlsx", ".xlsm"} else None
