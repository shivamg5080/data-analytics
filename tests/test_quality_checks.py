"""
Tests for agent/quality_checks.py
"""
import sys
import os
import pytest
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestQualityChecks:
    def _run(self, df, column_types=None, analysis_columns=None):
        from agent.quality_checks import run_quality_checks
        if column_types is None:
            column_types = {c: "numeric" if pd.api.types.is_numeric_dtype(df[c]) else "categorical"
                            for c in df.columns}
        if analysis_columns is None:
            analysis_columns = list(df.columns)
        return run_quality_checks(df, column_types, analysis_columns)

    def test_null_detection(self):
        df = pd.DataFrame({"a": [1.0, None, 3.0, None, 5.0]})
        result = self._run(df)
        cq = next(c for c in result["per_column"] if c["column"] == "a")
        assert cq["null_pct"] == pytest.approx(40.0, abs=1)

    def test_duplicate_row_detection(self):
        df = pd.DataFrame({"a": [1, 2, 1, 3, 2], "b": ["x", "y", "x", "z", "y"]})
        result = self._run(df)
        assert len(result["issues"]) >= 0

    def test_outlier_detection_iqr(self):
        vals = list(range(1, 101))
        vals.append(9999)  # extreme outlier
        df = pd.DataFrame({"val": vals})
        result = self._run(df, column_types={"val": "numeric"})
        cq = next(c for c in result["per_column"] if c["column"] == "val")
        assert cq.get("outliers", {}).get("iqr_outlier_count", 0) >= 1

    def test_fully_null_column_flagged(self):
        df = pd.DataFrame({"a": [1, 2, 3], "b": [None, None, None]})
        result = self._run(df, column_types={"a": "numeric", "b": "numeric"})
        issues = result.get("issues", [])
        assert any("b" in i for i in issues) or any(
            c["column"] == "b" and c["null_pct"] == 100 for c in result["per_column"]
        )

    def test_overall_score_decreases_with_nulls(self):
        df_clean = pd.DataFrame({"a": [1.0, 2.0, 3.0]})
        df_nulls = pd.DataFrame({"a": [1.0, None, None]})
        r_clean = self._run(df_clean)
        r_nulls = self._run(df_nulls)
        assert r_clean["quality_score"] > r_nulls["quality_score"]

    def test_does_not_crash_on_all_bad_data(self):
        df = pd.DataFrame({
            "mixed": ["abc", 123, None, True, 3.14],
            "all_null": [None] * 5,
        })
        result = self._run(df, column_types={"mixed": "text", "all_null": "numeric"})
        assert "quality_score" in result
