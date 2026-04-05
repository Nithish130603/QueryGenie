# 🧞 QueryGenie — Talk to Your Database

**Ask questions in plain English. Get SQL, results, and insights instantly.**

QueryGenie converts natural language questions into SQL queries using LLMs, executes them against your database, and displays results with smart formatting — all through a polished chat interface built with Next.js and FastAPI.

![QueryGenie Hero](assets/hero.png)

> 🔗 **[Try the Live Demo →](https://querygenie.up.railway.app)**

---

## ✨ Features

### Natural Language to SQL
Type a question in plain English — QueryGenie generates accurate SQL, runs it, and displays the results. No SQL knowledge required.

### Smart Result Display
Single-value results appear as large metric cards. Multi-row results display in clean, sortable tables. Column names are automatically formatted for readability.

![Metric Display](assets/metric.png)

### Multi-Model Support
Switch between cloud APIs and local models with one click:

| Provider | Models | Best For |
|----------|--------|----------|
| **Groq** | Llama 3.3 70B, Mixtral 8x7B | Blazing fast, free, ideal for demos |
| **OpenAI** | GPT-4o, GPT-4o-mini | Highest accuracy on complex queries |
| **Anthropic** | Claude Sonnet | Strong SQL generation |
| **Google** | Gemini 2.5 Flash | Fast, generous free tier |
| **Ollama** (local) | Mistral, Llama 3 | Free, private, offline development |

### Upload Any Database
Works with the built-in Chinook demo database, or upload your own `.sqlite`, `.db`, or `.csv` file. CSV files are automatically converted to queryable SQLite databases.

![CSV Upload](assets/csv_upload.png)

### SQL Explanation
Click "Explain this query" to get a structured, step-by-step breakdown of any generated query — great for learning SQL or understanding complex JOINs.

![SQL Explanation](assets/explain.png)

### Smart Example Questions
Curated examples for known databases, auto-generated examples for uploaded databases. Each example is clickable and runs instantly.

### Schema Viewer
Expandable schema browser in the sidebar shows all tables and their columns, so you always know what data is available to query.

### Export History
Download your entire query session (questions + generated SQL) as a CSV file for documentation or sharing.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────┐
│                   FRONTEND (Next.js)                │
│  Chat UI · Schema Viewer · File Upload · Export     │
└──────────────────────┬──────────────────────────────┘
                       │ REST API (axios)
┌──────────────────────▼──────────────────────────────┐
│                   BACKEND (FastAPI)                  │
│                                                      │
│  ┌─────────────┐  ┌───────────┐  ┌───────────────┐  │
│  │   Schema     │  │   LLM     │  │    Query      │  │
│  │  Extractor   │→ │  Engine   │→ │   Executor    │  │
│  │ (SQLAlchemy) │  │(LangChain)│  │  (SQLite)     │  │
│  └─────────────┘  └───────────┘  └───────────────┘  │
│                                                      │
│  ┌──────────────┐  ┌──────────────────────────────┐  │
│  │   Example     │  │   Visualizer (chart type     │  │
│  │  Generator    │  │   detection for frontend)    │  │
│  └──────────────┘  └──────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

Each module is independent with a single responsibility. The LLM engine doesn't know about execution; the executor doesn't know about the frontend. This makes the system testable, extensible, and easy to reason about.

---

## 🛡️ Safety & Security

Security is built into every layer (defense-in-depth):

- **Prompt-level:** System prompt restricts LLM to SELECT-only queries
- **Code-level:** Whitelist validation rejects anything that isn't SELECT or WITH (CTE)
- **Keyword blocking:** Word-boundary regex blocks DROP, DELETE, INSERT, UPDATE, ALTER, TRUNCATE, EXEC, GRANT, REVOKE
- **Row limits:** Results capped at 1,000 rows to prevent overload
- **Timeout:** 30-second execution limit prevents runaway queries
- **SQL cleaning:** Strips LLM commentary, code fences, and preamble text from output
- **CORS:** API configured with cross-origin protection

---

## 🛠️ Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| Frontend | Next.js + TypeScript + Tailwind | Modern React framework, type safety, utility-first styling |
| Backend API | FastAPI | Async Python, auto-generated docs, Pydantic validation |
| LLM Abstraction | LangChain | Unified interface across 5+ providers |
| Schema Reflection | SQLAlchemy | Database-agnostic, automatic relationship discovery |
| Database | SQLite | Serverless, zero-config, file-based |
| Data Processing | pandas | Column metadata, type inference |
| Cloud LLM | Groq | Sub-2-second inference, free tier |
| Local LLM | Ollama | Private, offline, no API key needed |

---

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- Node.js 18+
- [Ollama](https://ollama.com/download) (optional — for free local models)

### Backend Setup

```bash
cd backend

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure API key
cp .env.example .env
# Edit .env — add at minimum: GROQ_API_KEY=your_key_here

# Start the API
python -m uvicorn api:app --reload --port 8000
```

API docs available at `http://localhost:8000/docs`

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Start the dev server
npm run dev
```

Open `http://localhost:3000` and start asking questions.

### Local Model Setup (Optional)

```bash
# Install Ollama, then pull a model
ollama pull mistral

# Start Ollama server
ollama serve
```

Select `mistral` from the model dropdown — free, private, no API key needed.

---

## 📁 Project Structure

```
QueryGenie/
├── backend/
│   ├── api.py                  # FastAPI endpoints
│   ├── src/
│   │   ├── schema_extractor.py # Database schema reflection
│   │   ├── llm_engine.py       # Multi-provider LLM abstraction
│   │   ├── query_executor.py   # Safe SQL execution
│   │   ├── visualizer.py       # Chart type detection
│   │   ├── example_generator.py# Smart example questions
│   │   └── utils.py            # CSV-to-SQLite conversion
│   ├── data/
│   │   └── chinook.db          # Demo database (music store)
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── app/
│   │   ├── page.tsx            # Main chat interface
│   │   ├── layout.tsx          # Root layout
│   │   └── globals.css         # Global styles
│   ├── package.json
│   └── tsconfig.json
├── assets/                     # Screenshots for README
├── README.md
└── LICENSE
```

---

## 🔌 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/models` | List available LLM models |
| GET | `/schema` | Get current database schema |
| GET | `/examples` | Get example questions for current database |
| POST | `/query` | Generate SQL from question and execute |
| POST | `/explain` | Explain a SQL query in plain English |
| POST | `/upload` | Upload a .sqlite, .db, or .csv file |
| POST | `/reset` | Reset to demo Chinook database |

---

## 🧠 Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Next.js + FastAPI over Streamlit | Production-grade UI with proper API separation. Streamlit limits customization and deployment flexibility |
| SQLAlchemy reflection over raw SQL | Database-agnostic — same code for SQLite, PostgreSQL, MySQL |
| Text schema format over JSON | LLMs generate better SQL with structured text (DIN-SQL research) |
| Temperature 0.0 | SQL generation is deterministic — precision over creativity |
| Few-shot prompting (3 examples) | 15-25% accuracy improvement over zero-shot on Text-to-SQL benchmarks |
| Defense-in-depth security | Each layer validates independently — never trust upstream |
| Groq for deployment | Sub-2-second inference vs 15-30s with local models. Critical for demo UX |
| Heuristic examples over LLM-generated | Zero latency, zero cost, deterministic, guaranteed schema-valid |
| LangChain as thin abstraction only | Unified model interface without framework lock-in |

---

## 🗺️ Roadmap

- [x] Multi-provider LLM support (OpenAI, Anthropic, Google, Groq, Ollama)
- [x] Full-stack architecture (Next.js + FastAPI)
- [x] CSV upload with auto-conversion
- [x] Query explanation with structured steps
- [x] Smart example questions
- [x] Schema viewer
- [x] Query history export
- [ ] Auto-retry with rephrased prompt on SQL failure
- [ ] Interactive chart visualization (Recharts)
- [ ] Multi-database support (PostgreSQL, MySQL)
- [ ] Query caching for repeated questions
- [ ] Conversational follow-up queries

---

## 👨‍💻 Author

**Nithish Kumar Reddy Kundam**
Master of Data Science and Decisions — UNSW Sydney

[![LinkedIn](https://img.shields.io/badge/LinkedIn-Connect-blue?style=flat&logo=linkedin)](https://linkedin.com/in/nithish-reddy-a35626279)
[![GitHub](https://img.shields.io/badge/GitHub-Follow-black?style=flat&logo=github)](https://github.com/Nithish130603)

---

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.