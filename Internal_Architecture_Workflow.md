# Data Analysis Agent - Internal Workflow & Architecture

This document breaks down the internal technical architecture of the Data Analysis Agent, detailing how data flows through the system from raw upload to finished analysis report.

## 1. High-Level Architecture Flowchart

```mermaid
flowchart TD
    A[User Uploads File] -->|CSV / Excel| B[app.py / Streamlit FileUploader]
    
    subgraph pipeline [Orchestrator Pipeline]
        direction TB
        C[agent/ingestion.py] --> D[agent/schema_inference.py]
        D --> E[agent/quality_checks.py]
        E --> F[agent/semantic_layer.py]
        F --> G[agent/analysis_engine.py]
        G --> H[agent/visualization.py]
        H --> I[agent/report_generator.py]
    end

    B -->|Calls run_pipeline()| pipeline
    
    pipeline -->|Output Dictionary| J[Results Dictionary]
    
    J -->|Rendered in UI| K[Streamlit UI Tabs]
    J -->|HTML Report rendered via Jinja2| L[analysis_report.html]
```

## 2. Step-by-Step Module Workflow

The `agent/orchestrator.py` serves as the nerve center. When `run_pipeline()` is invoked, it passes the dataset sequentially through the following modules in exact order:

### Phase 1: Data Preparation
1. **`ingestion.py` (Load Excel/CSV):**
   * **Purpose:** Safely load the raw file bytes into a Pandas DataFrame.
   * **Internals:** For Excel files, it scans the workbook to find the largest/most relevant sheet (`_pick_best_sheet`). It also runs `_detect_header_row` to skip over empty or title rows at the top of a spreadsheet so that the true table headers are used.
2. **`schema_inference.py` (Infer Schema):**
   * **Purpose:** Identify the internal data type (not just Python `dtypes`, but Business Logic types).
   * **Internals:** Analyzes up to 200 sample rows for each column. Checks thresholds to classify the column as `numeric`, `categorical`, `datetime`, `boolean`, `identifier` (e.g., UUIDs or Primary Keys), or `text`. It flags completely empty strings or single-value columns to be ignored in the subsequent analysis steps.

### Phase 2: Assessment & Semantic Mapping
3. **`quality_checks.py` (Data Quality):**
   * **Purpose:** Assess dataset health without crashing. 
   * **Internals:** Looks at null percentages, duplicate rows, whitespace issues, mixed types within columns, skewed data, and statistical outliers via IQR and Z-scores. Returns a 0-100 `quality_score`.
4. **`semantic_layer.py` (Semantic Layer Construction):**
   * **Purpose:** Acts like a mini-dbt layer. It bridges the gap between raw tables and business logic.
   * **Internals:** Classifies the schema-inferred columns into `dimensions` (categorical data) and `measures` (numeric data). It intelligently assigns standard aggregations (like SUM for "revenue", AVG for "ratings", COUNT for "IDs") and automatically generates formulaic KPIs (Key Performance Indicators) if it finds both Revenue and Quantity columns.

### Phase 3: Analytics & Reporting
5. **`analysis_engine.py` (Statistical Auto-Analysis):**
   * **Purpose:** Produce math-driven text insights without needing an LLM.
   * **Internals:** Runs categorical frequency checks, computes numeric descriptive statistics (mean, median, standard deviations), performs Pearson correlation checks between standard measures, and identifies time-time trends if a `datetime` dimension exists. These results are scored and prioritized into high/medium/low severity "Insights".
6. **`visualization.py` (Smart Charting):**
   * **Purpose:** Automatically generate the ideal chart for the data combinations.
   * **Internals:** Generates Plotly JSON/HTML figures. E.g., If a time-series dimension exists alongside a numeric measure, it generates a Line Chart. If it finds two highly correlated numeric measures, it generates a Scatter Plot. If it sees a categorical dimension and a sum measure, it builds a Bar Chart.
7. **`report_generator.py` (Final Compilation):**
   * **Purpose:** Compile everything into a portable format.
   * **Internals:** Uses `Jinja2` to take an HTML template and embed all the tables, summaries, insights, and Plotly JS scripts directly into one static, standalone `.html` file. 

## 3. Configuration & Overrides
The entire pipeline is dynamically configurable. The orchestrator references a central `config.yaml` document (if available in the root dict).
* Through the config, users can adjust threshold thresholds (e.g., adjust the IQR multiplier from `1.5` to `2.0`, change the logic for string extraction, or enforce synonym mapping for specific business terms). This ensures the tool can scale across entirely different departments with entirely different jargons.
