import os
import json
import sqlite3
from fastmcp import FastMCP

# Paths
DB_PATH = os.path.join(os.path.dirname(__file__), "expenses.db")
CATEGORIES_PATH = os.path.join(os.path.dirname(__file__), "categories.json")

mcp = FastMCP("ExpenseTracker")

# -------------------------------
# Database initialisation (SQLite)
# -------------------------------
def init_db():
    """Create expenses and credits tables if they don't exist."""
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        # Expenses table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                amount REAL NOT NULL,
                category TEXT NOT NULL,
                subcategory TEXT DEFAULT '',
                note TEXT DEFAULT ''
            )
        """)
        # Credits table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS credits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                amount REAL NOT NULL,
                category TEXT NOT NULL,
                subcategory TEXT DEFAULT '',
                note TEXT DEFAULT ''
            )
        """)
        conn.commit()

init_db()

# -------------------------------
# Helper to convert rows to dict
# -------------------------------
def row_to_dict(cursor, row):
    """Convert a sqlite3 row to a dictionary."""
    return {col[0]: row[i] for i, col in enumerate(cursor.description)}

# -------------------------------
# 1. Add expense
# -------------------------------
@mcp.tool()
def add_expense(date: str, amount: float, category: str, subcategory: str = "", note: str = ""):
    """Add a new expense entry."""
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute(
            "INSERT INTO expenses (date, amount, category, subcategory, note) VALUES (?,?,?,?,?)",
            (date, amount, category, subcategory, note)
        )
        return {"status": "ok", "id": cur.lastrowid}

# -------------------------------
# 2. List expenses (date range)
# -------------------------------
@mcp.tool()
def list_expenses(start_date: str, end_date: str):
    """List all expenses between start_date and end_date (inclusive)."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute(
            """
            SELECT id, date, amount, category, subcategory, note
            FROM expenses
            WHERE date BETWEEN ? AND ?
            ORDER BY id ASC
            """,
            (start_date, end_date)
        )
        rows = cur.fetchall()
        return [dict(row) for row in rows]

# -------------------------------
# 3. Summarise expenses by category (optional category filter)
# -------------------------------
@mcp.tool()
def summarize(start_date: str, end_date: str, category: str = None):
    """Summarise expenses by category within a date range."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        query = """
            SELECT category, SUM(amount) AS total_amount
            FROM expenses
            WHERE date BETWEEN ? AND ?
        """
        params = [start_date, end_date]
        if category:
            query += " AND category = ?"
            params.append(category)
        query += " GROUP BY category ORDER BY category ASC"
        cur = conn.execute(query, params)
        rows = cur.fetchall()
        return [dict(row) for row in rows]

# -------------------------------
# 4. Edit an existing expense
# -------------------------------
@mcp.tool()
def edit_expense(expense_id: int, date: str = None, amount: float = None,
                 category: str = None, subcategory: str = None, note: str = None):
    """Update fields of an expense. Only provided fields are updated."""
    updates = []
    params = []
    if date is not None:
        updates.append("date = ?")
        params.append(date)
    if amount is not None:
        updates.append("amount = ?")
        params.append(amount)
    if category is not None:
        updates.append("category = ?")
        params.append(category)
    if subcategory is not None:
        updates.append("subcategory = ?")
        params.append(subcategory)
    if note is not None:
        updates.append("note = ?")
        params.append(note)

    if not updates:
        return {"status": "error", "message": "No fields to update"}

    params.append(expense_id)
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute(
            f"UPDATE expenses SET {', '.join(updates)} WHERE id = ? RETURNING id",
            params
        )
        updated = cur.fetchone()
        conn.commit()
        if updated:
            return {"status": "ok", "id": updated[0]}
        else:
            return {"status": "error", "message": f"Expense with id {expense_id} not found"}

# -------------------------------
# 5. Delete an expense
# -------------------------------
@mcp.tool()
def delete_expense(expense_id: int):
    """Delete an expense by its ID."""
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute("DELETE FROM expenses WHERE id = ? RETURNING id", (expense_id,))
        deleted = cur.fetchone()
        conn.commit()
        if deleted:
            return {"status": "ok", "id": deleted[0]}
        else:
            return {"status": "error", "message": f"Expense with id {expense_id} not found"}

# -------------------------------
# 6. Add a credit / income entry
# -------------------------------
@mcp.tool()
def add_credit(date: str, amount: float, category: str, subcategory: str = "", note: str = ""):
    """Add a new credit (income) entry."""
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute(
            "INSERT INTO credits (date, amount, category, subcategory, note) VALUES (?,?,?,?,?)",
            (date, amount, category, subcategory, note)
        )
        return {"status": "ok", "id": cur.lastrowid}

# -------------------------------
# Resource: categories (JSON)
# -------------------------------
@mcp.resource("expense://categories", mime_type="application/json")
def categories():
    """Return the contents of categories.json."""
    with open(CATEGORIES_PATH, "r", encoding="utf-8") as f:
        return f.read()

# -------------------------------
# Run the MCP server
# -------------------------------
if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=8000)