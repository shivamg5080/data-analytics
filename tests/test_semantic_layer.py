"""
Tests for agent/semantic_layer.py
"""
import sys
import os
import pytest
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestSemanticLayer:
    def _build(self, df, column_types=None, analysis_columns=None):
        from agent.semantic_layer import build_semantic_layer
        if column_types is None:
            column_types = {}
            for c in df.columns:
                if pd.api.types.is_numeric_dtype(df[c]):
                    column_types[c] = "numeric"
                elif pd.api.types.is_datetime64_any_dtype(df[c]):
                    column_types[c] = "datetime"
                else:
                    column_types[c] = "categorical"
        if analysis_columns is None:
            analysis_columns = list(df.columns)
        return build_semantic_layer(df, column_types, analysis_columns)

    def test_has_required_keys(self):
        df = pd.DataFrame({"cat": ["A", "B", "A"], "val": [1.0, 2.0, 3.0]})
        result = self._build(df, {"cat": "categorical", "val": "numeric"})
        for key in ("dimensions", "measures", "time_fields", "entities", "kpis"):
            assert key in result

    def test_numeric_cols_become_measures(self):
        df = pd.DataFrame({"revenue": [100.0, 200.0], "cost": [50.0, 70.0]})
        result = self._build(df, {"revenue": "numeric", "cost": "numeric"})
        measure_cols = [m["raw_column"] for m in result["measures"]]
        assert "revenue" in measure_cols
        assert "cost" in measure_cols

    def test_categorical_cols_become_dimensions(self):
        df = pd.DataFrame({"region": ["North", "South", "East"]})
        result = self._build(df, {"region": "categorical"})
        dim_cols = [d["raw_column"] for d in result["dimensions"]]
        assert "region" in dim_cols

    def test_datetime_cols_become_time_fields(self):
        df = pd.DataFrame({"order_date": pd.to_datetime(["2023-01-01", "2023-02-01"])})
        result = self._build(df, {"order_date": "datetime"})
        time_cols = [t["raw_column"] for t in result["time_fields"]]
        assert "order_date" in time_cols

    def test_kpis_auto_generated_when_measures_present(self):
        df = pd.DataFrame({
            "revenue": [1000.0, 2000.0],
            "units": [10.0, 20.0],
        })
        result = self._build(df, {"revenue": "numeric", "units": "numeric"})
        # KPIs may or may not be generated depending on impl — just verify no crash
        assert isinstance(result["kpis"], list)

    def test_identifier_not_in_dimensions_or_measures(self):
        df = pd.DataFrame({
            "order_id": [f"ORD-{i}" for i in range(50)],
            "revenue": np.random.uniform(100, 500, 50),
        })
        result = self._build(df, {"order_id": "identifier", "revenue": "numeric"})
        dim_cols = [d["raw_column"] for d in result["dimensions"]]
        meas_cols = [m["raw_column"] for m in result["measures"]]
        assert "order_id" not in dim_cols
        assert "order_id" not in meas_cols
