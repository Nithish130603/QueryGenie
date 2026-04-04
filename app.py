"""
QueryGenie — Natural Language to SQL
=====================================
Main Streamlit application entry point.

Architecture:
    User Question → Schema Extractor → LLM Engine → Query Executor → Display

Layout:
    Sidebar: Database selection, model selection, schema viewer
    Main area: Chat-style Q&A with SQL and results display
"""

import streamlit as st
import os
import tempfile
from dotenv import load_dotenv

from src.schema_extractor import SchemaExtractor
from src.llm_engine import generate_sql, get_available_models, explain_sql
from src.query_executor import QueryExecutor
from src.utils import csv_to_sqlite
from src.visualizer import suggest_chart_type, create_chart, render_metric
from src.example_generator import get_examples

# Load environment variables (API keys)
load_dotenv()

# ---- Page Configuration ----
# Must be the first Streamlit command
st.set_page_config(
    page_title="QueryGenie — Talk to Your Database",
    page_icon="🧞",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---- Session State Initialization ----
# Why initialize here?
#   Streamlit reruns the full script on every interaction.
#   Session state persists across reruns. We check 'if key not in'
#   to avoid resetting state on each rerun.

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if "schema_text" not in st.session_state:
    st.session_state.schema_text = None

if "db_path" not in st.session_state:
    st.session_state.db_path = None

if "executor" not in st.session_state:
    st.session_state.executor = None

if "current_db_name" not in st.session_state:
    st.session_state.current_db_name = None

if "example_question" not in st.session_state:
    st.session_state.example_question = None

if "explain_index" not in st.session_state:
    st.session_state.explain_index = None


# ============================================================
#  SIDEBAR — Configuration
# ============================================================

with st.sidebar:
    st.title("⚙️ Configuration")

    # ---- Database Selection ----
    st.subheader("📁 Database")
    db_choice = st.radio(
        "Choose a database:",
        options=["Demo (Chinook Music Store)", "Upload your own"],
        help="Chinook is a sample music store database with artists, albums, tracks, customers, and invoices.",
    )

    if db_choice == "Demo (Chinook Music Store)":
        db_path = "data/chinook.db"
        db_name = "chinook_demo"

        if st.session_state.current_db_name != db_name:
            st.session_state.current_db_name = db_name
            st.session_state.db_path = db_path
            extractor = SchemaExtractor(db_path)
            st.session_state.schema_text = extractor.format_schema_for_llm()
            st.session_state.executor = QueryExecutor(db_path)
            st.session_state.chat_history = []

    else:
        uploaded_file = st.file_uploader(
            "Upload a .sqlite, .db, or .csv file",
            type=["sqlite", "db", "csv"],
        )

        if uploaded_file is not None:
            db_name = f"upload_{uploaded_file.name}"

            # Only re-process if this is a new file
            if st.session_state.current_db_name != db_name:
                suffix = os.path.splitext(uploaded_file.name)[1]
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                    tmp.write(uploaded_file.getbuffer())
                    tmp_path = tmp.name

                if suffix == ".csv":
                    db_path = tmp_path.replace(".csv", ".db")
                    table_name = os.path.splitext(uploaded_file.name)[0]
                    table_name = table_name.replace(" ", "_").replace("-", "_")
                    csv_to_sqlite(tmp_path, db_path, table_name)
                else:
                    db_path = tmp_path

                st.session_state.current_db_name = db_name
                st.session_state.db_path = db_path
                extractor = SchemaExtractor(db_path)
                st.session_state.schema_text = extractor.format_schema_for_llm()
                st.session_state.executor = QueryExecutor(db_path)
                st.session_state.chat_history = []

                st.success(f"Loaded: {uploaded_file.name}")
        else:
            # No file uploaded yet — clear state if we were previously on a file
            if st.session_state.current_db_name and st.session_state.current_db_name.startswith("upload_"):
                st.session_state.current_db_name = None
                st.session_state.schema_text = None
                st.session_state.db_path = None
                st.session_state.executor = None
                st.session_state.chat_history = []

    # ---- Model Selection ----
    st.subheader("🤖 Model")
    available_models = get_available_models()
    selected_model = st.selectbox(
        "Choose an LLM:",
        options=list(available_models.keys()),
        format_func=lambda x: f"{x} — {available_models[x]}",
        index=list(available_models.keys()).index("mistral"),  # default to local
    )

    # ---- Schema Viewer ----
    if st.session_state.schema_text:
        st.subheader("🗂️ Database Schema")
        with st.expander("View full schema", expanded=False):
            st.code(st.session_state.schema_text, language="text")

    # ---- Example Questions ----
    if st.session_state.schema_text and st.session_state.db_path:
        st.subheader("💡 Example Questions")
        extractor = SchemaExtractor(st.session_state.db_path)
        examples = get_examples(st.session_state.schema_text, extractor)

        for ex in examples:
            if st.button(
                f"{ex['question']}",
                key=f"ex_{ex['question'][:30]}",
                use_container_width=True,
                help=ex["category"],
            ):
                st.session_state.example_question = ex["question"]
                st.rerun()


# ============================================================
#  MAIN AREA — Chat Interface
# ============================================================

st.title("🧞 QueryGenie")
st.caption("Ask questions about your database in plain English. I'll write and run the SQL for you.")

# ---- Check if database is loaded ----
if st.session_state.schema_text is None:
    st.info("👈 Select or upload a database from the sidebar to get started.")
    st.stop()

# ---- Display chat history ----
for entry in st.session_state.chat_history:
    # User message
    with st.chat_message("user"):
        st.write(entry["question"])

    # Assistant response
    with st.chat_message("assistant"):
        if entry["success"]:
            st.code(entry["sql"], language="sql")
            if entry["data"] is not None and not entry["data"].empty:
                # Auto-visualization
                suggestion = suggest_chart_type(entry["data"])

                if suggestion["chart_type"] == "metric":
                    metrics = render_metric(entry["data"], suggestion)
                    cols = st.columns(len(metrics))
                    for i, m in enumerate(metrics):
                        cols[i].metric(label=m["label"], value=m["value"])
                else:
                    chart = create_chart(entry["data"], suggestion)
                    if chart:
                        st.plotly_chart(chart, use_container_width=True)
                    st.dataframe(entry["data"], use_container_width=True)

                if entry["truncated"]:
                    st.warning(
                        f"Results truncated to {len(entry['data'])} rows. "
                        "The full result set is larger."
                    )
            st.caption(f"Model: {entry['model']} · Rows: {entry['row_count']}")

            # Query explanation (lazy-loaded with click-to-reveal)
            if entry.get("sql"):
                entry_index = st.session_state.chat_history.index(entry)

                if entry.get("explanation"):
                    st.markdown(f"**🔍 Explanation:**")
                    st.markdown(entry["explanation"])
                elif st.session_state.explain_index == entry_index:
                    with st.spinner("🧠 Generating explanation..."):
                        result = explain_sql(
                            entry["sql"],
                            model_key=entry["model"],
                        )
                    if result["success"]:
                        st.session_state.chat_history[entry_index]["explanation"] = result["explanation"]
                        st.session_state.explain_index = None
                        st.rerun()
                    else:
                        st.error(result["error"])
                        st.session_state.explain_index = None
                else:
                    def set_explain_hist(idx=entry_index):
                        st.session_state.explain_index = idx

                    st.button(
                        "🔍 Explain this SQL",
                        key=f"explain_{entry_index}",
                        on_click=set_explain_hist,
                    )
        else:
            st.error(entry["error"])

# ---- Chat input ----
# Check if an example question was clicked
question = st.chat_input("Ask a question about your database...")

if st.session_state.example_question:
    question = st.session_state.example_question
    st.session_state.example_question = None

if question:
    # Display user message immediately
    with st.chat_message("user"):
        st.write(question)

    # Generate and execute
    with st.chat_message("assistant"):
        with st.spinner("Generating SQL..."):
            # Step 1: Generate SQL
            llm_result = generate_sql(
                question=question,
                schema_text=st.session_state.schema_text,
                model_key=selected_model,
            )

        if llm_result["success"]:
            # Show the generated SQL
            st.code(llm_result["sql"], language="sql")

            with st.spinner("Running query..."):
                # Step 2: Execute the SQL
                exec_result = st.session_state.executor.execute(llm_result["sql"])

            if exec_result["success"]:
                # Auto-visualization
                suggestion = suggest_chart_type(exec_result["data"])

                if suggestion["chart_type"] == "metric":
                    metrics = render_metric(exec_result["data"], suggestion)
                    cols = st.columns(len(metrics))
                    for i, m in enumerate(metrics):
                        cols[i].metric(label=m["label"], value=m["value"])
                else:
                    chart = create_chart(exec_result["data"], suggestion)
                    if chart:
                        st.plotly_chart(chart, use_container_width=True)
                    st.dataframe(exec_result["data"], use_container_width=True)

                if exec_result["truncated"]:
                    st.warning(
                        f"Results truncated to {exec_result['row_count']} rows. "
                        "The full result set is larger."
                    )
                st.caption(
                    f"Model: {selected_model} · Rows: {exec_result['row_count']}"
                )

                # on_click callback runs BEFORE the rerun,
                # guaranteeing session state is set
                current_index = len(st.session_state.chat_history)

                def set_explain(idx=current_index):
                    st.session_state.explain_index = idx

                st.button(
                    "🔍 Explain this SQL",
                    key=f"explain_live_{current_index}",
                    on_click=set_explain,
                )

                # Save to history
                st.session_state.chat_history.append({
                    "question": question,
                    "success": True,
                    "sql": llm_result["sql"],
                    "data": exec_result["data"],
                    "row_count": exec_result["row_count"],
                    "truncated": exec_result["truncated"],
                    "model": selected_model,
                    "error": None,
                    "explanation": None,
                })
            else:
                # SQL execution failed
                st.error(f"Query failed: {exec_result['error']}")
                st.code(llm_result["sql"], language="sql")
                st.caption("The generated SQL had an error. Try rephrasing your question.")

                st.session_state.chat_history.append({
                    "question": question,
                    "success": False,
                    "sql": llm_result["sql"],
                    "data": None,
                    "row_count": 0,
                    "truncated": False,
                    "model": selected_model,
                    "error": exec_result["error"],
                    "explanation": None,
                })
        else:
            # LLM generation failed
            st.error(llm_result["error"])

            st.session_state.chat_history.append({
                "question": question,
                "success": False,
                "sql": None,
                "data": None,
                "row_count": 0,
                "truncated": False,
                "model": selected_model,
                "error": llm_result["error"],
                "explanation": None,
            })

# ============================================================
#  SIDEBAR — Chat Controls (rendered last so chat_history is populated)
# ============================================================

with st.sidebar:
    if st.session_state.chat_history:
        st.divider()

        col1, col2 = st.columns(2)

        with col1:
            def clear_chat():
                st.session_state.chat_history = []
                st.session_state.explain_index = None

            st.button(
                "🗑️ Clear",
                on_click=clear_chat,
                use_container_width=True,
            )

        with col2:
            import csv
            import io

            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(["question", "sql", "success", "rows", "model"])
            for entry in st.session_state.chat_history:
                writer.writerow([
                    entry["question"],
                    entry.get("sql", ""),
                    entry["success"],
                    entry["row_count"],
                    entry["model"],
                ])

            st.download_button(
                "📥 Export",
                data=output.getvalue(),
                file_name="querygenie_history.csv",
                mime="text/csv",
                use_container_width=True,
            )