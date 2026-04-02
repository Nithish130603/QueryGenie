"""
Visualizer Module
-----------------
Automatically generates appropriate charts from query results.

Uses heuristic analysis of DataFrame structure (column types, 
cardinality, shape) to select the best visualization type.

Chart selection logic:
- Single value result    → Metric display (big number)
- 1 categorical + 1 numeric → Bar chart (+ pie if ≤ 6 categories)
- Date/time + numeric    → Line chart
- Multiple numerics      → Table only (too ambiguous)

Why Plotly over Matplotlib?
- Interactive (hover, zoom, pan) — better UX in web apps
- Native Streamlit integration via st.plotly_chart()
- Consistent theming with dark/light modes
"""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


def analyze_columns(df: pd.DataFrame) -> dict:
    """
    Analyze DataFrame columns to determine their types and roles.

    This is the foundation of smart chart selection. We classify
    each column as categorical, numeric, or temporal, then count
    how many of each type exist.

    Why not just use df.dtypes?
        pandas dtype detection isn't always reliable — a column of
        numbers stored as strings will show as 'object'. We do our
        own analysis: try to convert to numeric/datetime, and fall
        back to categorical if both fail.

        Also, a numeric column with very few unique values (like
        Pclass: 1, 2, 3) is better treated as categorical for
        visualization purposes. We handle this with cardinality checks.

    Returns:
        dict with:
            - categorical: list of categorical column names
            - numeric: list of numeric column names
            - temporal: list of date/time column names
            - shape: (rows, cols) of the DataFrame
    """
    categorical = []
    numeric = []
    temporal = []

    for col in df.columns:
        series = df[col]

        # Try datetime first
        if _is_temporal(series):
            temporal.append(col)
            continue

        # Check if numeric
        if _is_numeric(series):
            # But if very few unique values, treat as categorical
            # e.g., Pclass (1, 2, 3) is better as a category
            if series.nunique() <= 6 and series.nunique() < len(series) * 0.5:
                categorical.append(col)
            else:
                numeric.append(col)
            continue

        # Default: categorical
        categorical.append(col)

    return {
        "categorical": categorical,
        "numeric": numeric,
        "temporal": temporal,
        "shape": df.shape,
    }


def _is_numeric(series: pd.Series) -> bool:
    """Check if a series contains numeric data."""
    if pd.api.types.is_numeric_dtype(series):
        return True
    # Try converting string values to numbers
    try:
        pd.to_numeric(series.dropna())
        return True
    except (ValueError, TypeError):
        return False


def _is_temporal(series: pd.Series) -> bool:
    """
    Check if a series contains date/time data.

    Why check for numeric dtype first?
        pd.to_datetime() aggressively converts integers to timestamps
        (treating them as Unix epoch times). A column like [1297, 579]
        would be "successfully" converted to dates in 1970. We must
        exclude numeric types before attempting datetime conversion.
    """
    if pd.api.types.is_datetime64_any_dtype(series):
        return True
    # Don't try to convert numeric data to dates
    if pd.api.types.is_numeric_dtype(series):
        return False
    # Only try converting string values to dates
    try:
        converted = pd.to_datetime(series.dropna(), format="mixed")
        return converted.notna().sum() > len(series) * 0.5
    except (ValueError, TypeError):
        return False


def suggest_chart_type(df: pd.DataFrame) -> dict:
    """
    Analyze results and suggest the best visualization.

    This is the main decision engine. It looks at the column
    analysis and picks the most appropriate chart type.

    Decision tree:
    1. Single cell (1 row, 1 col) → metric
    2. Single row, multiple cols → metric (multiple values)
    3. Has temporal + numeric → line chart
    4. Has 1 categorical + 1 numeric → bar chart
    5. Has 1 categorical + 1 numeric, ≤ 6 categories → also offer pie
    6. Everything else → table only

    Returns:
        dict with:
            - chart_type: "metric" | "bar" | "line" | "pie" | "table"
            - x: column name for x-axis (if applicable)
            - y: column name for y-axis (if applicable)
            - title: suggested chart title
            - pie_eligible: bool (can also be shown as pie)
    """
    if df.empty:
        return {"chart_type": "table", "x": None, "y": None,
                "title": "No results", "pie_eligible": False}

    analysis = analyze_columns(df)
    rows, cols = analysis["shape"]

    # Case 1: Single value — show as big metric
    if rows == 1 and cols == 1:
        return {
            "chart_type": "metric",
            "x": None,
            "y": df.columns[0],
            "title": df.columns[0],
            "pie_eligible": False,
        }

    # Case 2: Single row, multiple columns — show as metrics
    if rows == 1:
        return {
            "chart_type": "metric",
            "x": None,
            "y": None,
            "title": "Query Result",
            "pie_eligible": False,
        }

    # Case 3: Temporal + numeric → line chart
    if analysis["temporal"] and analysis["numeric"]:
        return {
            "chart_type": "line",
            "x": analysis["temporal"][0],
            "y": analysis["numeric"][0],
            "title": f"{analysis['numeric'][0]} over time",
            "pie_eligible": False,
        }

    # Case 4: Categorical + numeric → bar chart
    if analysis["categorical"] and analysis["numeric"]:
        x_col = analysis["categorical"][0]
        y_col = analysis["numeric"][0]
        n_categories = df[x_col].nunique()

        return {
            "chart_type": "bar",
            "x": x_col,
            "y": y_col,
            "title": f"{y_col} by {x_col}",
            "pie_eligible": n_categories <= 6,
        }

    # Default: just show the table
    return {
        "chart_type": "table",
        "x": None,
        "y": None,
        "title": "Query Results",
        "pie_eligible": False,
    }


