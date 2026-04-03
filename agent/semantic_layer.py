"""
Semantic Layer Module
=====================
Builds a dbt-inspired semantic layer on top of raw column data.
Classifies columns into dimensions, measures, time fields, entities,
and auto-generates KPIs. Exports a YAML metadata file for reproducibility.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

logger = logging.getLogger(__name__)

# Semantic types
SEM_DIMENSION = "dimension"
SEM_MEASURE = "measure"
SEM_TIME = "time"
SEM_ENTITY = "entity"
SEM_KPI = "kpi"

# Aggregation choices per numeric context
AGG_SUM_KEYWORDS = ["amount", "revenue", "sales", "profit", "cost", "price",
                    "quantity", "qty", "total", "sum", "income", "expense"]
AGG_AVG_KEYWORDS = ["rate", "ratio", "average", "avg", "score", "percent",
                    "pct", "satisfaction", "rating", "age"]
AGG_COUNT_KEYWORDS = ["count", "cnt", "num", "number", "id"]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_semantic_layer(
    df: pd.DataFrame,
    column_types: dict[str, str],
    analysis_columns: list[str],
    config: dict | None = None,
    output_path: str | None = None,
) -> dict[str, Any]:
    """
    Build and return the semantic layer.

    Returns
    -------
    dict with keys:
        - ``dimensions``  : list[dict]
        - ``measures``    : list[dict]
        - ``time_fields`` : list[dict]
        - ``entities``    : list[dict]
        - ``kpis``        : list[dict]
        - ``yaml``        : str — YAML representation
        - ``lineage``     : dict — raw col → semantic field mapping
        - ``summary``     : str — human-readable summary
    """
    cfg = (config or {}).get("semantic_layer", {})
    auto_kpi: bool = cfg.get("auto_kpi_generation", True)
    standardize: bool = cfg.get("standardize_names", True)
    synonym_map: dict = cfg.get("synonym_mapping", {})

    # Build synonym lookup: raw_keyword → canonical_name
    synonym_lookup = _build_synonym_lookup(synonym_map)

    dimensions: list[dict] = []
    measures: list[dict] = []
    time_fields: list[dict] = []
    entities: list[dict] = []
    lineage: dict[str, str] = {}

    for col in analysis_columns:
        col_type = column_types.get(col, "unknown")
        canonical = _canonical_name(col, synonym_lookup, standardize)
        lineage[col] = canonical

        entry_base = {
            "raw_column": col,
            "semantic_name": canonical,
            "description": _infer_description(col, col_type),
            "nullable": bool(df[col].isna().any()),
        }

        if col_type == "datetime":
            time_fields.append({
                **entry_base,
                "semantic_type": SEM_TIME,
                "granularities": ["day", "month", "quarter", "year"],
            })
        elif col_type == "identifier":
            entities.append({
                **entry_base,
                "semantic_type": SEM_ENTITY,
            })
        elif col_type == "numeric":
            agg = _infer_aggregation(col)
            measures.append({
                **entry_base,
                "semantic_type": SEM_MEASURE,
                "aggregation": agg,
                "format": _infer_format(col),
            })
        elif col_type in ("categorical", "boolean"):
            dimensions.append({
                **entry_base,
                "semantic_type": SEM_DIMENSION,
                "values": _get_dimension_values(df, col),
            })
        else:
            # text → treat as dimension
            dimensions.append({
                **entry_base,
                "semantic_type": SEM_DIMENSION,
            })

    # ---- Auto-generate KPIs ------------------------------------------------
    kpis: list[dict] = []
    if auto_kpi:
        kpis = _generate_kpis(measures, time_fields, dimensions, df, column_types)

    # ---- YAML export -------------------------------------------------------
    layer_dict = {
        "semantic_layer": {
            "version": "1.0",
            "dimensions": dimensions,
            "measures": measures,
            "time_fields": time_fields,
            "entities": entities,
            "kpis": kpis,
        }
    }
    yaml_str = yaml.dump(layer_dict, default_flow_style=False, allow_unicode=True, sort_keys=False)

    if output_path:
        Path(output_path).write_text(yaml_str, encoding="utf-8")
        logger.info("Semantic layer saved to: %s", output_path)

    summary = _build_summary(dimensions, measures, time_fields, entities, kpis)
    logger.info(
        "Semantic layer built: %d dimensions, %d measures, %d time, %d entities, %d KPIs",
        len(dimensions), len(measures), len(time_fields), len(entities), len(kpis)
    )

    return {
        "dimensions": dimensions,
        "measures": measures,
        "time_fields": time_fields,
        "entities": entities,
        "kpis": kpis,
        "yaml": yaml_str,
        "lineage": lineage,
        "summary": summary,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_synonym_lookup(synonym_map: dict) -> dict[str, str]:
    """Build keyword → canonical mapping from config synonym_mapping."""
    lookup: dict[str, str] = {}
    for canonical, synonyms in synonym_map.items():
        for syn in synonyms:
            lookup[syn.lower()] = canonical
    return lookup


def _canonical_name(col: str, synonym_lookup: dict[str, str], standardize: bool) -> str:
    """Convert raw column name to canonical semantic name."""
    name = col.lower().strip()
    # Check full match first
    if name in synonym_lookup:
        return synonym_lookup[name]
    # Check partial keyword match
    for kw, canonical in synonym_lookup.items():
        if kw in name:
            return re.sub(kw, canonical, name)
    if standardize:
        return re.sub(r"[^\w]", "_", name).strip("_")
    return name


def _infer_description(col: str, col_type: str) -> str:
    """Generate a human-readable description for a column."""
    readable = col.replace("_", " ").title()
    type_descriptions = {
        "numeric": f"Numeric measure: {readable}",
        "categorical": f"Categorical dimension: {readable}",
        "datetime": f"Time field: {readable}",
        "boolean": f"Boolean flag: {readable}",
        "identifier": f"Unique identifier: {readable}",
        "text": f"Free-text field: {readable}",
    }
    return type_descriptions.get(col_type, f"Field: {readable}")


def _infer_aggregation(col: str) -> str:
    """Infer the best aggregation for a measure column based on its name."""
    name = col.lower()
    if any(kw in name for kw in AGG_AVG_KEYWORDS):
        return "avg"
    if any(kw in name for kw in AGG_COUNT_KEYWORDS):
        return "count"
    return "sum"


def _infer_format(col: str) -> str:
    """Infer display format (currency, percentage, number)."""
    name = col.lower()
    if any(kw in name for kw in ["price", "revenue", "cost", "amount", "sales", "profit", "income"]):
        return "currency"
    if any(kw in name for kw in ["pct", "percent", "rate", "ratio"]):
        return "percentage"
    return "number"


def _get_dimension_values(df: pd.DataFrame, col: str) -> list[str]:
    """Return sorted unique values for a dimension (capped at 50)."""
    try:
        vals = df[col].dropna().unique()[:50]
        return sorted([str(v) for v in vals])
    except Exception:
        return []


    return False


def _generate_kpis(
    measures: list[dict],
    time_fields: list[dict],
    dimensions: list[dict],
    df: pd.DataFrame,
    column_types: dict[str, str],
) -> list[dict]:
    """Auto-generate business KPIs from available measures and dimensions."""
    kpis: list[dict] = []
    measure_names = [m["semantic_name"] for m in measures]
    raw_measure_cols = {m["semantic_name"]: m["raw_column"] for m in measures}

    # KPI 1: Total of each sum measure
    for m in measures:
        if m.get("aggregation") == "sum":
            kpis.append({
                "name": f"total_{m['semantic_name']}",
                "semantic_type": SEM_KPI,
                "formula": f"SUM({m['raw_column']})",
                "description": f"Total {m['raw_column'].replace('_', ' ')} across all records",
                "format": m.get("format", "number"),
                "source_measures": [m["semantic_name"]],
            })

    # KPI 2: Average of avg measures
    for m in measures:
        if m.get("aggregation") == "avg" and m.get("format") != "currency":
            kpis.append({
                "name": f"avg_{m['semantic_name']}",
                "semantic_type": SEM_KPI,
                "formula": f"AVG({m['raw_column']})",
                "description": f"Average {m['raw_column'].replace('_', ' ')}",
                "format": m.get("format", "number"),
                "source_measures": [m["semantic_name"]],
            })

    # KPI 3: Revenue per quantity (if both exist)
    revenue_col = next((m for m in measure_names if "revenue" in m or "sales" in m or "amount" in m), None)
    qty_col = next((m for m in measure_names if "quantity" in m or "qty" in m or "units" in m), None)
    if revenue_col and qty_col:
        kpis.append({
            "name": "revenue_per_unit",
            "semantic_type": SEM_KPI,
            "formula": f"SUM({raw_measure_cols.get(revenue_col,'revenue')}) / SUM({raw_measure_cols.get(qty_col,'quantity')})",
            "description": "Average revenue generated per unit sold",
            "format": "currency",
            "source_measures": [revenue_col, qty_col],
        })

    # KPI 4: Count of records per dimension (if dimensions exist)
    if dimensions:
        for dim in dimensions[:2]:  # limit to first 2
            kpis.append({
                "name": f"record_count_by_{dim['semantic_name']}",
                "semantic_type": SEM_KPI,
                "formula": f"COUNT(*) GROUP BY {dim['raw_column']}",
                "description": f"Number of records per {dim['raw_column'].replace('_', ' ')}",
                "format": "number",
                "source_measures": [],
            })

    return kpis


def _build_summary(
    dimensions: list[dict],
    measures: list[dict],
    time_fields: list[dict],
    entities: list[dict],
    kpis: list[dict],
) -> str:
    lines = [
        f"**Semantic Layer Summary**",
        f"- **{len(dimensions)} Dimension(s)**: {', '.join(d['semantic_name'] for d in dimensions[:8])}{'...' if len(dimensions) > 8 else ''}",
        f"- **{len(measures)} Measure(s)**: {', '.join(m['semantic_name'] for m in measures[:8])}{'...' if len(measures) > 8 else ''}",
        f"- **{len(time_fields)} Time Field(s)**: {', '.join(t['semantic_name'] for t in time_fields)}",
        f"- **{len(entities)} Entity/Identifier(s)**: {', '.join(e['semantic_name'] for e in entities[:5])}",
        f"- **{len(kpis)} Auto-Generated KPI(s)**",
    ]
    return "\n".join(lines)
