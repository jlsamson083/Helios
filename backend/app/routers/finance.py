from fastapi import APIRouter

from app.core.database import get_connection


router = APIRouter()


@router.get("/summary")
def monthly_summary():
    connection = get_connection()
    try:
        rows = connection.execute(
            """
            SELECT substr(transaction_date, 1, 7) AS month,
                   SUM(CASE WHEN direction = 'income' THEN amount_php ELSE 0 END) AS income_php,
                   SUM(CASE WHEN direction = 'expense' THEN amount_php ELSE 0 END) AS expenses_php
            FROM finance_entries
            GROUP BY substr(transaction_date, 1, 7)
            ORDER BY month
            """
        ).fetchall()
    finally:
        connection.close()
    months = []
    for row in rows:
        income = float(row["income_php"] or 0)
        expenses = float(row["expenses_php"] or 0)
        months.append({
            "month": row["month"],
            "income_php": income,
            "expenses_php": expenses,
            "remaining_php": income - expenses,
        })
    return {"months": months}


@router.get("/entries")
def entries():
    connection = get_connection()
    try:
        rows = connection.execute(
            """
            SELECT id, transaction_date, direction, description, category,
                   amount_php, source, created_at
            FROM finance_entries
            ORDER BY transaction_date DESC, id DESC
            LIMIT 250
            """
        ).fetchall()
    finally:
        connection.close()
    return {"entries": [dict(row) for row in rows]}
