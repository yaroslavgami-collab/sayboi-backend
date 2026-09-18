import secrets
import string
import sqlite3
import json
import re
from datetime import datetime, timezone

from werkzeug.security import generate_password_hash, check_password_hash

DATABASE = "database.db"


def get_connection():
    conn = sqlite3.connect(
        DATABASE,
        timeout=30
    )

    conn.row_factory = sqlite3.Row

    conn.execute("PRAGMA busy_timeout = 30000")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")

    return conn


def _add_column_if_missing(conn, table, column, definition):
    existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}

    if column not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def init_database():
    conn = get_connection()

    # Таблица пользователей (телеграм-бот / оплата)
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

    # ======================================
    # LMS: аккаунты (учителя и ученики)
    # ======================================

    conn.execute("""
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT NOT NULL CHECK(role IN ('teacher', 'student')),
            login TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            full_name TEXT,
            telegram_id INTEGER UNIQUE,
            course TEXT,
            must_change_password INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS lessons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course TEXT NOT NULL,
            order_index INTEGER NOT NULL DEFAULT 0,
            title TEXT NOT NULL,
            content TEXT,
            video_url TEXT,
            attachment_url TEXT,
            scheduled_at TEXT,
            is_published INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lesson_id INTEGER NOT NULL REFERENCES lessons(id) ON DELETE CASCADE,
            order_index INTEGER NOT NULL DEFAULT 0,
            title TEXT NOT NULL,
            description TEXT,
            type TEXT NOT NULL DEFAULT 'text',
            options TEXT,
            correct_option INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    _add_column_if_missing(conn, "lessons", "attachment_url", "TEXT")
    _add_column_if_missing(conn, "assignments", "type", "TEXT NOT NULL DEFAULT 'text'")
    _add_column_if_missing(conn, "assignments", "options", "TEXT")
    _add_column_if_missing(conn, "assignments", "correct_option", "INTEGER")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS lesson_progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
            lesson_id INTEGER NOT NULL REFERENCES lessons(id) ON DELETE CASCADE,
            completed_at TEXT NOT NULL,
            UNIQUE(student_id, lesson_id)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
            assignment_id INTEGER NOT NULL REFERENCES assignments(id) ON DELETE CASCADE,
            answer_text TEXT,
            status TEXT DEFAULT 'submitted' CHECK(status IN ('submitted', 'reviewed')),
            score INTEGER,
            feedback TEXT,
            submitted_at TEXT NOT NULL,
            reviewed_at TEXT,
            UNIQUE(student_id, assignment_id)
        )
    """)

    conn.commit()
    conn.close()


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


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


# ==========================================
# LMS: АККАУНТЫ
# ==========================================

LOGIN_ALPHABET = string.digits
PASSWORD_ALPHABET = string.ascii_letters + string.digits


def _generate_password(length=10):
    return "".join(
        secrets.choice(PASSWORD_ALPHABET) for _ in range(length)
    )


def _generate_unique_login(conn, prefix):
    while True:
        candidate = prefix + "".join(
            secrets.choice(LOGIN_ALPHABET) for _ in range(5)
        )

        exists = conn.execute(
            "SELECT 1 FROM accounts WHERE login = ?",
            (candidate,)
        ).fetchone()

        if not exists:
            return candidate


def _generate_login_from_username(conn, username, fallback_prefix="std"):
    """
    Формує логін з telegram-нікнейму (без @, тільки [a-z0-9_], до 20 символів).
    Якщо нікнейм відсутній/порожній після очищення — падає назад на випадковий логін.
    При колізії додає числовий суфікс (ivan, ivan2, ivan3, ...).
    """

    base = re.sub(r"[^a-z0-9_]", "", (username or "").lower())[:20]

    if not base:
        return _generate_unique_login(conn, fallback_prefix)

    candidate = base
    suffix = 1

    while True:
        exists = conn.execute(
            "SELECT 1 FROM accounts WHERE login = ?",
            (candidate,)
        ).fetchone()

        if not exists:
            return candidate

        suffix += 1
        candidate = f"{base}{suffix}"


def get_account(account_id):
    conn = get_connection()

    account = conn.execute(
        "SELECT * FROM accounts WHERE id = ?",
        (account_id,)
    ).fetchone()

    conn.close()

    return account


def get_account_by_login(login):
    conn = get_connection()

    account = conn.execute(
        "SELECT * FROM accounts WHERE login = ?",
        (login,)
    ).fetchone()

    conn.close()

    return account


