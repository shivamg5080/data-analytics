"""
Tests for agent/ingestion.py
"""
import io
import sys
import os
import pytest
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _make_xlsx_bytes(df: pd.DataFrame) -> io.BytesIO:
    buf = io.BytesIO()
    df.to_excel(buf, index=False, engine="openpyxl")
    buf.seek(0)
    return buf


class TestLoadExcel:
    def test_basic_load(self):
        from agent.ingestion import load_excel
        df_in = pd.DataFrame({"A": [1, 2, 3], "B": ["x", "y", "z"]})
        buf = _make_xlsx_bytes(df_in)
        result = load_excel(buf, filename="test.xlsx")
        assert "dataframe" in result
        assert len(result["dataframe"]) == 3
        assert list(result["dataframe"].columns) == ["a", "b"]

    def test_sheet_name_returned(self):
        from agent.ingestion import load_excel
        df_in = pd.DataFrame({"col1": range(5)})
        buf = _make_xlsx_bytes(df_in)
        result = load_excel(buf, filename="test.xlsx")
        assert "sheet_name" in result

    def test_empty_file_raises(self):
        from agent.ingestion import load_excel
        buf = io.BytesIO(b"not an xlsx file")
        with pytest.raises(Exception):
            load_excel(buf, filename="bad.xlsx")

    def test_duplicate_columns_handled(self):
        from agent.ingestion import load_excel
        # Create xlsx with duplicate headers manually
        df_in = pd.DataFrame([[1, 2, 3]], columns=["A", "B", "A"])
        buf = io.BytesIO()
        # openpyxl allows duplicate col names as raw write
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["A", "B", "A"])
        ws.append([1, 2, 3])
        wb.save(buf)
        buf.seek(0)
        result = load_excel(buf, filename="dup_cols.xlsx")
        # Should not crash; columns should be unique
        assert result["dataframe"] is not None
        cols = list(result["dataframe"].columns)
        assert len(set(cols)) == len(cols), "Duplicate columns should have been renamed"

    def test_multi_row_header_detection(self):
        """File with a title row before actual headers."""
        from agent.ingestion import load_excel
        import openpyxl
        buf = io.BytesIO()
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["My Report Title"])
        ws.append([])
        ws.append(["ID", "Name", "Value"])
        for i in range(5):
            ws.append([i, f"item_{i}", i * 10.5])
        wb.save(buf)
        buf.seek(0)
        result = load_excel(buf, filename="title_row.xlsx")
        df = result["dataframe"]
        assert len(df) >= 5
