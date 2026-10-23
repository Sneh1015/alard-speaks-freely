"""
database.py - SQLite storage for Alard Speaks Freely.

This replaces the Supabase (Postgres) backend of the original Lovable project.
The tables mirror the original schema:

    complaints                 -> public.complaints
    complaint_status_history   -> public.complaint_status_history
    complaint_comments         -> public.complaint_comments
    admin_users                -> auth.users + public.user_roles + public.profiles
                                  (only the admin/moderator accounts are stored,
                                  because complaint submitters are anonymous)

Everything here uses only Python's standard library (sqlite3).
"""

import os
import secrets
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from flask import current_app, g
from werkzeug.security import generate_password_hash

# --------------------------------------------------------------------------
# Constants (ported from src/lib/complaints.ts)
# --------------------------------------------------------------------------
COMPLAINT_CATEGORIES = [
    ("academic", "Academic Issues"),
    ("harassment", "Harassment"),
    ("infrastructure", "Infrastructure"),
    ("administration", "Administration"),
    ("faculty_behavior", "Faculty Behavior"),
    ("student_conduct", "Student Conduct"),
    ("financial", "Financial / Fee Related"),
    ("safety", "Safety & Security"),
    ("other", "Other"),
]
CATEGORY_LABELS = dict(COMPLAINT_CATEGORIES)

# status -> (label, colour classes) - same values as STATUS_CONFIG in complaints.ts
STATUS_CONFIG = {
    "received": ("Received", "bg-info text-info-foreground"),
    "in_review": ("In Review", "bg-warning text-warning-foreground"),
    "resolved": ("Resolved", "bg-success text-success-foreground"),
    "closed": ("Closed", "bg-muted text-muted-foreground"),
}

TRACKING_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no I, O, 0, 1


def generate_tracking_id() -> str:
    """ALU-XXXXXXXX, same alphabet and format as the original generateTrackingId()."""
    return "ALU-" + "".join(secrets.choice(TRACKING_ALPHABET) for _ in range(8))