def create_chart(df: pd.DataFrame, suggestion: dict) -> go.Figure | None:
    """
    Create a Plotly chart based on the suggestion.

    Why return a Plotly Figure object instead of rendering directly?
        Separation of concerns. The visualizer decides WHAT to draw,
        the UI layer (app.py) decides WHERE and HOW to display it.
        This also makes the visualizer testable without Streamlit.

    Returns:
        A plotly Figure object, or None if chart_type is "table" or "metric"
    """
    chart_type = suggestion["chart_type"]

    if chart_type == "bar":
        fig = px.bar(
            df,
            x=suggestion["x"],
            y=suggestion["y"],
            title=suggestion["title"],
            text_auto=True,
        )
        fig.update_layout(
            xaxis_title=suggestion["x"],
            yaxis_title=suggestion["y"],
            showlegend=False,
        )
        return fig

    elif chart_type == "line":
        fig = px.line(
            df,
            x=suggestion["x"],
            y=suggestion["y"],
            title=suggestion["title"],
            markers=True,
        )
        fig.update_layout(
            xaxis_title=suggestion["x"],
            yaxis_title=suggestion["y"],
        )
        return fig

    elif chart_type == "pie":
        fig = px.pie(
            df,
            names=suggestion["x"],
            values=suggestion["y"],
            title=suggestion["title"],
        )
        return fig

    # metric and table types don't need a Plotly chart
    return None


def render_metric(df: pd.DataFrame, suggestion: dict):
    """
    Prepare metric display data for single-value results.

    Returns a list of dicts, each with 'label' and 'value',
    for the UI to render using st.metric().

    Why not render directly with Streamlit here?
        Keeping this module Streamlit-free means it can be
        tested independently and reused in other contexts
        (e.g., an API endpoint or CLI tool).
    """
    metrics = []
    if df.shape[0] == 1:
        for col in df.columns:
            value = df[col].iloc[0]
            # Format large numbers with commas
            if isinstance(value, (int, float)):
                if isinstance(value, float):
                    formatted = f"{value:,.2f}"
                else:
                    formatted = f"{value:,}"
            else:
                formatted = str(value)
            metrics.append({"label": col, "value": formatted})
    return metrics


# ---- Quick test ----
if __name__ == "__main__":
    # Test 1: Single value
    print("=== Test 1: Single value ===")
    df1 = pd.DataFrame({"total_tracks": [3503]})
    suggestion = suggest_chart_type(df1)
    print(f"Type: {suggestion['chart_type']}")
    print(f"Metrics: {render_metric(df1, suggestion)}")

    # Test 2: Categorical + numeric (bar chart)
    print("\n=== Test 2: Bar chart candidate ===")
    df2 = pd.DataFrame({
        "genre": ["Rock", "Latin", "Metal", "Jazz", "Blues"],
        "track_count": [1297, 579, 374, 130, 81],
    })
    suggestion = suggest_chart_type(df2)
    print(f"Type: {suggestion['chart_type']}, Pie eligible: {suggestion['pie_eligible']}")

    # Test 3: Many categories (bar only, not pie)
    print("\n=== Test 3: Many categories ===")
    df3 = pd.DataFrame({
        "customer": [f"Customer_{i}" for i in range(20)],
        "total_spent": [round(50 + i * 3.5, 2) for i in range(20)],
    })
    suggestion = suggest_chart_type(df3)
    print(f"Type: {suggestion['chart_type']}, Pie eligible: {suggestion['pie_eligible']}")

    # Test 4: Temporal data
    print("\n=== Test 4: Time series ===")
    df4 = pd.DataFrame({
        "date": pd.date_range("2025-01-01", periods=5, freq="ME"),
        "revenue": [1000, 1200, 950, 1400, 1600],
    })
    suggestion = suggest_chart_type(df4)
    print(f"Type: {suggestion['chart_type']}")