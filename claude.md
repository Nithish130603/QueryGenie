# CLAUDE.md — QueryGenie Project Guide

## Project Overview

QueryGenie is a Natural Language to SQL application that allows users to ask questions about databases in plain English and receive SQL queries, executed results, and auto-generated visualizations. It supports multiple LLM providers (API and local) and works with both a built-in demo database and user-uploaded databases (SQLite and CSV).

**Live Stack:** Streamlit (frontend) + LangChain (LLM abstraction) + SQLAlchemy (schema reflection) + SQLite (database) + Plotly (visualization)

**Target Audience:** Portfolio project for data science internship applications. Must be impressive to technical recruiters at companies like Canva, Atlassian, Quantium, Google.

---

## Architecture

```
User Question (English)
        │
        ▼
┌─────────────────────┐
│  Schema Extractor    │ ◄── Reads DB structure via SQLAlchemy reflection
│  (schema_extractor)  │     Database-agnostic (works with any SQLite DB)
└────────┬────────────┘
         │ schema text
         ▼
┌─────────────────────┐
│  LLM Engine          │ ◄── Converts question + schema → SQL
│  (llm_engine)        │     Supports: OpenAI, Anthropic, Google, Ollama
└────────┬────────────┘
         │ generated SQL
         ▼
┌─────────────────────┐
│  Query Executor      │ ◄── Runs SQL safely against the database
│  (query_executor)    │     Safety: whitelist SELECT/WITH only
└────────┬────────────┘
         │ pandas DataFrame
         ▼
┌─────────────────────┐
│  Visualizer          │ ◄── Auto-selects chart type from result shape
│  (visualizer)        │     Types: metric, bar, pie, line, table
└────────┬────────────┘
         │ Plotly figure
         ▼
┌─────────────────────┐
│  Streamlit UI        │ ◄── Chat interface with sidebar config
│  (app.py)            │     Example questions, query explanation
└─────────────────────┘
```

### Data Flow Summary
1. User types a question or clicks an example
2. SchemaExtractor reads the current database structure via SQLAlchemy reflection
3. LLM Engine builds a system prompt with schema + rules + few-shot examples, sends to selected LLM
4. Generated SQL is validated (whitelist: only SELECT/WITH allowed)
5. Query Executor runs the SQL against SQLite, returns a pandas DataFrame
6. Visualizer analyzes column types (categorical, numeric, temporal) and picks the best chart
7. Streamlit renders: SQL code block → chart (if applicable) → data table → explain button

---

## Project Structure

```
QueryGenie/
├── app.py                      # Streamlit entry point — UI layout and interaction logic
├── src/
│   ├── __init__.py
│   ├── schema_extractor.py     # SQLAlchemy-based schema reflection
│   ├── llm_engine.py           # LLM abstraction, prompt engineering, SQL generation
│   ├── query_executor.py       # Safe SQL execution with validation and limits
│   ├── visualizer.py           # Heuristic-based auto-visualization
│   ├── example_generator.py    # Smart example question generation
│   └── utils.py                # Helpers (CSV-to-SQLite conversion)
├── data/
│   └── chinook.db              # Demo database (Chinook music store)
├── assets/                     # Screenshots, architecture diagrams for README
├── requirements.txt
├── .env                        # API keys (git-ignored)
├── .env.example                # Template for API keys
├── .gitignore
├── README.md
└── claude.md                   # This file
```

---

## Module Details

### `src/schema_extractor.py`
- **Class:** `SchemaExtractor`
- **Purpose:** Connects to any SQLite database and extracts full schema (tables, columns, types, primary keys, foreign keys)
- **Key method:** `format_schema_for_llm()` — returns a clean text representation optimized for LLM consumption
- **Design choice:** Uses SQLAlchemy's `inspect()` and `MetaData.reflect()` for database-agnostic reflection
- **Why text over JSON for schema format:** LLMs generate better SQL with structured natural text (supported by DIN-SQL and DAIL-SQL research)

### `src/llm_engine.py`
- **Key function:** `generate_sql(question, schema_text, model_key)` → dict with sql, success, error
- **Key function:** `explain_sql(sql, model_key)` → dict with explanation, success, error
- **Key function:** `get_available_models()` → dict of model_key: description
- **Design pattern:** MODEL_REGISTRY dict maps model keys to provider classes (Open/Closed Principle)
- **Prompt engineering:** System prompt uses role prompting + schema injection + strict output rules + few-shot examples (3 examples)
- **Safety:** Prompt restricts to SELECT-only + code-level validation via `_is_safe_sql()`
- **Temperature:** 0.0 for deterministic SQL generation
- **Supported providers:**
  - `gpt-4o-mini`, `gpt-4o` — OpenAI (ChatOpenAI)
  - `claude-sonnet` — Anthropic (ChatAnthropic)
  - `gemini-flash` — Google (ChatGoogleGenerativeAI)
  - `mistral`, `llama3` — Local via Ollama (ChatOllama)