def has_teacher():
    conn = get_connection()

    row = conn.execute(
        "SELECT 1 FROM accounts WHERE role = 'teacher' LIMIT 1"
    ).fetchone()

    conn.close()

    return row is not None


def get_account_by_telegram_id(telegram_id):
    conn = get_connection()

    account = conn.execute(
        "SELECT * FROM accounts WHERE telegram_id = ?",
        (telegram_id,)
    ).fetchone()

    conn.close()

    return account


def verify_login(login, password):
    account = get_account_by_login(login)

    if account is None:
        return None

    if not check_password_hash(account["password_hash"], password):
        return None

    return account


def get_or_create_student_account(telegram_id, course, full_name="", username=""):
    """
    Идемпотентно создаёт аккаунт ученика после оплаты.
    Возвращает (account_row, plain_password_or_None).
    plain_password is None если аккаунт уже существовал (пароль не меняем).
    """

    conn = get_connection()

    existing = conn.execute(
        "SELECT * FROM accounts WHERE telegram_id = ?",
        (telegram_id,)
    ).fetchone()

    if existing is not None:
        conn.execute(
            "UPDATE accounts SET course = ? WHERE id = ?",
            (course, existing["id"])
        )
        conn.commit()

        account = conn.execute(
            "SELECT * FROM accounts WHERE id = ?",
            (existing["id"],)
        ).fetchone()

        conn.close()

        return account, None

    login = _generate_login_from_username(conn, username)
    plain_password = _generate_password()
    password_hash = generate_password_hash(plain_password)

    conn.execute("""
        INSERT INTO accounts
        (role, login, password_hash, full_name, telegram_id, course, must_change_password, created_at)
        VALUES ('student', ?, ?, ?, ?, ?, 1, ?)
    """, (login, password_hash, full_name, telegram_id, course, _now()))

    conn.commit()

    account = conn.execute(
        "SELECT * FROM accounts WHERE login = ?",
        (login,)
    ).fetchone()

    conn.close()

    return account, plain_password


def create_teacher_account(full_name):
    conn = get_connection()

    login = _generate_unique_login(conn, "tch")
    plain_password = _generate_password()
    password_hash = generate_password_hash(plain_password)

    conn.execute("""
        INSERT INTO accounts
        (role, login, password_hash, full_name, must_change_password, created_at)
        VALUES ('teacher', ?, ?, ?, 1, ?)
    """, (login, password_hash, full_name, _now()))

    conn.commit()
    conn.close()

    return login, plain_password


def set_password(account_id, new_plain_password):
    conn = get_connection()

    conn.execute("""
        UPDATE accounts
        SET password_hash = ?, must_change_password = 0
        WHERE id = ?
    """, (generate_password_hash(new_plain_password), account_id))

    conn.commit()
    conn.close()


def list_students(course=None):
    conn = get_connection()

    if course:
        rows = conn.execute("""
            SELECT * FROM accounts
            WHERE role = 'student' AND course = ?
            ORDER BY created_at DESC
        """, (course,)).fetchall()
    else:
        rows = conn.execute("""
            SELECT * FROM accounts
            WHERE role = 'student'
            ORDER BY created_at DESC
        """).fetchall()

    conn.close()

    return rows


def get_teacher_overview_stats():
    conn = get_connection()

    lessons_count = conn.execute("SELECT COUNT(*) AS n FROM lessons WHERE is_published = 1").fetchone()["n"]
    students_count = conn.execute("SELECT COUNT(*) AS n FROM accounts WHERE role = 'student'").fetchone()["n"]
    pending_count = conn.execute("SELECT COUNT(*) AS n FROM submissions WHERE status = 'submitted'").fetchone()["n"]

    conn.close()

    return {
        "lessons_count": lessons_count,
        "students_count": students_count,
        "pending_count": pending_count,
    }


def get_pending_submissions():
    conn = get_connection()

    rows = conn.execute("""
        SELECT
            s.*,
            acc.full_name AS student_name,
            acc.login AS student_login,
            a.title AS assignment_title,
            a.lesson_id AS lesson_id,
            l.title AS lesson_title
        FROM submissions s
        JOIN accounts acc ON acc.id = s.student_id
        JOIN assignments a ON a.id = s.assignment_id
        JOIN lessons l ON l.id = a.lesson_id
        WHERE s.status = 'submitted'
        ORDER BY s.submitted_at ASC
    """).fetchall()

    conn.close()

    return rows


# ==========================================
# LMS: УРОКИ
# ==========================================