def now_iso() -> str:
    """UTC timestamp that JavaScript's `new Date()` can parse directly."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def new_id() -> str:
    return str(uuid.uuid4())


# --------------------------------------------------------------------------
# Schema
# --------------------------------------------------------------------------
SCHEMA = """
CREATE TABLE IF NOT EXISTS complaints (
    id           TEXT PRIMARY KEY,
    tracking_id  TEXT NOT NULL UNIQUE,
    title        TEXT NOT NULL CHECK (length(title) > 0 AND length(title) <= 150),
    description  TEXT NOT NULL CHECK (length(description) > 0 AND length(description) <= 5000),
    category     TEXT NOT NULL CHECK (category IN (
                     'academic','harassment','infrastructure','administration',
                     'faculty_behavior','student_conduct','financial','safety','other')),
    status       TEXT NOT NULL DEFAULT 'received'
                     CHECK (status IN ('received','in_review','resolved','closed')),
    file_urls    TEXT,                       -- JSON list of attachment file names (as in the original)
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS complaint_status_history (
    id            TEXT PRIMARY KEY,
    complaint_id  TEXT NOT NULL REFERENCES complaints(id) ON DELETE CASCADE,
    status        TEXT NOT NULL CHECK (status IN ('received','in_review','resolved','closed')),
    note          TEXT,
    changed_by    TEXT REFERENCES admin_users(id),
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS complaint_comments (
    id            TEXT PRIMARY KEY,
    complaint_id  TEXT NOT NULL REFERENCES complaints(id) ON DELETE CASCADE,
    author_name   TEXT NOT NULL DEFAULT 'Anonymous Student'
                      CHECK (length(author_name) BETWEEN 1 AND 50),
    content       TEXT NOT NULL CHECK (length(content) BETWEEN 1 AND 1000),
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS admin_users (
    id             TEXT PRIMARY KEY,
    email          TEXT NOT NULL UNIQUE,
    password_hash  TEXT NOT NULL,
    display_name   TEXT,
    role           TEXT NOT NULL DEFAULT 'admin' CHECK (role IN ('admin','moderator')),
    created_at     TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_complaints_tracking_id ON complaints(tracking_id);
CREATE INDEX IF NOT EXISTS idx_complaints_status ON complaints(status);
CREATE INDEX IF NOT EXISTS idx_complaints_category ON complaints(category);
CREATE INDEX IF NOT EXISTS idx_status_history_complaint_id ON complaint_status_history(complaint_id);
CREATE INDEX IF NOT EXISTS idx_comments_complaint_id ON complaint_comments(complaint_id);
"""


# --------------------------------------------------------------------------
# Connection handling
# --------------------------------------------------------------------------
def _connect(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")  # needed for ON DELETE CASCADE
    return conn


def get_db() -> sqlite3.Connection:
    """One connection per request, stored on flask.g."""
    if "db" not in g:
        g.db = _connect(current_app.config["DATABASE"])
    return g.db


def close_db(_exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db(app) -> None:
    """Create the database file and tables if they don't exist yet."""
    path = Path(app.config["DATABASE"])
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = _connect(str(path))
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()
    app.teardown_appcontext(close_db)


# --------------------------------------------------------------------------
# Complaints
# --------------------------------------------------------------------------
def create_complaint(title, description, category, file_names):
    """Insert a complaint + its initial 'received' history row. Returns the tracking id."""
    import json

    db = get_db()
    complaint_id = new_id()
    ts = now_iso()
    for _ in range(10):  # retry in the (very unlikely) event of a tracking-id clash
        tracking_id = generate_tracking_id()
        try:
            db.execute(
                "INSERT INTO complaints (id, tracking_id, title, description, category, status,"
                " file_urls, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    complaint_id, tracking_id, title, description, category, "received",
                    json.dumps(file_names) if file_names else None, ts, ts,
                ),
            )
            break
        except sqlite3.IntegrityError as exc:
            if "tracking_id" not in str(exc):
                raise
    else:  # pragma: no cover
        raise RuntimeError("Could not generate a unique tracking id")

    db.execute(
        "INSERT INTO complaint_status_history (id, complaint_id, status, note, changed_by, created_at)"
        " VALUES (?,?,?,?,?,?)",
        (new_id(), complaint_id, "received", None, None, ts),
    )
    db.commit()
    return tracking_id


def get_active_complaints(limit=20):
    """Home page live feed: received / in_review, newest first."""
    return get_db().execute(
        "SELECT * FROM complaints WHERE status IN ('received','in_review')"
        " ORDER BY created_at DESC LIMIT ?",
        (limit,),
    ).fetchall()


def get_complaint_by_tracking_id(tracking_id):
    return get_db().execute(
        "SELECT * FROM complaints WHERE tracking_id = ?", (tracking_id,)
    ).fetchone()


def get_complaint(complaint_id):
    return get_db().execute("SELECT * FROM complaints WHERE id = ?", (complaint_id,)).fetchone()


def list_complaints(status=None, category=None):
    """Admin dashboard list with the optional status / category filters."""
    sql, params = "SELECT * FROM complaints", []
    where = []
    if status:
        where.append("status = ?")
        params.append(status)
    if category:
        where.append("category = ?")
        params.append(category)
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY created_at DESC"
    return get_db().execute(sql, params).fetchall()


def delete_complaint(complaint_id) -> bool:
    db = get_db()
    cur = db.execute("DELETE FROM complaints WHERE id = ?", (complaint_id,))  # cascades
    db.commit()
    return cur.rowcount > 0


def update_status(complaint_id, status, note, admin_id) -> bool:
    db = get_db()
    ts = now_iso()
    cur = db.execute(
        "UPDATE complaints SET status = ?, updated_at = ? WHERE id = ?",
        (status, ts, complaint_id),
    )
    if cur.rowcount == 0:
        db.rollback()
        return False
    db.execute(
        "INSERT INTO complaint_status_history (id, complaint_id, status, note, changed_by, created_at)"
        " VALUES (?,?,?,?,?,?)",
        (new_id(), complaint_id, status, note, admin_id, ts),
    )
    db.commit()
    return True


# --------------------------------------------------------------------------
# Status history
# --------------------------------------------------------------------------
def get_history(complaint_id):
    return get_db().execute(
        "SELECT * FROM complaint_status_history WHERE complaint_id = ? ORDER BY created_at ASC, rowid ASC",
        (complaint_id,),
    ).fetchall()


def get_history_for(complaint_ids):
    """{complaint_id: [rows]} for many complaints at once (admin dashboard)."""
    result = {cid: [] for cid in complaint_ids}
    if not complaint_ids:
        return result
    marks = ",".join("?" * len(complaint_ids))
    rows = get_db().execute(
        f"SELECT * FROM complaint_status_history WHERE complaint_id IN ({marks})"
        " ORDER BY created_at ASC, rowid ASC",
        list(complaint_ids),
    ).fetchall()
    for r in rows:
        result[r["complaint_id"]].append(r)
    return result


# --------------------------------------------------------------------------
# Comments
# --------------------------------------------------------------------------
def get_comments(complaint_id):
    return get_db().execute(
        "SELECT * FROM complaint_comments WHERE complaint_id = ? ORDER BY created_at DESC, rowid DESC",
        (complaint_id,),
    ).fetchall()


def get_comments_for(complaint_ids):
    result = {cid: [] for cid in complaint_ids}
    if not complaint_ids:
        return result
    marks = ",".join("?" * len(complaint_ids))
    rows = get_db().execute(
        f"SELECT * FROM complaint_comments WHERE complaint_id IN ({marks})"
        " ORDER BY created_at DESC, rowid DESC",
        list(complaint_ids),
    ).fetchall()
    for r in rows:
        result[r["complaint_id"]].append(r)
    return result


def add_comment(complaint_id, author_name, content):
    db = get_db()
    row_id = new_id()
    db.execute(
        "INSERT INTO complaint_comments (id, complaint_id, author_name, content, created_at)"
        " VALUES (?,?,?,?,?)",
        (row_id, complaint_id, author_name, content, now_iso()),
    )
    db.commit()
    return db.execute("SELECT * FROM complaint_comments WHERE id = ?", (row_id,)).fetchone()


def get_comment(comment_id):
    return get_db().execute(
        "SELECT * FROM complaint_comments WHERE id = ?", (comment_id,)
    ).fetchone()


def delete_comment(comment_id) -> bool:
    db = get_db()
    cur = db.execute("DELETE FROM complaint_comments WHERE id = ?", (comment_id,))
    db.commit()
    return cur.rowcount > 0


# --------------------------------------------------------------------------
# Admin users
# --------------------------------------------------------------------------
def get_admin_by_email(email):
    return get_db().execute(
        "SELECT * FROM admin_users WHERE lower(email) = lower(?)", (email,)
    ).fetchone()


def get_admin(admin_id):
    return get_db().execute("SELECT * FROM admin_users WHERE id = ?", (admin_id,)).fetchone()


def create_admin(email, password, role="admin", display_name=None):
    db = get_db()
    admin_id = new_id()
    db.execute(
        "INSERT INTO admin_users (id, email, password_hash, display_name, role, created_at)"
        " VALUES (?,?,?,?,?,?)",
        (admin_id, email.strip().lower(), generate_password_hash(password),
         display_name or email.strip(), role, now_iso()),
    )
    db.commit()
    return admin_id


def count_admins() -> int:
    return get_db().execute("SELECT COUNT(*) FROM admin_users").fetchone()[0]
