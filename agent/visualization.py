"""
Visualization Engine Module
============================
Selects and generates the most appropriate Plotly charts based on
column types and data characteristics. Every chart comes with a
plain-English insight and stakeholder relevance note.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

logger = logging.getLogger(__name__)

# Chart colours
PALETTE = px.colors.qualitative.Set2
ACCENT = "#4F81BD"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_visualizations(
    df: pd.DataFrame,
    column_types: dict[str, str],
    analysis_result: dict[str, Any],
    semantic_layer: dict[str, Any],
    analysis_columns: list[str],
    config: dict | None = None,
) -> list[dict[str, Any]]:
    """
    Generate a curated list of Plotly charts.

    Returns
    -------
    list[dict] each with keys:
        - ``fig``              : plotly Figure
        - ``html``             : str — standalone HTML of the chart
        - ``title``            : str
        - ``insight``          : str
        - ``stakeholder_note`` : str
        - ``chart_type``       : str
    """
    cfg = (config or {}).get("visualization", {})
    max_charts: int = cfg.get("max_charts", 30)
    max_scatter: int = cfg.get("max_scatter_points", 5000)

    charts: list[dict] = []

    measure_cols = [m["raw_column"] for m in semantic_layer.get("measures", []) if m["raw_column"] in df.columns]
    dimension_cols = [d["raw_column"] for d in semantic_layer.get("dimensions", []) if d["raw_column"] in df.columns]
    time_cols = [t["raw_column"] for t in semantic_layer.get("time_fields", []) if t["raw_column"] in df.columns]

    # 1. Missing value overview
    _add_chart(charts, _missing_value_chart(df, analysis_columns))

    # 2. Histograms for numeric columns
    for col in measure_cols[:6]:
        _add_chart(charts, _histogram_chart(df, col))

    # 3. Box plots for numeric columns (outliers)
    for col in measure_cols[:6]:
        _add_chart(charts, _box_plot_chart(df, col))

    # 4. Bar charts for categorical columns (top N)
    for col in dimension_cols[:6]:
        _add_chart(charts, _bar_chart_categorical(df, col))

    # 5. Time-series line charts
    ts_results = analysis_result.get("time_series") or []
    for ts in ts_results:
        for trend in ts.get("trends", [])[:3]:
            _add_chart(charts, _time_series_chart(trend, ts["time_column"]))

    # 6. Correlation heatmap
    corr = analysis_result.get("correlations")
    if corr and len(measure_cols) >= 2:
        _add_chart(charts, _correlation_heatmap(corr, measure_cols))

    # 7. Scatter plots (top 2 pairs with highest correlation)
    if corr and corr.get("strong_correlations"):
        for sc in corr["strong_correlations"][:2]:
            _add_chart(charts, _scatter_plot(df, sc["col1"], sc["col2"], dimension_cols, max_scatter))

    # 8. Segment bar charts (measure by dimension)
    for seg in (analysis_result.get("segment_analyses") or [])[:4]:
        _add_chart(charts, _segment_bar_chart(seg))

    # 9. Overall KPI summary card
    kpi_chart = _kpi_summary_card(df, measure_cols, semantic_layer.get("kpis", []))
    _add_chart(charts, kpi_chart)

    # Cap at max_charts
    charts = [c for c in charts if c is not None][:max_charts]
    logger.info("Generated %d chart(s)", len(charts))
    return charts


# ---------------------------------------------------------------------------
# Chart generators
# ---------------------------------------------------------------------------

def _missing_value_chart(df: pd.DataFrame, columns: list[str]) -> dict | None:
    """Horizontal bar chart showing null % per column."""
    try:
        null_pcts = (df[columns].isna().mean() * 100).sort_values(ascending=False)
        null_pcts = null_pcts[null_pcts > 0]
        if null_pcts.empty:
            return None

        fig = px.bar(
            x=null_pcts.values,
            y=null_pcts.index,
            orientation="h",
            color=null_pcts.values,
            color_continuous_scale="Reds",
            title="Missing Value Analysis — Null % by Column",
            labels={"x": "Null Percentage (%)", "y": "Column"},
        )
        fig.update_layout(**_base_layout())
        return _wrap_chart(
            fig,
            title="Missing Value Analysis",
            chart_type="bar_horizontal",
            insight=f"{len(null_pcts)} of {len(columns)} columns have missing values. "
                    f"Worst: '{null_pcts.index[0]}' at {null_pcts.iloc[0]:.1f}%.",
            stakeholder_note="High missing data rates may indicate data collection gaps or system issues that need addressing.",
        )
    except Exception as e:
        logger.warning("Missing value chart failed: %s", e)
        return None


def _histogram_chart(df: pd.DataFrame, col: str) -> dict | None:
    """Distribution histogram for a numeric column."""
    try:
        series = pd.to_numeric(df[col], errors="coerce").dropna()
        if len(series) < 5:
            return None

        fig = px.histogram(
            series,
            nbins=min(50, int(len(series) ** 0.5) + 10),
            title=f"Distribution — {col.replace('_', ' ').title()}",
            labels={"value": col},
            color_discrete_sequence=[ACCENT],
        )
        fig.update_layout(**_base_layout())
        skew = float(series.skew())
        skew_note = f" The distribution is {'right' if skew > 0 else 'left'}-skewed (skew={skew:.2f})." if abs(skew) > 0.5 else ""
        return _wrap_chart(
            fig,
            title=f"Distribution of {col}",
            chart_type="histogram",
            insight=f"Mean={series.mean():.2f}, Median={series.median():.2f}, Std={series.std():.2f}.{skew_note}",
            stakeholder_note=f"Understanding the spread of '{col}' helps identify normal vs. abnormal values and plan targets.",
        )
    except Exception as e:
        logger.warning("Histogram failed for '%s': %s", col, e)
        return None


def _box_plot_chart(df: pd.DataFrame, col: str) -> dict | None:
    """Box plot to visualise outliers."""
    try:
        series = pd.to_numeric(df[col], errors="coerce").dropna()
        if len(series) < 10:
            return None

        q1, q3 = series.quantile(0.25), series.quantile(0.75)
        iqr = q3 - q1
        outliers = ((series < q1 - 1.5 * iqr) | (series > q3 + 1.5 * iqr)).sum()

        fig = go.Figure(go.Box(y=series, name=col, marker_color=ACCENT, boxmean=True))
        fig.update_layout(title=f"Outlier Analysis — {col.replace('_', ' ').title()}", **_base_layout())
        return _wrap_chart(
            fig,
            title=f"Box Plot: {col}",
            chart_type="box",
            insight=f"{outliers} outlier(s) detected. IQR range: [{q1:.2f}, {q3:.2f}]. "
                    f"Median = {series.median():.2f}.",
            stakeholder_note=f"Outliers in '{col}' may indicate data entry errors, exceptional cases, or genuine extremes.",
        )
    except Exception as e:
        logger.warning("Box plot failed for '%s': %s", col, e)
        return None


def _bar_chart_categorical(df: pd.DataFrame, col: str, top_n: int = 15) -> dict | None:
    """Top-N bar chart for a categorical column."""
    try:
        vc = df[col].dropna().astype(str).value_counts().head(top_n)
        if vc.empty:
            return None

        fig = px.bar(
            x=vc.index,
            y=vc.values,
            title=f"Category Distribution — {col.replace('_', ' ').title()} (Top {min(top_n, len(vc))})",
            labels={"x": col, "y": "Count"},
            color=vc.values,
            color_continuous_scale="Blues",
        )
        fig.update_layout(**_base_layout())
        top_val = vc.index[0]
        top_pct = vc.iloc[0] / vc.sum() * 100
        return _wrap_chart(
            fig,
            title=f"Distribution of {col}",
            chart_type="bar",
            insight=f"Top value: '{top_val}' ({top_pct:.1f}% of records). {vc.nunique()} unique categories shown.",
            stakeholder_note=f"The distribution of '{col}' reveals which categories dominate and where to focus attention.",
        )
    except Exception as e:
        logger.warning("Bar chart failed for '%s': %s", col, e)
        return None


def _time_series_chart(trend: dict, time_col: str) -> dict | None:
    """Line chart for a time-series trend."""
    try:
        data = trend.get("monthly_data", [])
        if not data:
            return None
        ts_df = pd.DataFrame(data)
        measure = trend["measure"]
        fig = px.line(
            ts_df,
            x="period",
            y="value",
            title=f"Time Trend — {measure.replace('_', ' ').title()} over {time_col.replace('_', ' ').title()}",
            markers=True,
            color_discrete_sequence=[ACCENT],
        )
        fig.update_layout(**_base_layout())
        direction = trend.get("trend_direction", "stable")
        r2 = trend.get("r_squared", 0)
        return _wrap_chart(
            fig,
            title=f"Time Trend: {measure}",
            chart_type="line",
            insight=f"'{measure}' shows a {direction} trend (R²={r2:.2f}). "
                    f"{'Strong' if r2 > 0.7 else 'Moderate' if r2 > 0.4 else 'Weak'} fit.",
            stakeholder_note=f"Tracking '{measure}' over time reveals growth patterns and seasonal effects.",
        )
    except Exception as e:
        logger.warning("Time-series chart failed: %s", e)
        return None


def _correlation_heatmap(corr: dict, numeric_cols: list[str]) -> dict | None:
    """Correlation matrix heatmap."""
    try:
        matrix = pd.DataFrame(corr["matrix"])
        cols = [c for c in numeric_cols if c in matrix.columns]
        if len(cols) < 2:
            return None
        sub = matrix.loc[cols, cols]
        fig = px.imshow(
            sub,
            text_auto=".2f",
            color_continuous_scale="RdBu_r",
            zmin=-1,
            zmax=1,
            title="Correlation Heatmap — Numeric Measures",
        )
        fig.update_layout(**_base_layout())
        strong = corr.get("strong_correlations", [])
        insight = (
            f"{len(strong)} strong correlation(s) found: "
            + ", ".join(f"{s['col1']} ↔ {s['col2']} ({s['correlation']})" for s in strong[:3])
            if strong else "No strong correlations found between numeric columns."
        )
        return _wrap_chart(
            fig,
            title="Correlation Heatmap",
            chart_type="heatmap",
            insight=insight,
            stakeholder_note="Highly correlated measures may be redundant or causally linked — useful for forecasting models.",
        )
    except Exception as e:
        logger.warning("Correlation heatmap failed: %s", e)
        return None


def _scatter_plot(
    df: pd.DataFrame,
    col1: str,
    col2: str,
    color_dims: list[str],
    max_points: int,
) -> dict | None:
    """Scatter plot for two correlated numeric columns."""
    try:
        sub = df[[col1, col2] + (color_dims[:1] if color_dims else [])].copy()
        sub[col1] = pd.to_numeric(sub[col1], errors="coerce")
        sub[col2] = pd.to_numeric(sub[col2], errors="coerce")
        sub = sub.dropna(subset=[col1, col2])
        if len(sub) > max_points:
            sub = sub.sample(max_points, random_state=42)
        color_col = color_dims[0] if color_dims and color_dims[0] in sub.columns else None
        fig = px.scatter(
            sub,
            x=col1,
            y=col2,
            color=color_col,
            trendline="ols",
            title=f"Relationship — {col1.replace('_', ' ').title()} vs {col2.replace('_', ' ').title()}",
            opacity=0.6,
        )
        fig.update_layout(**_base_layout())
        return _wrap_chart(
            fig,
            title=f"Scatter: {col1} vs {col2}",
            chart_type="scatter",
            insight=f"Visual relationship between '{col1}' and '{col2}'. Trend line shows direction.",
            stakeholder_note=f"If these two measures are strongly linked, changes in one may predict changes in the other.",
        )
    except Exception as e:
        logger.warning("Scatter plot failed for '%s' vs '%s': %s", col1, col2, e)
        return None


def _segment_bar_chart(seg: dict) -> dict | None:
    """Grouped bar chart for a segment analysis result."""
    try:
        segs = seg.get("segments", [])
        if not segs:
            return None
        seg_df = pd.DataFrame(segs).head(15)
        fig = px.bar(
            seg_df,
            x="segment",
            y="total",
            title=f"'{seg['measure'].replace('_', ' ').title()}' by '{seg['dimension'].replace('_', ' ').title()}'",
            color="total",
            color_continuous_scale="Teal",
            text="total",
        )
        fig.update_traces(texttemplate="%{text:.2s}", textposition="outside")
        fig.update_layout(**_base_layout())
        top = segs[0]
        return _wrap_chart(
            fig,
            title=f"{seg['measure']} by {seg['dimension']}",
            chart_type="bar_segment",
            insight=f"Top segment: '{top.get('segment')}' with total {top.get('total', 0):,.0f} "
                    f"(avg {top.get('avg', 0):.2f} per record).",
            stakeholder_note=f"Comparing '{seg['measure']}' across '{seg['dimension']}' reveals where value is concentrated.",
        )
    except Exception as e:
        logger.warning("Segment bar chart failed: %s", e)
        return None


def _kpi_summary_card(
    df: pd.DataFrame, measure_cols: list[str], kpis: list[dict]
) -> dict | None:
    """KPI indicator card showing top-level measures."""
    try:
        figs = []
        for col in measure_cols[:6]:
            series = pd.to_numeric(df[col], errors="coerce").dropna()
            if len(series) == 0:
                continue
            figs.append(go.Indicator(
                mode="number+delta",
                value=float(series.sum()),
                title={"text": f"Total {col.replace('_', ' ').title()}"},
                number={"font": {"size": 28}},
            ))

        if not figs:
            return None

        rows = (len(figs) + 2) // 3
        fig = make_subplots(rows=rows, cols=3, specs=[[{"type": "indicator"}] * 3] * rows)
        for i, indicator in enumerate(figs):
            fig.add_trace(indicator, row=i // 3 + 1, col=i % 3 + 1)

        fig.update_layout(title_text="Key Metrics Overview", **_base_layout(height=250 * rows))
        return _wrap_chart(
            fig,
            title="KPI Overview",
            chart_type="kpi_card",
            insight=f"Top-level aggregate metrics for {len(figs)} measure(s).",
            stakeholder_note="Quick snapshot of the most important numbers in this dataset.",
        )
    except Exception as e:
        logger.warning("KPI card failed: %s", e)
        return None


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _base_layout(height: int = 450) -> dict:
    return {
        "plot_bgcolor": "#FAFAFA",
        "paper_bgcolor": "#FFFFFF",
        "font": {"family": "Inter, sans-serif", "size": 13},
        "height": height,
        "margin": {"l": 60, "r": 30, "t": 60, "b": 60},
    }


def _wrap_chart(fig, title: str, chart_type: str, insight: str, stakeholder_note: str) -> dict:
    """Convert a Plotly figure to a chart dict with metadata."""
    html = fig.to_html(full_html=False, include_plotlyjs=False)
    return {
        "fig": fig,
        "html": html,
        "title": title,
        "chart_type": chart_type,
        "insight": insight,
        "stakeholder_note": stakeholder_note,
    }


def _add_chart(charts: list, chart: dict | None) -> None:
    if chart is not None:
        charts.append(chart)
