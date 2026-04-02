"""
LLM Engine Module
-----------------
Handles all LLM interactions for SQL generation. Supports multiple
model providers (OpenAI, Anthropic, Local via Ollama) through a
unified interface using LangChain.

Design decisions:
- LangChain used ONLY as a model abstraction layer (not for chains/agents)
- Prompt engineering logic kept in our own code for full control
- System prompt uses role prompting + few-shot examples + strict output rules
- Safety: only SELECT queries allowed (no mutations)
"""

import re
from langchain_ollama import ChatOllama
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import SystemMessage, HumanMessage


# ---- Supported model configurations ----
# Each entry maps a model key to its provider class and model name.
# Adding a new model = adding one entry here. Zero code changes elsewhere.

MODEL_REGISTRY = {
    # API Models (require API keys)
    "gpt-4o-mini": {
        "provider": ChatOpenAI,
        "model_name": "gpt-4o-mini",
        "description": "Fast, affordable OpenAI model. Good for most queries.",
    },
    "gpt-4o": {
        "provider": ChatOpenAI,
        "model_name": "gpt-4o",
        "description": "Most capable OpenAI model. Best for complex queries.",
    },
    "claude-sonnet": {
        "provider": ChatAnthropic,
        "model_name": "claude-sonnet-4-20250514",
        "description": "Anthropic's balanced model. Great SQL generation.",
    },
    "gemini-flash": {
        "provider": ChatGoogleGenerativeAI,
        "model_name": "gemini-2.0-flash",
        "description": "Google's fast, efficient model. Generous free tier.",
    },
    "gemini-1.5-flash": {
        "provider": ChatGoogleGenerativeAI,
        "model_name": "gemini-1.5-flash",
        "description": "Google's Gemini 1.5 Flash. Separate free tier quota.",
    },
    # Local Models (require Ollama running locally)
    "mistral": {
        "provider": ChatOllama,
        "model_name": "mistral",
        "description": "Local model. Free, private, no API key needed.",
    },
    "llama3": {
        "provider": ChatOllama,
        "model_name": "llama3",
        "description": "Meta's local model. Free, private, good accuracy.",
    },
}


def _build_system_prompt(schema_text: str) -> str:
    """
    Construct the system prompt that defines the LLM's behavior.

    This is the most critical piece of the entire application.
    Every line exists for a reason:

    - Role definition: improves task-specific performance (role prompting)
    - Schema injection: gives the model complete database awareness
    - Output rules: ensures clean, parseable SQL output
    - Safety rules: prevents destructive operations (security by design)
    - Few-shot examples: improves accuracy by 15-25% vs zero-shot

    Args:
        schema_text: Formatted schema from SchemaExtractor

    Returns:
        Complete system prompt string
    """
    return f"""You are an expert SQL analyst. Your job is to convert natural language questions into accurate, efficient SQL queries.

## DATABASE SCHEMA
{schema_text}

## RULES (STRICT — follow every one)
1. Return ONLY the SQL query. No explanations, no markdown, no code fences, no preamble.
2. Only generate SELECT statements. NEVER use INSERT, UPDATE, DELETE, DROP, ALTER, or any data-modifying operation.
3. Use the exact table and column names from the schema above. Never guess or hallucinate names.
4. When joining tables, always use the foreign key relationships defined in the schema.
5. Use aliases for readability when joining multiple tables (e.g., SELECT a.Name FROM Artist a).
6. If the question is ambiguous, make a reasonable assumption and write the query.
7. If the question cannot be answered with the given schema, respond with exactly: CANNOT_ANSWER
8. Always end your SQL with a semicolon.
9. For "top N" questions, always use LIMIT.
10. Prefer explicit JOIN syntax over implicit joins (WHERE-based).

## EXAMPLES

Question: "How many tracks are there?"
SQL: SELECT COUNT(*) AS total_tracks FROM Track;

Question: "Show me the top 5 customers who spent the most"
SQL: SELECT c.FirstName, c.LastName, SUM(i.Total) AS total_spent FROM Customer c JOIN Invoice i ON c.CustomerId = i.CustomerId GROUP BY c.CustomerId ORDER BY total_spent DESC LIMIT 5;

Question: "Which genre has the most tracks?"
SQL: SELECT g.Name AS genre, COUNT(t.TrackId) AS track_count FROM Genre g JOIN Track t ON g.GenreId = t.GenreId GROUP BY g.GenreId ORDER BY track_count DESC LIMIT 1;
"""


