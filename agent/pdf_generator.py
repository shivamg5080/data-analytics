"""
PDF Generator Module
====================
Simplified version for debugging "Not enough space" error.
"""

from __future__ import annotations
from typing import Any
from fpdf import FPDF

def _clean(text: Any) -> str:
    return str(text).encode("ascii", "ignore").decode("ascii")

class PDFReport(FPDF):
    def __init__(self, filename: str):
        super().__init__()
        self.filename = filename
        self.set_auto_page_break(True, margin=15)
        self.add_page()
        self.set_font("helvetica", "B", 16)
        
    def add_section(self, title: str, content: str):
        self.set_font("helvetica", "B", 14)
        self.cell(0, 10, _clean(title), ln=1)
        self.set_font("helvetica", "", 12)
        self.multi_cell(0, 10, _clean(content))
        self.ln(5)

def generate_pdf_report(pipeline_result: dict[str, Any]) -> bytes:
    meta = pipeline_result.get("metadata", {})
    filename = meta.get("filename", "report")
    
    pdf = PDFReport(filename)
    pdf.add_section("Overview", "This is a basic PDF report.")
    
    analysis = pipeline_result.get("analysis", {})
    ds = analysis.get("dataset_summary", {})
    pdf.add_section("Stats", f"Rows: {ds.get('rows', 0)}")
    
    return bytes(pdf.output())
