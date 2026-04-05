"""
QueryGenie API
--------------
FastAPI wrapper around existing modules.
Endpoints:
  POST /query     - Generate SQL and execute
  POST /explain   - Explain a SQL query
  GET  /schema    - Get current database schema
  GET  /models    - List available models
  GET  /examples  - Get example questions
  POST /upload    - Upload a database file
"""

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import tempfile
import os
import shutil
from dotenv import load_dotenv

load_dotenv()

from src.schema_extractor import SchemaExtractor
from src.llm_engine import generate_sql, explain_sql, get_available_models
from src.query_executor import QueryExecutor
from src.utils import csv_to_sqlite
from src.example_generator import get_examples

app = FastAPI(title="QueryGenie API", version="1.0.0")

# Allow Next.js frontend to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Will restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- State ----
# In a production app you'd use a database or Redis for this.
# For our portfolio project, in-memory state is fine.

state = {
    "db_path": "data/chinook.db",
    "db_name": "chinook_demo",
    "schema_text": None,
    "executor": None,
    "extractor": None,
}


def _load_database(db_path: str, db_name: str):
    """Load a database and extract its schema."""
    state["db_path"] = db_path
    state["db_name"] = db_name
    state["extractor"] = SchemaExtractor(db_path)
    state["schema_text"] = state["extractor"].format_schema_for_llm()
    state["executor"] = QueryExecutor(db_path)


# Load default database on startup
_load_database("data/chinook.db", "chinook_demo")


# ---- Request/Response Models ----

class QueryRequest(BaseModel):
    question: str
    model_key: str = "groq-llama3"

class ExplainRequest(BaseModel):
    sql: str
    model_key: str = "groq-llama3"


# ---- Endpoints ----

@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/models")
def list_models():
    """List all available LLM models."""
    return get_available_models()


@app.get("/schema")
def get_schema():
    """Get the current database schema."""
    if not state["schema_text"]:
        raise HTTPException(status_code=400, detail="No database loaded")
    return {
        "schema": state["schema_text"],
        "db_name": state["db_name"],
    }


@app.get("/examples")
def get_example_questions():
    """Get example questions for the current database."""
    if not state["extractor"]:
        raise HTTPException(status_code=400, detail="No database loaded")
    examples = get_examples(state["schema_text"], state["extractor"])
    return {"examples": examples}


@app.post("/query")
def run_query(req: QueryRequest):
    """Generate SQL from a question and execute it."""
    if not state["schema_text"]:
        raise HTTPException(status_code=400, detail="No database loaded")

    # Step 1: Generate SQL
    llm_result = generate_sql(
        question=req.question,
        schema_text=state["schema_text"],
        model_key=req.model_key,
    )

    if not llm_result["success"]:
        return {
            "success": False,
            "sql": None,
            "data": None,
            "columns": [],
            "row_count": 0,
            "error": llm_result["error"],
        }

    # Step 2: Execute SQL
    exec_result = state["executor"].execute(llm_result["sql"])

    if not exec_result["success"]:
        return {
            "success": False,
            "sql": llm_result["sql"],
            "data": None,
            "columns": [],
            "row_count": 0,
            "error": exec_result["error"],
        }

    # Convert DataFrame to JSON-safe format
    data = exec_result["data"].to_dict(orient="records") if exec_result["data"] is not None else None

    return {
        "success": True,
        "sql": llm_result["sql"],
        "data": data,
        "columns": exec_result["columns"],
        "row_count": exec_result["row_count"],
        "truncated": exec_result["truncated"],
        "error": None,
    }


@app.post("/explain")
def explain_query(req: ExplainRequest):
    """Explain a SQL query in plain English."""
    result = explain_sql(req.sql, model_key=req.model_key)
    return result


@app.post("/upload")
async def upload_database(file: UploadFile = File(...)):
    """Upload a .sqlite, .db, or .csv file."""
    suffix = os.path.splitext(file.filename)[1].lower()
    if suffix not in [".sqlite", ".db", ".csv"]:
        raise HTTPException(status_code=400, detail="Only .sqlite, .db, or .csv files are supported")

    # Save uploaded file
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    # Convert CSV to SQLite if needed
    if suffix == ".csv":
        db_path = tmp_path.replace(".csv", ".db")
        table_name = os.path.splitext(file.filename)[0]
        table_name = table_name.replace(" ", "_").replace("-", "_")
        csv_to_sqlite(tmp_path, db_path, table_name)
    else:
        db_path = tmp_path

    _load_database(db_path, file.filename)

    return {
        "success": True,
        "db_name": file.filename,
        "schema": state["schema_text"],
    }


@app.post("/reset")
def reset_to_demo():
    """Reset to the demo Chinook database."""
    _load_database("data/chinook.db", "chinook_demo")
    return {"success": True, "db_name": "chinook_demo"}