def get_available_models() -> dict:
    """
    Return the registry of all supported models.

    Why a registry pattern?
        Makes it trivial to add new models without touching any
        other code. The UI reads this registry to populate the
        model dropdown. This is the Open/Closed Principle in action —
        open for extension (new models), closed for modification
        (existing code doesn't change).
    """
    return {
        key: info["description"]
        for key, info in MODEL_REGISTRY.items()
    }


def _create_llm(model_key: str, temperature: float = 0.0):
    """
    Instantiate the appropriate LLM based on model key.

    Why temperature = 0.0?
        SQL generation is a deterministic task — there's usually
        one correct query for a given question. We want the model
        to be precise, not creative. Temperature 0 gives us the
        most likely (and usually most correct) output every time.

        In interviews, this shows you understand the difference
        between creative tasks (high temp) and precision tasks (low temp).

    Args:
        model_key: Key from MODEL_REGISTRY
        temperature: Controls randomness. 0.0 = deterministic.

    Returns:
        A LangChain chat model instance

    Raises:
        ValueError: If model_key not found in registry
    """
    if model_key not in MODEL_REGISTRY:
        raise ValueError(
            f"Unknown model: {model_key}. "
            f"Available: {list(MODEL_REGISTRY.keys())}"
        )

    config = MODEL_REGISTRY[model_key]
    provider = config["provider"]
    model_name = config["model_name"]

    # Ollama (local) doesn't need API keys
    # API models pick up keys from environment variables automatically
    if provider == ChatOllama:
        return provider(model=model_name, temperature=temperature)
    else:
        return provider(model=model_name, temperature=temperature)


def generate_sql(
    question: str,
    schema_text: str,
    model_key: str = "gpt-4o-mini"
) -> dict:
    """
    Generate a SQL query from a natural language question.

    This is the main entry point for SQL generation. It:
    1. Builds a schema-aware system prompt
    2. Creates the appropriate LLM instance
    3. Sends the question and gets a SQL response
    4. Cleans and validates the response

    Args:
        question: User's natural language question
        schema_text: Formatted database schema
        model_key: Which model to use (from MODEL_REGISTRY)

    Returns:
        dict with:
            - sql: The generated SQL query (or error message)
            - model: Which model was used
            - success: Whether generation succeeded
            - error: Error message if failed, None otherwise

    Why return a dict instead of just the SQL string?
        Structured returns make error handling much cleaner downstream.
        The UI can check 'success' before trying to execute the query,
        and display 'error' to the user if something went wrong.
        This is a defensive programming pattern.
    """
    try:
        # Step 1: Build the prompt
        system_prompt = _build_system_prompt(schema_text)

        # Step 2: Create the LLM
        llm = _create_llm(model_key)

        # Step 3: Send to LLM
        # We use the messages API (system + human) rather than a single
        # string prompt because it gives the model clearer role separation.
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Question: {question}"),
        ]

        response = llm.invoke(messages)

        # Step 4: Extract and clean the SQL
        raw_output = response.content.strip()
        cleaned_sql = _clean_sql_output(raw_output)

        # Step 5: Basic validation
        if cleaned_sql == "CANNOT_ANSWER":
            return {
                "sql": None,
                "model": model_key,
                "success": False,
                "error": "This question cannot be answered with the available database schema.",
            }

        if not _is_safe_sql(cleaned_sql):
            return {
                "sql": None,
                "model": model_key,
                "success": False,
                "error": "Generated query was blocked for safety reasons (non-SELECT operation detected).",
            }

        return {
            "sql": cleaned_sql,
            "model": model_key,
            "success": True,
            "error": None,
        }

    except Exception as e:
        return {
            "sql": None,
            "model": model_key,
            "success": False,
            "error": f"LLM generation failed: {str(e)}",
        }


