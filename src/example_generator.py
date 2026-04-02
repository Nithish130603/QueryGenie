"""
Example Question Generator
---------------------------
Generates contextually relevant example questions based on
database schema analysis.

Two modes:
1. Curated examples for known databases (Chinook)
2. Auto-generated examples from schema heuristics for unknown databases

Why heuristics over LLM?
- Zero latency (loads instantly with the page)
- Zero cost (no API calls)
- Guaranteed schema-valid questions
- Deterministic (same schema always gets same examples)
"""

from src.schema_extractor import SchemaExtractor


# ---- Curated examples for known databases ----
# These are hand-picked to showcase different SQL capabilities

CHINOOK_EXAMPLES = [
    {
        "question": "How many tracks are there in the database?",
        "category": "Simple Count",
    },
    {
        "question": "What are the top 5 genres by number of tracks?",
        "category": "Aggregation",
    },
    {
        "question": "Show me all albums by AC/DC",
        "category": "JOIN + Filter",
    },
    {
        "question": "Which customer has spent the most money?",
        "category": "Multi-table JOIN",
    },
    {
        "question": "What is the average track length in minutes by genre?",
        "category": "Aggregation + Math",
    },
    {
        "question": "How many customers are there in each country?",
        "category": "GROUP BY",
    },
    {
        "question": "What are the top 10 longest tracks?",
        "category": "ORDER BY + LIMIT",
    },
    {
        "question": "Which employee has supported the most customers?",
        "category": "Complex JOIN",
    },
]


def is_known_database(schema_text: str) -> str | None:
    """
    Check if the schema matches a known database.

    Why detect known databases?
        Curated examples are always better than auto-generated ones.
        If we recognize the database, we serve hand-crafted examples
        that showcase a variety of SQL patterns (COUNT, JOIN, GROUP BY,
        ORDER BY, subqueries).

    Returns:
        Database identifier string if recognized, None otherwise.
    """
    # Simple heuristic: check for signature tables
    if "Track" in schema_text and "Artist" in schema_text and "Invoice" in schema_text:
        return "chinook"
    return None


def generate_examples_from_schema(extractor: SchemaExtractor) -> list[dict]:
    """
    Auto-generate example questions from schema analysis.

    This is the core heuristic engine. It analyzes tables, columns,
    types, and relationships to produce relevant questions.

    The strategy:
    1. Generate a simple count for the first table
    2. Look for text + numeric column pairs → aggregation questions
    3. Look for foreign keys → JOIN questions
    4. Look for columns suggesting ranking → top N questions

    Why return category labels?
        Showing "Simple Count" or "JOIN + Filter" next to each example
        educates the user about what types of questions the app handles.
        It also shows recruiters you understand SQL taxonomy.
    """
    schema = extractor.get_full_schema()
    table_names = extractor.get_table_names()
    examples = []

    if not table_names:
        return examples

    # Strategy 1: Simple count for the first table
    first_table = table_names[0]
    examples.append({
        "question": f"How many records are in the {first_table} table?",
        "category": "Simple Count",
    })

    for table_name, table_info in schema.items():
        columns = table_info["columns"]
        foreign_keys = table_info["foreign_keys"]

        # Classify columns
        text_cols = []
        numeric_cols = []
        for col in columns:
            col_type = str(col["type"]).upper()
            if col["primary_key"]:
                continue
            # Skip ID-like columns — not useful for aggregation
            col_name_lower = col["name"].lower()
            if col_name_lower.endswith("id") or col_name_lower == "id":
                continue
            if any(t in col_type for t in ["VARCHAR", "TEXT", "CHAR", "NVARCHAR"]):
                text_cols.append(col["name"])
            elif any(t in col_type for t in ["INT", "REAL", "FLOAT", "DECIMAL",
                                              "NUMERIC", "DOUBLE"]):
                numeric_cols.append(col["name"])

        # Strategy 2: Text column exists → GROUP BY count
        if text_cols:
            col = text_cols[0]
            examples.append({
                "question": f"What are the different {col} values in {table_name} and how many of each?",
                "category": "GROUP BY",
            })

        # Strategy 3: Numeric column exists → aggregation
        if numeric_cols:
            col = numeric_cols[0]
            examples.append({
                "question": f"What is the average {col} in {table_name}?",
                "category": "Aggregation",
            })

        # Strategy 4: Numeric column → Top N
        if numeric_cols:
            col = numeric_cols[0]
            display_col = text_cols[0] if text_cols else f"{table_name} records"
            examples.append({
                "question": f"What are the top 5 {table_name} by highest {col}?",
                "category": "ORDER BY + LIMIT",
            })

        # Strategy 5: Foreign key → JOIN question
        if foreign_keys:
            fk = foreign_keys[0]
            examples.append({
                "question": f"Show me {table_name} data with their related {fk['to_table']} information",
                "category": "JOIN",
            })

        # Stop after we have enough — too many examples is overwhelming
        if len(examples) >= 8:
            break

    # Deduplicate by question text
    seen = set()
    unique_examples = []
    for ex in examples:
        if ex["question"] not in seen:
            seen.add(ex["question"])
            unique_examples.append(ex)

    return unique_examples[:8]  # cap at 8


def get_examples(schema_text: str, extractor: SchemaExtractor) -> list[dict]:
    """
    Main entry point — returns appropriate examples for the current database.

    Checks for known databases first (curated examples),
    falls back to auto-generation for unknown schemas.

    Args:
        schema_text: Formatted schema string (for known DB detection)
        extractor: SchemaExtractor instance (for auto-generation)

    Returns:
        List of dicts with 'question' and 'category' keys
    """
    known = is_known_database(schema_text)
    if known == "chinook":
        return CHINOOK_EXAMPLES
    return generate_examples_from_schema(extractor)