"""
Tests for agent/schema_inference.py
"""
import sys
import os
import pytest
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestInferSchema:
    def _infer(self, df):
        from agent.schema_inference import infer_schema
        return infer_schema(df)

    def test_numeric_column_detected(self):
        df = pd.DataFrame({"revenue": [100.0, 200.5, 300.1]})
        result = self._infer(df)
        assert result["column_types"]["revenue"] == "numeric"

    def test_categorical_column_detected(self):
        df = pd.DataFrame({"region": ["North", "South"] * 10})
        result = self._infer(df)
        assert result["column_types"]["region"] == "categorical"

    def test_datetime_column_detected(self):
        df = pd.DataFrame({"date": ["2023-01-01", "2023-02-15", "2023-06-30"]})
        result = self._infer(df)
        assert result["column_types"]["date"] == "datetime"

    def test_boolean_column_detected(self):
        df = pd.DataFrame({"is_active": [True, False, True, False]})
        result = self._infer(df)
        assert result["column_types"]["is_active"] == "boolean"

    def test_fully_empty_column_excluded_from_analysis(self):
        df = pd.DataFrame({"a": [1, 2, 3], "empty": [None, None, None]})
        result = self._infer(df)
        assert "empty" not in result.get("analysis_columns", [])

    def test_data_dictionary_has_all_columns(self):
        df = pd.DataFrame({"x": [1, 2], "y": ["a", "b"]})
        result = self._infer(df)
        dd_cols = {entry["column_name"] for entry in result["data_dictionary"]}
        assert "x" in dd_cols and "y" in dd_cols

    def test_null_pct_in_data_dict(self):
        df = pd.DataFrame({"val": [1.0, None, 3.0, None]})
        result = self._infer(df)
        val_entry = next(e for e in result["data_dictionary"] if e["column_name"] == "val")
        assert val_entry["null_pct"] == pytest.approx(50.0, abs=1.0)

    def test_identifier_column_excluded(self):
        """High-uniqueness string column should be typed as identifier."""
        df = pd.DataFrame({
            "order_id": [f"ORD-{i}" for i in range(150)],
            "revenue": np.random.uniform(100, 1000, 150),
        })
        result = self._infer(df)
        assert result["column_types"].get("order_id") == "identifier"
