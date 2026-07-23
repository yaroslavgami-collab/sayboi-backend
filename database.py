
import sqlite3

DATABASE = "database.db"


def get_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS purchases (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id TEXT NOT NULL,
        course TEXT NOT NULL,
        amount INTEGER NOT NULL,
        order_id TEXT UNIQUE NOT NULL,
        status TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    conn.commit()
    conn.close()


def create_purchase(telegram_id, course, amount, order_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO purchases
    (telegram_id, course, amount, order_id, status)
    VALUES (?, ?, ?, ?, ?)
    """, (
        telegram_id,
        course,
        amount,
        order_id,
        "pending"
    ))

    conn.commit()
    conn.close()


def payment_success(order_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    UPDATE purchases
    SET status='success'
    WHERE order_id=?
    """, (order_id,))

    conn.commit()
    conn.close()


def payment_failed(order_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    UPDATE purchases
    SET status='failed'
    WHERE order_id=?
    """, (order_id,))

    conn.commit()
    conn.close()


def has_access(telegram_id, course):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT *
    FROM purchases
    WHERE telegram_id=?
    AND course=?
    AND status='success'
    """, (
        telegram_id,
        course
    ))

    result = cursor.fetchone()

    conn.close()

    return result is not None


def get_purchase(order_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT *
    FROM purchases
    WHERE order_id=?
    """, (order_id,))

    result = cursor.fetchone()

    conn.close()

    return result