def _clean_sql_output(raw: str) -> str:
    """
    Clean the LLM's raw output to extract just the SQL.

    Why is this necessary?
        Even with strict instructions, LLMs sometimes wrap SQL in
        markdown code blocks (```sql ... ```) or add explanatory text.
        This function strips all of that reliably.

    The cleaning order matters:
        1. Remove code fences first (most common wrapper)
        2. Strip whitespace
        3. Remove trailing semicolons then re-add one
           (normalizes inconsistent semicolon usage)
    """
    # Remove markdown code blocks if present
    cleaned = re.sub(r"```sql\s*", "", raw)
    cleaned = re.sub(r"```\s*", "", cleaned)

    # Strip whitespace
    cleaned = cleaned.strip()

    # Strip "SQL:" prefix some models (e.g. Mistral) add despite instructions
    cleaned = re.sub(r"^SQL:\s*", "", cleaned, flags=re.IGNORECASE)

    # Normalize semicolons — ensure exactly one at the end
    cleaned = cleaned.rstrip(";").strip() + ";"

    return cleaned


def _is_safe_sql(sql: str) -> bool:
    """
    Check if the generated SQL is safe to execute.

    This is a CRITICAL security layer. We whitelist SELECT and
    block everything else. This is defense-in-depth — even though
    our prompt says "only SELECT", we don't trust the LLM to
    always comply.

    Why not just check for dangerous keywords?
        A blocklist approach (checking for DROP, DELETE, etc.) can
        be bypassed with creative SQL. A whitelist approach (only
        allowing SELECT) is much harder to circumvent.

    Interview point:
        "I implemented defense-in-depth for SQL safety. The prompt
        restricts the LLM to SELECT-only, but I also validate the
        output server-side because you should never trust LLM output
        for security-critical decisions."
    """
    # Normalize for checking
    sql_upper = sql.upper().strip()

    # Must start with SELECT or WITH (for CTEs)
    if not (sql_upper.startswith("SELECT") or sql_upper.startswith("WITH")):
        return False

    # Block dangerous keywords anywhere in the query
    dangerous_keywords = [
        "INSERT", "UPDATE", "DELETE", "DROP", "ALTER",
        "CREATE", "TRUNCATE", "EXEC", "EXECUTE", "GRANT", "REVOKE"
    ]
    for keyword in dangerous_keywords:
        # Use word boundary matching to avoid false positives
        # e.g., "SELECTED" should not match "SELECT" + "ED"
        if re.search(rf"\b{keyword}\b", sql_upper):
            return False

    return True



def explain_sql(sql: str, model_key: str = "mistral") -> dict:
    """
    Generate a plain English explanation of a SQL query.

    This serves a different purpose than SQL generation — here we're
    translating FROM SQL TO English (the reverse direction).

    Why a separate function instead of adding to generate_sql?
        Single responsibility. generate_sql converts questions to SQL.
        explain_sql converts SQL to explanations. Different prompts,
        different use cases, different error handling needs.

    Why lazy-loaded (only called on user click)?
        Not every user wants an explanation. Calling the LLM for every
        query would double latency and cost. This is an on-demand feature.

    Args:
        sql: The SQL query to explain
        model_key: Which model to use

    Returns:
        dict with success, explanation, and error fields
    """
    try:
        llm = _create_llm(model_key, temperature=0.0)

        messages = [
            SystemMessage(content="""You are a SQL tutor. Explain the given SQL query in simple,
clear English that a beginner could understand.

## RULES
1. Break the query down step by step.
2. Explain what each clause does (SELECT, FROM, JOIN, WHERE, GROUP BY, ORDER BY, LIMIT).
3. Describe the final result the query produces.
4. Use simple language — avoid jargon.
5. Keep it concise — aim for 3-6 bullet points.
6. Format your response as a short paragraph followed by bullet points."""),
            HumanMessage(content=f"Explain this SQL query:\n\n{sql}"),
        ]

        response = llm.invoke(messages)
        return {
            "success": True,
            "explanation": response.content.strip(),
            "error": None,
        }

    except Exception as e:
        return {
            "success": False,
            "explanation": None,
            "error": f"Explanation failed: {str(e)}",
        }


# ---- Quick test ----
if __name__ == "__main__":
    from src.schema_extractor import SchemaExtractor

    # Extract schema
    extractor = SchemaExtractor("data/chinook.db")
    schema = extractor.format_schema_for_llm()

    # Test with local Mistral model (no API key needed)
    result = generate_sql(
        question="What are the top 5 longest tracks?",
        schema_text=schema,
        model_key="mistral"
    )
    print(f"Success: {result['success']}")
    print(f"SQL: {result['sql']}")
    if result["error"]:
        print(f"Error: {result['error']}")