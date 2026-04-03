"""
Streamlit UI for the Automated Excel Data Analysis Agent
=========================================================
Provides a beautiful multi-tab interface for file upload,
analysis pipeline execution, and result exploration.
"""

import io
import logging
import os
import sys
import tempfile

import streamlit as st

# Ensure the project root is on the path
sys.path.insert(0, os.path.dirname(__file__))

# ---- Logging setup ----
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger("app")

# -----------------------------------------------------------------------
# Page config + custom CSS
# -----------------------------------------------------------------------
st.set_page_config(
    page_title="Data Analysis Agent",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
  /* Google Font */
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

  html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

  /* Hide Streamlit branding */
  #MainMenu, footer { visibility: hidden; }

  /* Header gradient */
  .hero {
    background: linear-gradient(135deg, #1e3a5f 0%, #2d6a9f 100%);
    border-radius: 14px;
    padding: 2.5rem 2rem;
    color: white;
    margin-bottom: 1.8rem;
  }
  .hero h1 { font-size: 2rem; font-weight: 700; margin: 0; }
  .hero p  { opacity: .85; margin-top: .4rem; font-size: 1rem; }

  /* Metric cards */
  div[data-testid="metric-container"] {
    background: white;
    border-radius: 12px;
    padding: 1rem 1.2rem;
    box-shadow: 0 1px 6px rgba(0,0,0,.08);
    border-top: 3px solid #2d6a9f;
  }

  /* Upload area */
  .stFileUploader > div {
    border: 2px dashed #2d6a9f !important;
    border-radius: 12px !important;
    background: #f0f7ff !important;
  }

  /* Buttons */
  .stButton > button {
    background: linear-gradient(135deg, #1e3a5f, #2d6a9f);
    color: white;
    border: none;
    border-radius: 8px;
    padding: .6rem 2rem;
    font-weight: 600;
    font-size: 1rem;
    width: 100%;
    transition: opacity .2s;
  }
  .stButton > button:hover { opacity: .88; }

  /* Tab styling */
  .stTabs [data-baseweb="tab-list"] {
    gap: 6px;
    border-bottom: 2px solid #E2E8F0;
  }
  .stTabs [data-baseweb="tab"] {
    border-radius: 8px 8px 0 0;
    font-weight: 500;
    padding: .5rem 1.2rem;
  }
  .stTabs [aria-selected="true"] {
    background: #dbeafe;
    color: #1D4ED8 !important;
  }

  /* Insight card */
  .insight-box {
    padding: 1rem 1.2rem;
    border-radius: 10px;
    border-left: 4px solid #2d6a9f;
    background: white;
    margin-bottom: .7rem;
    box-shadow: 0 1px 4px rgba(0,0,0,.06);
  }
  .insight-box.p1 { border-color:#E53E3E; background:#fff5f5; }
  .insight-box.p2 { border-color:#DD6B20; background:#fffaf0; }
  .insight-box.p3 { border-color:#2d6a9f; background:#ebf4ff; }
  .insight-box.p4 { border-color:#38A169; background:#f0fff4; }

  /* Sidebar log */
  .log-entry { font-size:.78rem; color:#4A5568; padding:.2rem 0; border-bottom:1px solid #EDF2F7; }
</style>
""", unsafe_allow_html=True)


# -----------------------------------------------------------------------
# Sidebar
# -----------------------------------------------------------------------
with st.sidebar:
    st.markdown("## ⚙️ Settings")
    config_path = os.path.join(os.path.dirname(__file__), "config.yaml")
    if os.path.exists(config_path):
        st.success("✅ config.yaml loaded")
    else:
        st.info("ℹ️ No config.yaml found — using defaults")

    st.markdown("---")
    st.markdown("### 📋 Pipeline Log")
    log_placeholder = st.empty()

    st.markdown("---")
    st.markdown("""
    **How it works:**
    1. Upload an Excel or CSV file
    2. Click **Run Analysis**
    3. Explore results in tabs
    4. Download the HTML or PDF report
    """)


# -----------------------------------------------------------------------
# Hero header
# -----------------------------------------------------------------------
st.markdown("""
<div class="hero">
  <h1>📊 Automated Data Analysis Agent</h1>
  <p>Upload any Excel or CSV file — get instant schema inference, data quality checks,
  semantic modeling, auto-analysis, smart visualizations, and a stakeholder report.</p>
</div>
""", unsafe_allow_html=True)


# -----------------------------------------------------------------------
# File upload
# -----------------------------------------------------------------------
uploaded_file = st.file_uploader(
    "Upload your Data file",
    type=["xlsx", "xls", "csv"],
    help="Supports .xlsx, .xls, and .csv files up to 200,000 rows",
    key="file_uploader",
)

run_col, _ = st.columns([1, 3])
with run_col:
    run_btn = st.button("🚀 Run Analysis", disabled=uploaded_file is None, key="run_btn")


# -----------------------------------------------------------------------
# Session state helpers
# -----------------------------------------------------------------------
if "result" not in st.session_state:
    st.session_state.result = None
if "logs" not in st.session_state:
    st.session_state.logs = []


def _update_log(logs: list[str]):
    html = "".join(f"<div class='log-entry'>{l}</div>" for l in logs[-30:])
    log_placeholder.markdown(html, unsafe_allow_html=True)


# -----------------------------------------------------------------------
# Run pipeline
# -----------------------------------------------------------------------
if run_btn and uploaded_file is not None:
    st.session_state.result = None
    st.session_state.logs = []

    progress_bar = st.progress(0)
    status_text = st.empty()

    def on_progress(step: int, total: int, message: str):
        pct = int(step / total * 100)
        progress_bar.progress(pct)
        status_text.info(f"**Step {step}/{total}** — {message}")
        st.session_state.logs.append(message)
        _update_log(st.session_state.logs)

    try:
        from agent.orchestrator import run_pipeline

        file_bytes = io.BytesIO(uploaded_file.read())
        result = run_pipeline(
            file=file_bytes,
            filename=uploaded_file.name,
            config_path=config_path if os.path.exists(config_path) else None,
            progress_callback=on_progress,
        )
        st.session_state.result = result
        st.session_state.logs = result.get("logs", [])
        _update_log(st.session_state.logs)
        progress_bar.progress(100)
        status_text.success(
            f"✅ Analysis complete in {result['elapsed_seconds']}s — "
            f"{len(result['analysis'].get('insights', []))} insights, "
            f"{len(result['charts'])} charts"
        )
    except Exception as e:
        status_text.error(f"❌ Pipeline failed: {e}")
        logger.exception("Pipeline error")


# -----------------------------------------------------------------------
# Results tabs
# -----------------------------------------------------------------------
if st.session_state.result:
    result = st.session_state.result
    meta = result.get("metadata", {})
    schema = result.get("schema", {})
    quality = result.get("quality", {})
    semantic = result.get("semantic", {})
    analysis = result.get("analysis", {})
    charts = result.get("charts", [])
    report_html = result.get("report_html", "")

    # Top-level metrics
    ds = analysis.get("dataset_summary", {})
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Rows", f"{ds.get('rows', 0):,}")
    c2.metric("Columns", ds.get("columns", 0))
    c3.metric("Complete Rows", f"{ds.get('complete_row_pct', 0):.0f}%")
    c4.metric("Insights", len(analysis.get("insights", [])))
    c5.metric("Charts", len(charts))

    st.markdown("---")

    tabs = st.tabs([
        "📋 Data Quality",
        "🗂️ Schema",
        "🧠 Semantic Layer",
        "📈 Analysis & Insights",
        "📊 Charts",
        "📄 Download Report",
    ])

    # ---- Tab 1: Quality ---------------------------------------------------
    with tabs[0]:
        st.subheader("Data Quality Report")
        overall_score = quality.get("overall_score", 1.0)
        q_col1, q_col2 = st.columns([1, 3])
        with q_col1:
            color = "normal" if overall_score >= 0.8 else "inverse"
            st.metric("Quality Score", f"{int(overall_score * 100)}%", delta=None)

        with q_col2:
            issues = quality.get("issues", [])
            if issues:
                st.error("**Issues found:**\n" + "\n".join(f"- {i}" for i in issues[:10]))
            else:
                st.success("No major data quality issues found.")

        import pandas as pd
        col_quality = quality.get("column_quality", [])
        if col_quality:
            st.markdown("#### Per-Column Quality")
            df_q = pd.DataFrame(col_quality)
            display_cols = [c for c in [
                "column", "total_rows", "non_null_count", "null_pct",
                "unique_count", "duplicate_count", "outlier_count"
            ] if c in df_q.columns]
            st.dataframe(
                df_q[display_cols].style.background_gradient(
                    subset=["null_pct"] if "null_pct" in display_cols else [],
                    cmap="RdYlGn_r",
                ),
                use_container_width=True,
                height=400,
            )

    # ---- Tab 2: Schema ----------------------------------------------------
    with tabs[1]:
        st.subheader("Schema / Data Dictionary")
        data_dict = schema.get("data_dictionary", [])
        if data_dict:
            import pandas as pd
            df_schema = pd.DataFrame(data_dict)
            # Limit long notes/samples for display
            for col in ["sample_values", "notes"]:
                if col in df_schema.columns:
                    df_schema[col] = df_schema[col].astype(str).str[:80]
            display_cols = [c for c in [
                "column", "inferred_type", "non_null_count", "null_pct",
                "unique_count", "sample_values", "notes"
            ] if c in df_schema.columns]
            st.dataframe(df_schema[display_cols], use_container_width=True, height=450)

            # Type breakdown
            if "inferred_type" in df_schema.columns:
                type_counts = df_schema["inferred_type"].value_counts()
                st.markdown("#### Column Type Distribution")
                import plotly.express as px
                fig = px.pie(
                    values=type_counts.values,
                    names=type_counts.index,
                    color_discrete_sequence=px.colors.qualitative.Set2,
                    hole=0.4,
                )
                fig.update_layout(height=320, margin=dict(t=20, b=20))
                st.plotly_chart(fig, use_container_width=True)

    # ---- Tab 3: Semantic Layer --------------------------------------------
    with tabs[2]:
        st.subheader("Semantic Layer")

        def _show_sem_group(title, items, key_field="raw_column"):
            if items:
                st.markdown(f"**{title}** ({len(items)})")
                cols = st.columns(min(len(items), 4))
                for i, item in enumerate(items):
                    cols[i % 4].info(item.get(key_field, str(item)))

        _show_sem_group("📐 Dimensions", semantic.get("dimensions", []))
        _show_sem_group("📏 Measures", semantic.get("measures", []))
        _show_sem_group("📅 Time Fields", semantic.get("time_fields", []))
        _show_sem_group("🔑 Entities", semantic.get("entities", []))

        kpis = semantic.get("kpis", [])
        if kpis:
            st.markdown(f"**🎯 KPIs** ({len(kpis)})")
            for kpi in kpis:
                st.markdown(f"- **{kpi.get('name', '')}** — {kpi.get('description', '')}")

        # YAML export
        import yaml
        yaml_str = yaml.dump(
            {k: v for k, v in semantic.items() if k != "dataframe"},
            default_flow_style=False,
            allow_unicode=True,
        )
        with st.expander("📄 View Semantic Layer as YAML"):
            st.code(yaml_str, language="yaml")

        st.download_button(
            "⬇️ Download Semantic Layer YAML",
            data=yaml_str,
            file_name="semantic_layer.yaml",
            mime="text/yaml",
        )

    # ---- Tab 4: Insights --------------------------------------------------
    with tabs[3]:
        st.subheader("Key Insights")
        insights = analysis.get("insights", [])
        priority_map = {1: ("🔴", "p1", "Critical"), 2: ("🟠", "p2", "High"),
                        3: ("🔵", "p3", "Medium"), 4: ("🟢", "p4", "Low")}

        if insights:
            for ins in insights:
                p = ins.get("priority", 3)
                icon, cls, level = priority_map.get(p, ("🔵", "p3", "Medium"))
                st.markdown(f"""
                <div class="insight-box {cls}">
                  <div style="font-size:.75rem;font-weight:600;color:#718096;text-transform:uppercase;letter-spacing:.05em;margin-bottom:.2rem;">
                    {icon} {ins.get('category', '')} &bull; {level}
                  </div>
                  <div style="font-weight:600;margin-bottom:.25rem;">{ins.get('title', '')}</div>
                  <div style="font-size:.875rem;color:#4A5568;">{ins.get('detail', '')}</div>
                  <div style="font-size:.75rem;color:#A0AEC0;margin-top:.4rem;">
                    Confidence: {int(ins.get('confidence', 0.8) * 100)}%
                  </div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("No insights generated.")

        st.markdown("---")

    # ---- Tab 5: Charts ----------------------------------------------------
    with tabs[4]:
        st.subheader("Visualizations")
        if charts:
            for i, chart in enumerate(charts):
                with st.expander(f"📊 {chart.get('title', f'Chart {i+1}')}", expanded=i < 3):
                    st.caption(f"💡 {chart.get('insight', '')}")
                    st.plotly_chart(
                        chart["fig"],
                        use_container_width=True,
                        key=f"chart_{i}",
                    )
                    st.caption(f"📌 {chart.get('stakeholder_note', '')}")
        else:
            st.info("No charts generated.")

    # ---- Tab 6: Download Report -------------------------------------------
    with tabs[5]:
        st.subheader("Download Analysis Report")
        st.markdown("""
        The report is a **self-contained HTML file** that includes:
        - 📋 Dataset overview & data quality
        - 🗂️ Full schema / data dictionary
        - 🧠 Semantic layer summary
        - 💡 All key insights
        - 📊 All interactive Plotly charts embedded inline
        """)

        report_filename = f"analysis_report_{meta.get('filename', 'report').replace(' ', '_').replace('.xlsx', '').replace('.xls', '')}.html"
        st.download_button(
            label="⬇️ Download HTML Report",
            data=report_html.encode("utf-8"),
            file_name=report_filename,
            mime="text/html",
            use_container_width=True,
        )

        # PDF Download
        try:
            from agent.pdf_generator import generate_pdf_report
            pdf_bytes = generate_pdf_report(result)
            pdf_filename = report_filename.replace(".html", ".pdf")
            
            st.download_button(
                label="⬇️ Download PDF Report",
                data=pdf_bytes,
                file_name=pdf_filename,
                mime="application/pdf",
                use_container_width=True,
            )
        except Exception as e:
            st.warning(f"⚠️ PDF generation is temporarily unavailable: {e}")

        st.markdown("#### Report Preview")
        st.components.v1.html(report_html, height=600, scrolling=True)

else:
    # Landing placeholder
    st.markdown("""
    <div style="text-align:center;padding:4rem 2rem;color:#A0AEC0;">
      <div style="font-size:4rem;">📁</div>
      <div style="font-size:1.2rem;margin-top:1rem;font-weight:500;">
        Upload an Excel file above to get started
      </div>
      <div style="font-size:.9rem;margin-top:.5rem;">
        The agent will automatically analyse your data end-to-end
      </div>
    </div>
    """, unsafe_allow_html=True)
