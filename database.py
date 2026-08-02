import sqlite3

DATABASE = "database.db"


def get_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_database():
    conn = get_connection()

    # Таблица пользователей
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER UNIQUE NOT NULL,
            username TEXT,
            premium INTEGER DEFAULT 0,
            progress INTEGER DEFAULT 0,
            lessons_completed INTEGER DEFAULT 0,
            purchase_date TEXT
        )
    """)

    # Таблица покупок
    conn.execute("""
        CREATE TABLE IF NOT EXISTS purchases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER NOT NULL,
            course TEXT NOT NULL,
            amount INTEGER NOT NULL,
            order_id TEXT UNIQUE NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()


def add_user(telegram_id, username=""):
    conn = get_connection()

    conn.execute("""
        INSERT OR IGNORE INTO users
        (telegram_id, username)
        VALUES (?, ?)
    """, (telegram_id, username))

    conn.commit()
    conn.close()


def get_user(telegram_id):
    conn = get_connection()

    user = conn.execute("""
        SELECT * FROM users
        WHERE telegram_id = ?
    """, (telegram_id,)).fetchone()

    conn.close()

    return user


def activate_premium(telegram_id):
    conn = get_connection()

    conn.execute("""
        UPDATE users
        SET premium = 1
        WHERE telegram_id = ?
    """, (telegram_id,))

    conn.commit()
    conn.close()


def update_progress(telegram_id, progress, lessons):
    conn = get_connection()

    conn.execute("""
        UPDATE users
        SET progress = ?,
            lessons_completed = ?
        WHERE telegram_id = ?
    """, (progress, lessons, telegram_id))

    conn.commit()
    conn.close()


def create_purchase(telegram_id, course, amount, order_id):
    conn = get_connection()

    conn.execute("""
        INSERT INTO purchases
        (telegram_id, course, amount, order_id)
        VALUES (?, ?, ?, ?)
    """, (telegram_id, course, amount, order_id))

    conn.commit()
    conn.close()


def get_purchase(order_id):
    conn = get_connection()

    purchase = conn.execute("""
        SELECT * FROM purchases
        WHERE order_id = ?
    """, (order_id,)).fetchone()

    conn.close()

    return purchase


def complete_purchase(order_id):
    conn = get_connection()

    conn.execute("""
        UPDATE purchases
        SET status = 'paid'
        WHERE order_id = ?
    """, (order_id,))

    conn.commit()
    conn.close()
