"""
Schema Extractor Module
-----------------------
Connects to a SQLite database and extracts its complete structure
(tables, columns, types, primary keys, foreign keys) using SQLAlchemy's
reflection API. Outputs a clean text description for LLM consumption.

Why SQLAlchemy reflection?
- Database-agnostic: same code works for SQLite, PostgreSQL, MySQL
- Automatic discovery: no need to hardcode table names
- Relationship mapping: foreign keys extracted automatically
"""

from sqlalchemy import create_engine, inspect, MetaData


class SchemaExtractor:
    """
    Extracts and formats database schema information for LLM-based
    SQL generation.
    
    The formatted output is designed to be injected into LLM prompts,
    giving the model complete awareness of the database structure
    before it generates SQL queries.
    """

    def __init__(self, db_path: str):
        """
        Initialize the extractor with a path to a SQLite database.

        Args:
            db_path: Path to the .db or .sqlite file

        Why sqlite:/// prefix?
            SQLAlchemy uses URI-style connection strings. The three slashes
            in sqlite:/// indicate a relative path. Four slashes (sqlite:////)
            would mean an absolute path. This is a common interview gotcha.
        """
        self.engine = create_engine(f"sqlite:///{db_path}")
        self.inspector = inspect(self.engine)
        self.metadata = MetaData()
        self.metadata.reflect(bind=self.engine)

    def get_table_names(self) -> list[str]:
        """Return a list of all table names in the database."""
        return self.inspector.get_table_names()

    def get_table_info(self, table_name: str) -> dict:
        """
        Extract complete information about a single table.

        Returns a dict with:
            - columns: list of {name, type, nullable, primary_key}
            - foreign_keys: list of {from_column, to_table, to_column}

        Why track nullable?
            Knowing whether a column allows NULLs helps the LLM decide
            whether to use COALESCE or handle missing data in queries.
        """
        columns = []
        for col in self.inspector.get_columns(table_name):
            columns.append({
                "name": col["name"],
                "type": str(col["type"]),
                "nullable": col.get("nullable", True),
                "primary_key": col.get("autoincrement", False) or col["name"]
                in [
                    pk
                    for pk in self.inspector.get_pk_constraint(table_name).get(
                        "constrained_columns", []
                    )
                ],
            })

        foreign_keys = []
        for fk in self.inspector.get_foreign_keys(table_name):
            for i, col in enumerate(fk["constrained_columns"]):
                foreign_keys.append({
                    "from_column": col,
                    "to_table": fk["referred_table"],
                    "to_column": fk["referred_columns"][i],
                })

        return {"columns": columns, "foreign_keys": foreign_keys}

    def get_full_schema(self) -> dict:
        """
        Extract schema information for ALL tables in the database.

        Returns a dict mapping table_name -> table_info
        """
        schema = {}
        for table_name in self.get_table_names():
            schema[table_name] = self.get_table_info(table_name)
        return schema

    def format_schema_for_llm(self) -> str:
        """
        Convert the raw schema into a clean, readable text format
        optimized for LLM consumption.

        Why text over JSON?
            LLMs generate better SQL when the schema is presented as
            structured natural text. Research (DIN-SQL, DAIL-SQL) shows
            this format reduces hallucinated column names and improves
            JOIN accuracy. JSON adds token overhead without improving
            comprehension for the model.

        Returns:
            A formatted string describing all tables, columns, types,
            primary keys, and foreign key relationships.
        """
        schema = self.get_full_schema()
        lines = []
        lines.append("=== DATABASE SCHEMA ===\n")

        for table_name, table_info in schema.items():
            lines.append(f"Table: {table_name}")
            lines.append("-" * (len(table_name) + 7))

            # Format columns
            lines.append("  Columns:")
            for col in table_info["columns"]:
                pk_marker = " [PRIMARY KEY]" if col["primary_key"] else ""
                null_marker = " (nullable)" if col["nullable"] else " (not null)"
                lines.append(
                    f"    - {col['name']}: {col['type']}{pk_marker}{null_marker}"
                )

            # Format foreign keys (relationships)
            if table_info["foreign_keys"]:
                lines.append("  Relationships:")
                for fk in table_info["foreign_keys"]:
                    lines.append(
                        f"    - {fk['from_column']} -> "
                        f"{fk['to_table']}.{fk['to_column']}"
                    )

            lines.append("")  # blank line between tables

        return "\n".join(lines)


# ---- Quick test ----
if __name__ == "__main__":
    extractor = SchemaExtractor("data/chinook.db")
    print(extractor.format_schema_for_llm())