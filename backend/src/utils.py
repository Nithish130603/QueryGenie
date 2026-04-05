"""
Utility Module
--------------
Helper functions used across the application.
Currently handles CSV-to-SQLite conversion for user uploads.
"""

import sqlite3
import pandas as pd
import os


def csv_to_sqlite(csv_path: str, db_path: str, table_name: str = "uploaded_data") -> str:
    """
    Convert a CSV file to a SQLite database.

    Why do we need this?
        We promised users can upload their own data. CSV is the most
        common format people have. But our pipeline works with SQLite
        databases (for schema extraction and SQL execution). This
        bridge function converts any CSV into a queryable SQLite DB.

    Why SQLite as the intermediate format (not just query the CSV directly)?
        1. SQL queries need a database engine — you can't run JOINs on a CSV
        2. SQLAlchemy reflection only works on databases
        3. SQLite is serverless (just a file) — no setup needed
        4. pandas read_csv + to_sql makes this conversion trivial

    Args:
        csv_path: Path to the uploaded CSV file
        db_path: Where to save the SQLite database
        table_name: Name for the table (default: "uploaded_data")

    Returns:
        Path to the created SQLite database
    """
    # Read CSV with pandas (handles encoding, delimiters automatically)
    df = pd.read_csv(csv_path)

    # Clean column names — remove spaces, special chars
    # SQL column names with spaces cause issues
    df.columns = [
        col.strip().replace(" ", "_").replace(".", "_").replace("-", "_")
        for col in df.columns
    ]

    # Write to SQLite
    conn = sqlite3.connect(db_path)
    try:
        df.to_sql(table_name, conn, if_exists="replace", index=False)
    finally:
        conn.close()

    return db_path