def create_lesson(course, title, content, video_url, attachment_url, scheduled_at, order_index):
    conn = get_connection()

    now = _now()

    cursor = conn.execute("""
        INSERT INTO lessons
        (course, order_index, title, content, video_url, attachment_url, scheduled_at, is_published, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
    """, (course, order_index, title, content, video_url, attachment_url, scheduled_at, now, now))

    conn.commit()

    lesson_id = cursor.lastrowid

    conn.close()

    return lesson_id


def update_lesson(lesson_id, course, title, content, video_url, attachment_url, scheduled_at, order_index, is_published):
    conn = get_connection()

    conn.execute("""
        UPDATE lessons
        SET course = ?, order_index = ?, title = ?, content = ?,
            video_url = ?, attachment_url = ?, scheduled_at = ?, is_published = ?, updated_at = ?
        WHERE id = ?
    """, (
        course, order_index, title, content, video_url, attachment_url,
        scheduled_at, 1 if is_published else 0, _now(), lesson_id
    ))

    conn.commit()
    conn.close()


def delete_lesson(lesson_id):
    conn = get_connection()

    conn.execute("DELETE FROM lessons WHERE id = ?", (lesson_id,))

    conn.commit()
    conn.close()


def get_lesson(lesson_id):
    conn = get_connection()

    lesson = conn.execute(
        "SELECT * FROM lessons WHERE id = ?",
        (lesson_id,)
    ).fetchone()

    conn.close()

    return lesson


def list_all_lessons():
    conn = get_connection()

    rows = conn.execute("""
        SELECT * FROM lessons
        ORDER BY course, order_index
    """).fetchall()

    conn.close()

    return rows


def get_lessons_by_course(course, published_only=False):
    conn = get_connection()

    if published_only:
        rows = conn.execute("""
            SELECT * FROM lessons
            WHERE course = ? AND is_published = 1
            ORDER BY order_index
        """, (course,)).fetchall()
    else:
        rows = conn.execute("""
            SELECT * FROM lessons
            WHERE course = ?
            ORDER BY order_index
        """, (course,)).fetchall()

    conn.close()

    return rows


# ==========================================
# LMS: ЗАДАНИЯ
# ==========================================