- **Adding a new model:** Add one entry to MODEL_REGISTRY. Zero other code changes.

### `src/query_executor.py`
- **Class:** `QueryExecutor`
- **Purpose:** Safely execute SQL and return results as pandas DataFrame
- **Key method:** `execute(sql)` → dict with success, data (DataFrame), row_count, truncated, columns, error
- **Safety layers:**
  1. Whitelist validation (SELECT/WITH only)
  2. Keyword blocking (DROP, DELETE, INSERT, UPDATE, etc.) with word boundary regex
  3. Row limit (default 1000) to prevent browser overload
  4. Timeout (default 30 seconds) to prevent runaway queries
- **Design choice:** Creates fresh SQLite connection per query (thread safety for Streamlit)
- **Design choice:** Defense-in-depth — duplicates safety check from llm_engine because executor might be called directly
- **Truncation detection:** Uses `fetchmany(limit + 1)` trick to detect more rows without counting full result set
- **Duplicate column handling:** Auto-renames duplicate column names with `_1`, `_2` suffixes (LLMs sometimes generate duplicate aliases)

### `src/visualizer.py`
- **Key function:** `suggest_chart_type(df)` → dict with chart_type, x, y, title, pie_eligible
- **Key function:** `create_chart(df, suggestion)` → Plotly Figure or None
- **Key function:** `render_metric(df, suggestion)` → list of {label, value} dicts
- **Chart selection heuristics:**
  - Single cell (1 row, 1 col) → metric (big number display)
  - Single row, multiple cols → metric (multiple values)
  - Temporal + numeric columns → line chart
  - 1 categorical + 1 numeric → bar chart
  - ≤ 6 categories → also pie-eligible
  - Everything else → table only
- **Column type detection order (matters!):**
  1. Check datetime dtype first
  2. Reject numeric types from datetime conversion (prevents pandas aggressive coercion)
  3. Try string-to-datetime conversion
  4. Check numeric dtype
  5. Low-cardinality numerics (≤ 6 unique, < 50% of rows) → treat as categorical
  6. Default: categorical
- **Known bug fixed:** `pd.to_datetime()` converts integers to 1970s timestamps. Guard added: skip numeric columns before attempting datetime conversion.

### `src/example_generator.py`
- **Key function:** `get_examples(schema_text, extractor)` → list of {question, category} dicts
- **Two modes:**
  1. **Known databases:** Curated hand-picked examples (currently: Chinook with 8 examples covering COUNT, JOIN, GROUP BY, ORDER BY, aggregation, multi-table)
  2. **Unknown databases:** Auto-generated via heuristics analyzing schema
- **Heuristic strategies:** Simple count, GROUP BY on text columns, AVG on numeric columns, Top N, JOIN via foreign keys
- **Filters:** Skips primary key columns and ID-like columns (ending in "id") from example generation
- **Why heuristics over LLM:** Zero latency (instant sidebar load), zero cost, deterministic, guaranteed schema-valid
- **Cap:** Maximum 8 examples to avoid overwhelming the sidebar

### `src/utils.py`
- **Key function:** `csv_to_sqlite(csv_path, db_path, table_name)` → path to created SQLite DB
- **Column name cleaning:** Replaces spaces, dots, hyphens with underscores
- **Uses:** `pandas.read_csv()` + `DataFrame.to_sql()` for conversion

### `app.py`
- **Layout:** Sidebar (database selector, model selector, schema viewer, example questions) + Main area (chat interface)
- **Session state keys:**
  - `chat_history` — list of query result dicts
  - `schema_text` — current database schema as formatted text
  - `db_path` — path to current database file
  - `executor` — QueryExecutor instance for current database
  - `current_db_name` — stable identifier for loaded database (not temp file path)
  - `example_question` — pending example question from sidebar click
  - `explain_index` — which chat entry to generate explanation for
- **Database switching:** Tracked by `current_db_name` (not file path) to survive Streamlit reruns. File path was unstable for uploaded files.
- **Example question flow:** Sidebar button → sets `example_question` in session state → `st.rerun()` → main area picks it up as `question`
- **Explain flow:** Button with `on_click` callback → sets `explain_index` → rerun → chat history loop detects index → spinner → LLM call → saves to entry → rerun → displays cached explanation
- **Why on_click callbacks:** Regular `if st.button()` clicks are lost if the button doesn't re-render on the next rerun. `on_click` executes before rerun, guaranteeing session state persistence.

---

## Key Design Decisions & Interview Talking Points

