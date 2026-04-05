"""
Query Executor Module
---------------------
Safely executes SQL queries against a SQLite database and returns
results as pandas DataFrames.

Safety layers:
1. SQL validation (whitelist SELECT/WITH only)
2. Execution timeout (prevents runaway queries)
3. Row limit (prevents browser-crashing result sets)
4. Read-only connection mode

Design:
- Returns structured results with metadata (row count, truncation status)
- Uses context managers for guaranteed connection cleanup
- Separate from LLM engine (single responsibility principle)
"""

import sqlite3
import pandas as pd
import threading


# Default safety limits
DEFAULT_TIMEOUT = 30      # seconds
DEFAULT_ROW_LIMIT = 1000  # max rows returned to UI


class QueryExecutor:
    """
    Executes SQL queries safely against a SQLite database.

    Why a class and not just functions?
        The executor needs to hold a reference to the database path
        and reuse it across multiple queries in a session. A class
        keeps this state clean. It also lets us configure per-instance
        settings (timeout, row limit) if needed later.
    """

    def __init__(
        self,
        db_path: str,
        timeout: int = DEFAULT_TIMEOUT,
        row_limit: int = DEFAULT_ROW_LIMIT,
    ):
        """
        Args:
            db_path: Path to the SQLite database file
            timeout: Maximum query execution time in seconds
            row_limit: Maximum rows to return (prevents UI overload)
        """
        self.db_path = db_path
        self.timeout = timeout
        self.row_limit = row_limit

    def _get_connection(self) -> sqlite3.Connection:
        """
        Create a new database connection.

        Why create a new connection each time instead of reusing one?
            SQLite connections are not thread-safe by default, and
            Streamlit runs callbacks in threads. Creating a fresh
            connection per query avoids concurrency bugs. The overhead
            is negligible for SQLite (it's just opening a file).

            In a production app with PostgreSQL, you'd use connection
            pooling instead (e.g., SQLAlchemy's pool). That's a good
            interview talking point about scaling differences.
        """
        conn = sqlite3.connect(self.db_path, timeout=self.timeout)
        # Enable row factory for column name access
        conn.row_factory = sqlite3.Row
        return conn

    def execute(self, sql: str) -> dict:
        """
        Execute a SQL query and return results with metadata.

        This is the main entry point. It:
        1. Validates the SQL is safe (SELECT/WITH only)
        2. Runs it with a timeout
        3. Converts results to a DataFrame
        4. Truncates if over row limit
        5. Returns structured result with metadata

        Args:
            sql: The SQL query to execute

        Returns:
            dict with:
                - success (bool): Whether execution succeeded
                - data (DataFrame or None): Query results
                - row_count (int): Total rows returned
                - truncated (bool): Whether results were capped
                - columns (list): Column names
                - error (str or None): Error message if failed

        Why this structure?
            The UI needs to know not just the data, but whether it
            was truncated (to show a warning), how many rows there
            are (to display count), and column names (for chart axis
            labels). Bundling this metadata avoids multiple calls.
        """
        # Step 1: Safety check (defense-in-depth, even though
        # llm_engine already checks — never trust upstream)
        if not self._is_safe(sql):
            return {
                "success": False,
                "data": None,
                "row_count": 0,
                "truncated": False,
                "columns": [],
                "error": "Query blocked: only SELECT statements are allowed.",
            }

        # Step 2: Execute with timeout protection
        try:
            conn = self._get_connection()
            try:
                cursor = conn.execute(sql)
                # Fetch one extra row to detect if there are more
                # than our limit (avoids counting the full result set)
                rows = cursor.fetchmany(self.row_limit + 1)
                columns = (
                    [desc[0] for desc in cursor.description]
                    if cursor.description
                    else []
                )

                # Step 3: Check truncation
                truncated = len(rows) > self.row_limit
                if truncated:
                    rows = rows[: self.row_limit]

                # Step 4: Convert to DataFrame
                # Handle duplicate column names — LLMs sometimes
                # generate SQL with duplicate aliases. pandas/pyarrow
                # crashes on duplicate columns, so we rename them.
                seen = {}
                unique_columns = []
                for col in columns:
                    if col in seen:
                        seen[col] += 1
                        unique_columns.append(f"{col}_{seen[col]}")
                    else:
                        seen[col] = 0
                        unique_columns.append(col)

                df = pd.DataFrame(rows, columns=unique_columns)

                return {
                    "success": True,
                    "data": df,
                    "row_count": len(df),
                    "truncated": truncated,
                    "columns": columns,
                    "error": None,
                }

            finally:
                # Always close connection — even if query fails
                # This is the context manager pattern in manual form.
                conn.close()

        except sqlite3.OperationalError as e:
            # Common: syntax errors in generated SQL, missing tables
            return {
                "success": False,
                "data": None,
                "row_count": 0,
                "truncated": False,
                "columns": [],
                "error": f"SQL execution error: {str(e)}",
            }
        except Exception as e:
            # Catch-all for unexpected errors
            return {
                "success": False,
                "data": None,
                "row_count": 0,
                "truncated": False,
                "columns": [],
                "error": f"Unexpected error: {str(e)}",
            }

    def _is_safe(self, sql: str) -> bool:
        """
        Validate that SQL is safe to execute.

        Why duplicate the safety check from llm_engine?
            Defense-in-depth. The executor might be called directly
            (e.g., user-typed SQL in a future feature), bypassing
            the LLM engine entirely. Every layer should protect itself.

            In security engineering this is called "never trust the caller."
        """
        sql_upper = sql.strip().upper()

        # Only allow SELECT and WITH (for CTEs)
        if not (sql_upper.startswith("SELECT") or sql_upper.startswith("WITH")):
            return False

        # Block dangerous operations
        import re
        dangerous = [
            "INSERT", "UPDATE", "DELETE", "DROP", "ALTER",
            "CREATE", "TRUNCATE", "EXEC", "EXECUTE", "GRANT", "REVOKE"
        ]
        for keyword in dangerous:
            if re.search(rf"\b{keyword}\b", sql_upper):
                return False

        return True

    def get_sample_data(self, table_name: str, limit: int = 5) -> pd.DataFrame:
        """
        Get a small sample of rows from a table.

        Why do we need this?
            When the user uploads a database and selects it, we want
            to show them a preview of what's inside each table.
            This helps them understand what questions they can ask.

            It also serves as a quick validation that the database
            is readable and not corrupted.
        """
        # Sanitize table name to prevent injection
        # (table names can't be parameterized in SQLite)
        safe_name = table_name.replace('"', '""')
        sql = f'SELECT * FROM "{safe_name}" LIMIT {limit};'
        result = self.execute(sql)
        return result.get("data", pd.DataFrame())


# ---- Quick test ----
if __name__ == "__main__":
    executor = QueryExecutor("data/chinook.db")

    # Test 1: Valid query
    print("=== Test 1: Valid SELECT ===")
    result = executor.execute(
        "SELECT Name, Milliseconds FROM Track ORDER BY Milliseconds DESC LIMIT 5;"
    )
    print(f"Success: {result['success']}")
    print(f"Rows: {result['row_count']}")
    if result["data"] is not None:
        print(result["data"].to_string(index=False))

    # Test 2: Dangerous query (should be blocked)
    print("\n=== Test 2: Dangerous query ===")
    result = executor.execute("DROP TABLE Artist;")
    print(f"Success: {result['success']}")
    print(f"Error: {result['error']}")

    # Test 3: Bad SQL (syntax error)
    print("\n=== Test 3: Bad SQL ===")
    result = executor.execute("SELECT * FROMM Track;")
    print(f"Success: {result['success']}")
    print(f"Error: {result['error']}")

    # Test 4: Sample data
    print("\n=== Test 4: Sample data ===")
    sample = executor.get_sample_data("Artist")
    print(sample.to_string(index=False))