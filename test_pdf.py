
import os
import sys
import yaml
import pandas as pd
import plotly.express as px
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent.pdf_generator import generate_pdf_report

def test_pdf_generation():
    print("Testing PDF generation...")
    
    # Mock data
    df = pd.DataFrame({
        "A": [1, 2, 3, 4, 5],
        "B": ["X", "Y", "X", "Z", "Y"],
        "C": [10.5, 20.1, 15.2, 30.5, 25.0]
    })
    
    fig = px.scatter(df, x="A", y="C", title="Test Chart")
    
    mock_result = {
        "metadata": {
            "filename": "test_data.xlsx",
            "sheet": "Sheet1",
            "rows_raw": 5,
            "pipeline_run_at": datetime.now().isoformat(),
        },
        "analysis": {
            "dataset_summary": {
                "rows": 5,
                "columns": 3,
                "complete_row_pct": 100.0,
                "analysis_columns": 3,
                "memory_mb": 0.1,
                "duplicate_rows": 0
            },
            "insights": [
                {"category": "test", "title": "Test Insight", "detail": "This is a test insight for PDF.", "priority": 2, "confidence": 0.95}
            ]
        },
        "quality": {
            "overall_score": 0.95,
            "issues": ["Test issue 1", "Test issue 2"]
        },
        "schema": {
            "data_dictionary": [
                {"column": "A", "inferred_type": "numeric", "null_pct": 0.0, "notes": "Test notes"}
            ]
        },
        "semantic": {
            "dimensions": [{"raw_column": "B"}],
            "measures": [{"raw_column": "C"}],
            "time_fields": [],
            "kpis": [{"name": "Total C"}],
            "entities": []
        },
        "charts": [
            {"fig": fig, "title": "Test Chart", "insight": "Test chart insight", "stakeholder_note": "Test note"}
        ]
    }
    
    try:
        pdf_bytes = generate_pdf_report(mock_result)
        output_path = "test_report.pdf"
        with open(output_path, "wb") as f:
            f.write(pdf_bytes)
        
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            print(f"✅ PDF generated successfully: {output_path} ({os.path.getsize(output_path)} bytes)")
        else:
            print("❌ PDF generation failed: empty or missing file")
    except Exception as e:
        import traceback
        print(f"❌ PDF generation failed with error: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    test_pdf_generation()