| Decision | Why | Alternative Considered |
|----------|-----|----------------------|
| SQLAlchemy reflection over raw SQL | Database-agnostic, same code for SQLite/PostgreSQL/MySQL | Raw `PRAGMA table_info` — SQLite-specific, not portable |
| Text schema format over JSON | LLMs generate better SQL with structured text (DIN-SQL research) | JSON — adds token overhead without improving comprehension |
| Temperature 0.0 | SQL generation is deterministic — precision over creativity | Higher temp — causes inconsistent/wrong queries |
| Few-shot prompting (3 examples) | 15-25% accuracy improvement over zero-shot on Text-to-SQL benchmarks | Zero-shot — simpler but less accurate |
| Defense-in-depth SQL safety | Never trust upstream; each layer protects itself independently | Single check in LLM engine — fragile if executor called directly |
| Whitelist (SELECT/WITH) over blocklist | Harder to bypass than blocking specific keywords | Blocklist (DROP, DELETE...) — can be circumvented with creative SQL |
| LangChain as thin abstraction only | Unified interface across 4+ providers; not using chains/agents/memory | Direct API calls — separate code per provider |
| MODEL_REGISTRY pattern | Open/Closed Principle — add models without changing existing code | If/else chain — grows unwieldy, violates OCP |
| Heuristic examples over LLM-generated | Zero latency, zero cost, deterministic, guaranteed schema-valid | LLM call — slow sidebar load, costs money, might generate bad questions |
| Streamlit over Flask+React | Value is in ML pipeline, not frontend. Native DataFrame/chart support | React — 3-4 days of frontend boilerplate for marginal benefit |
| Plotly over Matplotlib | Interactive (hover, zoom), native Streamlit integration, web-optimized | Matplotlib — static images, no interactivity |
| Fresh SQLite connection per query | Thread safety in Streamlit's execution model | Connection reuse — causes concurrency bugs in Streamlit |
| `on_click` callbacks over `if st.button()` | Click state survives reruns; prevents lost-click bugs | Regular button — clicks lost when button doesn't re-render |
| `fetchmany(limit+1)` for truncation | Detects "more rows exist" without counting full result set | `fetchall()` + len check — loads entire result into memory |
| pandas DataFrame as result format | Column metadata, native Streamlit/Plotly integration, free sort/filter | Raw tuples — loses column names; list of dicts — clunky for large data |

---

## Common Tasks

### Adding a new LLM provider
1. Install the LangChain integration package: `pip install langchain-<provider>`
2. Add import in `src/llm_engine.py`
3. Add entry to `MODEL_REGISTRY` dict with provider class and model name
4. That's it — no other code changes needed

### Adding a curated example set for a new database
1. Open `src/example_generator.py`
2. Add a constant like `MY_DB_EXAMPLES = [...]`
3. Add detection logic in `is_known_database()` (check for signature tables)
4. Add case in `get_examples()`

### Testing modules independently
```bash
python -m src.schema_extractor    # Prints Chinook schema
python -m src.llm_engine          # Tests SQL generation (needs Ollama or API key)
python -m src.query_executor      # Tests query execution + safety validation
python -m src.visualizer          # Tests chart type selection heuristics
```

---

## Environment Setup

### Prerequisites
- Python 3.10+
- Ollama installed and running (`ollama serve`) for local models
- Mistral model pulled (`ollama pull mistral`)

### Install
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### API Keys (optional — for cloud models)
```bash
cp .env.example .env
# Edit .env with your keys
```

### Run
```bash
streamlit run app.py
```

---

## Bugs Fixed & Lessons Learned

1. **Schema not switching on CSV upload:** Temp file paths are unstable across Streamlit reruns. Fixed by tracking `current_db_name` (file name) instead of file path.
2. **Duplicate column names crash:** LLMs sometimes generate SQL with duplicate aliases. Fixed with auto-deduplication (`col`, `col_1`, `col_2`).
3. **Numeric columns detected as temporal:** `pd.to_datetime()` aggressively converts integers to 1970s timestamps. Fixed by checking `is_numeric_dtype()` before attempting datetime conversion.
4. **Explain button requiring double-click:** Streamlit button clicks are lost if the button doesn't re-render. Fixed with `on_click` callbacks that execute before rerun.
5. **SQLite integer division:** Expressions like `COUNT/COUNT` return 0 instead of a decimal. This is a SQLite quirk — requires explicit CAST to FLOAT. Local models don't always handle this.

---

## Code Style & Conventions

- **Docstrings:** Every module, class, and function has a docstring explaining WHAT it does and WHY design decisions were made
- **Type hints:** Used for function signatures
- **Commit messages:** Conventional commits format (`feat:`, `fix:`, `docs:`, `refactor:`)
- **Error handling:** All modules return structured dicts with `success`, `error` fields — never raise exceptions to the UI layer
- **Security:** Every layer validates independently (defense-in-depth)
- **Comments:** Focus on WHY, not WHAT — explain design reasoning, not obvious code

---

## Upcoming Features (Roadmap)

- [ ] Query history export (download as CSV)
- [ ] Clear chat button
- [ ] Better error messages for non-database questions
- [ ] UI polish (colors, loading animations, about section)
- [ ] Comprehensive README with architecture diagram, screenshots, demo GIF
- [ ] Deploy to Streamlit Cloud
- [ ] Demo video recording
- [ ] LinkedIn post