def create_assignment(lesson_id, title, description, order_index, type="text", options=None, correct_option=None):
    conn = get_connection()

    options_json = json.dumps(options, ensure_ascii=False) if options else None

    cursor = conn.execute("""
        INSERT INTO assignments
        (lesson_id, order_index, title, description, type, options, correct_option, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (lesson_id, order_index, title, description, type, options_json, correct_option, _now()))

    conn.commit()

    assignment_id = cursor.lastrowid

    conn.close()

    return assignment_id


def update_assignment(assignment_id, title, description, order_index, type="text", options=None, correct_option=None):
    conn = get_connection()

    options_json = json.dumps(options, ensure_ascii=False) if options else None

    conn.execute("""
        UPDATE assignments
        SET title = ?, description = ?, order_index = ?, type = ?, options = ?, correct_option = ?
        WHERE id = ?
    """, (title, description, order_index, type, options_json, correct_option, assignment_id))

    conn.commit()
    conn.close()


def get_assignment_options(assignment):
    if not assignment["options"]:
        return []

    return json.loads(assignment["options"])


def delete_assignment(assignment_id):
    conn = get_connection()

    conn.execute("DELETE FROM assignments WHERE id = ?", (assignment_id,))

    conn.commit()
    conn.close()


def get_assignment(assignment_id):
    conn = get_connection()

    assignment = conn.execute(
        "SELECT * FROM assignments WHERE id = ?",
        (assignment_id,)
    ).fetchone()

    conn.close()

    return assignment


def get_assignments_by_lesson(lesson_id):
    conn = get_connection()

    rows = conn.execute("""
        SELECT * FROM assignments
        WHERE lesson_id = ?
        ORDER BY order_index
    """, (lesson_id,)).fetchall()

    conn.close()

    return rows


# ==========================================
# LMS: ПРОГРЕСС И ОТВЕТЫ
# ==========================================

def mark_lesson_completed(student_id, lesson_id):
    conn = get_connection()

    conn.execute("""
        INSERT OR IGNORE INTO lesson_progress
        (student_id, lesson_id, completed_at)
        VALUES (?, ?, ?)
    """, (student_id, lesson_id, _now()))

    conn.commit()
    conn.close()


def get_completed_lesson_ids(student_id):
    conn = get_connection()

    rows = conn.execute("""
        SELECT lesson_id FROM lesson_progress
        WHERE student_id = ?
    """, (student_id,)).fetchall()

    conn.close()

    return {row["lesson_id"] for row in rows}


def submit_assignment(student_id, assignment_id, answer_text):
    conn = get_connection()

    conn.execute("""
        INSERT INTO submissions
        (student_id, assignment_id, answer_text, status, submitted_at)
        VALUES (?, ?, ?, 'submitted', ?)
        ON CONFLICT(student_id, assignment_id) DO UPDATE SET
            answer_text = excluded.answer_text,
            status = 'submitted',
            score = NULL,
            feedback = NULL,
            submitted_at = excluded.submitted_at,
            reviewed_at = NULL
    """, (student_id, assignment_id, answer_text, _now()))

    conn.commit()
    conn.close()


def submit_quiz_answer(student_id, assignment_id, answer_text, is_correct):
    conn = get_connection()

    now = _now()
    score = 100 if is_correct else 0
    feedback = "Правильна відповідь!" if is_correct else "Неправильно."

    conn.execute("""
        INSERT INTO submissions
        (student_id, assignment_id, answer_text, status, score, feedback, submitted_at, reviewed_at)
        VALUES (?, ?, ?, 'reviewed', ?, ?, ?, ?)
        ON CONFLICT(student_id, assignment_id) DO UPDATE SET
            answer_text = excluded.answer_text,
            status = 'reviewed',
            score = excluded.score,
            feedback = excluded.feedback,
            submitted_at = excluded.submitted_at,
            reviewed_at = excluded.reviewed_at
    """, (student_id, assignment_id, answer_text, score, feedback, now, now))

    conn.commit()
    conn.close()


def get_submissions_for_student(student_id, lesson_id):
    conn = get_connection()

    rows = conn.execute("""
        SELECT s.* FROM submissions s
        JOIN assignments a ON a.id = s.assignment_id
        WHERE s.student_id = ? AND a.lesson_id = ?
    """, (student_id, lesson_id)).fetchall()

    conn.close()

    return {row["assignment_id"]: row for row in rows}


def get_student_stats(student_id):
    conn = get_connection()

    row = conn.execute("""
        SELECT
            COUNT(*) AS total_submissions,
            SUM(CASE WHEN score = 100 THEN 1 ELSE 0 END) AS correct_quiz_answers,
            SUM(CASE WHEN status = 'reviewed' THEN 1 ELSE 0 END) AS reviewed_count
        FROM submissions
        WHERE student_id = ?
    """, (student_id,)).fetchone()

    completed = conn.execute("""
        SELECT COUNT(*) AS n FROM lesson_progress WHERE student_id = ?
    """, (student_id,)).fetchone()

    conn.close()

    return {
        "total_submissions": row["total_submissions"] or 0,
        "correct_quiz_answers": row["correct_quiz_answers"] or 0,
        "reviewed_count": row["reviewed_count"] or 0,
        "lessons_completed": completed["n"] or 0,
    }


def get_submissions_for_assignment(assignment_id):
    conn = get_connection()

    rows = conn.execute("""
        SELECT s.*, a.full_name, a.login FROM submissions s
        JOIN accounts a ON a.id = s.student_id
        WHERE s.assignment_id = ?
        ORDER BY s.submitted_at DESC
    """, (assignment_id,)).fetchall()

    conn.close()

    return rows


def grade_submission(submission_id, score, feedback):
    conn = get_connection()

    conn.execute("""
        UPDATE submissions
        SET score = ?, feedback = ?, status = 'reviewed', reviewed_at = ?
        WHERE id = ?
    """, (score, feedback, _now(), submission_id))

    conn.commit()
    conn.close()


def get_student_lessons_with_status(student_id, course):
    """
    Возвращает уроки курса с расчётом доступности:
    'locked'    — ещё не открыт (не наступила дата или не завершён предыдущий)
    'unlocked'  — доступен, но не завершён
    'completed' — завершён учеником
    """

    now_iso = _now()

    lessons = get_lessons_by_course(course, published_only=True)
    completed_ids = get_completed_lesson_ids(student_id)

    available = [
        lesson for lesson in lessons
        if not lesson["scheduled_at"] or lesson["scheduled_at"] <= now_iso
    ]

    result = []
    previous_completed = True

    for lesson in available:
        is_completed = lesson["id"] in completed_ids

        if is_completed:
            status = "completed"
        elif previous_completed:
            status = "unlocked"
        else:
            status = "locked"

        result.append({"lesson": lesson, "status": status})

        previous_completed = is_completed

    return result
