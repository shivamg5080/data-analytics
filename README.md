# 📊 Automated Excel Data Analysis Agent

An end-to-end intelligent agent that automatically ingests Excel files, infers schemas, performs data quality checks, builds a semantic model, runs statistical analysis, generates smart visualizations, and produces a stakeholder-friendly HTML report — all with minimal manual intervention.

---

## 🚀 Quick Start

```bash
# 1. Clone / open the project
cd "data analysis agent"

# 2. Install dependencies
pip install -r requirements.txt

# 3. Generate sample data (optional)
python sample_data/generate_sample.py

# 4. Launch the Streamlit app
streamlit run app.py
```

Then open [http://localhost:8501](http://localhost:8501) in your browser, upload any `.xlsx` / `.xls` file, and click **Run Analysis**.

---

## 📁 Project Structure

```
data analysis agent/
├── agent/
│   ├── __init__.py
│   ├── ingestion.py          # Excel loading, sheet detection, header inference
│   ├── schema_inference.py   # Column type detection, data dictionary
│   ├── quality_checks.py     # Data quality, outlier/anomaly detection
│   ├── semantic_layer.py     # Dimensions, measures, KPIs, YAML export
│   ├── analysis_engine.py    # Stats, correlations, time-series, insights
│   ├── visualization.py      # Smart Plotly chart generation
│   ├── report_generator.py   # Self-contained HTML report
│   └── orchestrator.py       # Pipeline orchestration
├── tests/
│   ├── test_ingestion.py
│   ├── test_schema_inference.py
│   ├── test_quality_checks.py
│   └── test_semantic_layer.py
├── sample_data/
│   └── generate_sample.py    # Generates sample_sales.xlsx (1,000 rows)
├── app.py                    # Streamlit UI
├── config.yaml               # Configurable thresholds
├── requirements.txt
└── README.md
```

---

## 🧩 Pipeline Steps

| # | Module | What it does |
|---|--------|-------------|
| 1 | `ingestion.py` | Loads `.xlsx`/`.xls`, detects best sheet, handles merged cells & title rows |
| 2 | `schema_inference.py` | Infers column types (numeric, categorical, datetime, boolean, identifier, text) |
| 3 | `quality_checks.py` | Checks nulls, duplicates, outliers (IQR), mixed types |
| 4 | `semantic_layer.py` | Classifies dimensions/measures/KPIs, exports YAML |
| 5 | `analysis_engine.py` | Summaries, correlations, time-series trends, segment analysis, insights |
| 6 | `visualization.py` | Auto-selects and generates Plotly charts |
| 7 | `report_generator.py` | Builds self-contained HTML report with all charts embedded |

---

## ⚙️ Configuration

Edit `config.yaml` to tune the pipeline:

```yaml
schema:
  cardinality_threshold: 50        # max unique values for categorical
  identifier_min_uniqueness: 0.9   # uniqueness ratio to treat as ID

quality:
  outlier_method: iqr
  outlier_iqr_factor: 1.5

analysis:
  top_n_categories: 15
  correlation_min_columns: 2
  time_series_min_points: 10

visualization:
  max_charts: 30
  max_scatter_points: 5000

reporting:
  max_insights: 20
```

---

## 🧪 Running Tests

```bash
cd "data analysis agent"
python -m pytest tests/ -v --tb=short
```

---

## 📋 Streamlit UI Tabs

| Tab | Contents |
|-----|----------|
| 📋 Data Quality | Per-column null %, outlier count, duplicate rows, quality score |
| 🗂️ Schema | Data dictionary with inferred types, samples, notes |
| 🧠 Semantic Layer | Dimensions, measures, time fields, KPIs, YAML export |
| 📈 Analysis & Insights | Prioritized business insights with confidence scores |
| 📊 Charts | All interactive Plotly charts |
| 📄 Download Report | Self-contained HTML report download + preview |

---

## 📦 Requirements

| Package | Purpose |
|---------|---------|
| `pandas` | Data manipulation |
| `numpy` | Numerical operations |
| `openpyxl` / `xlrd` | Excel file reading |
| `scipy` | Statistical calculations |
| `plotly` | Interactive visualizations |
| `streamlit` | Web UI |
| `PyYAML` | Config and semantic layer export |
| `jinja2` | HTML templating |
| `python-dateutil` | Robust date parsing |

---

## 📄 License

MIT License — free to use, modify, and distribute.
