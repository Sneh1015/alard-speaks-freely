"""
app.py - Alard Speaks Freely (Anonymous Complaint Portal) - Flask version.

This is the Python/Flask replacement for the original React + Supabase app.
Pages (same URLs as the original React Router routes):

    /               Home (hero, live complaints feed, how it works, authorities portal)
    /submit         Submit a complaint (anonymous)
    /track          Track a complaint by tracking ID (+ delete)
    /admin/login    Authorities login
    /admin          Authorities dashboard

Run it with:   python app.py
"""

import json
import os
import secrets
import time
from functools import wraps
from pathlib import Path

from flask import (
    Flask, abort, flash, get_flashed_messages, jsonify, redirect, render_template,
    request, send_from_directory, session, url_for,
)
from werkzeug.security import check_password_hash

import database as db
from icons import icon
from ui import HELPERS

BASE_DIR = Path(__file__).resolve().parent


# --------------------------------------------------------------------------
# Tiny .env loader (so beginners don't need an extra package)
# --------------------------------------------------------------------------
def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_env_file(BASE_DIR / ".env")


def _secret_key(instance_dir: Path) -> str:
    """SECRET_KEY from the environment, or a random one saved to instance/secret_key."""
    env_key = os.environ.get("SECRET_KEY")
    if env_key:
        return env_key
    instance_dir.mkdir(parents=True, exist_ok=True)
    key_file = instance_dir / "secret_key"
    if not key_file.exists():
        key_file.write_text(secrets.token_hex(32), encoding="utf-8")
    return key_file.read_text(encoding="utf-8").strip()


# --------------------------------------------------------------------------
# App factory
# --------------------------------------------------------------------------
def create_app() -> Flask:
    app = Flask(__name__, instance_path=str(BASE_DIR / "instance"))
    instance_dir = Path(app.instance_path)
    app.config.update(
        SECRET_KEY=_secret_key(instance_dir),
        DATABASE=os.environ.get("DATABASE_PATH", str(instance_dir / "alard.db")),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        PERMANENT_SESSION_LIFETIME=60 * 60 * 24 * 7,  # admin stays signed in for 7 days
        JSON_SORT_KEYS=False,
    )

    db.init_db(app)
    seed_first_admin(app)

    # ---- template helpers: the shadcn class builders, icons and constants ----
    app.jinja_env.globals.update(HELPERS)
    app.jinja_env.globals.update(
        icon=icon,
        COMPLAINT_CATEGORIES=db.COMPLAINT_CATEGORIES,
        STATUS_CONFIG=db.STATUS_CONFIG,
        csrf_token=csrf_token,
    )
    app.jinja_env.filters["category_label"] = lambda v: db.CATEGORY_LABELS.get(v, "")
    app.jinja_env.filters["tojson_attr"] = lambda v: json.dumps(v)

    register_hooks(app)
    register_routes(app)
    register_cli(app)
    return app


def seed_first_admin(app: Flask) -> None:
    """
    The original app used Supabase auth. Here, authorities are rows in `admin_users`.
    On the very first run (no admin yet) one account is created from ADMIN_EMAIL /
    ADMIN_PASSWORD in .env. Change these before using the site for real!
    """
    with app.app_context():
        if db.count_admins() > 0:
            return
        email = os.environ.get("ADMIN_EMAIL", "admin@alard.edu")
        password = os.environ.get("ADMIN_PASSWORD", "ChangeMe123!")
        db.create_admin(email, password, role="admin", display_name="Administrator")
        print("=" * 70)
        print(f" First run: created admin account  {email}")
        if "ADMIN_PASSWORD" not in os.environ:
            print(" Using the DEFAULT password from the README - change it in .env!")
        print("=" * 70)


# --------------------------------------------------------------------------
# CSRF protection (no extra package needed)
# --------------------------------------------------------------------------
def csrf_token() -> str:
    if "_csrf" not in session:
        session["_csrf"] = secrets.token_hex(16)
    return session["_csrf"]


def register_hooks(app: Flask) -> None:
    @app.before_request
    def check_csrf():
        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            sent = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token", "")
            expected = session.get("_csrf", "")
            if not expected or not secrets.compare_digest(sent, expected):
                if request.path.startswith("/api/"):
                    return jsonify(error="Invalid or missing CSRF token"), 400
                flash("Your session expired. Please try again.", "error")
                return redirect(request.referrer or url_for("index"))

    @app.context_processor
    def inject_globals():
        return {"current_path": request.path}

    @app.after_request
    def no_store_for_admin(resp):
        if request.path.startswith("/admin"):
            resp.headers["Cache-Control"] = "no-store"
        return resp


# --------------------------------------------------------------------------
# Auth helpers (replace useAuth.tsx)
# --------------------------------------------------------------------------
def current_admin():
    admin_id = session.get("admin_id")
    return db.get_admin(admin_id) if admin_id else None


def admin_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not current_admin():
            session.pop("admin_id", None)
            return redirect(url_for("admin_login"))
        return view(*args, **kwargs)

    return wrapper


_LOGIN_ATTEMPTS: dict = {}  # ip -> [timestamps]; tiny brute-force guard
_MAX_ATTEMPTS, _WINDOW = 8, 15 * 60


def _too_many_attempts(ip: str) -> bool:
    now = time.time()
    recent = [t for t in _LOGIN_ATTEMPTS.get(ip, []) if now - t < _WINDOW]
    _LOGIN_ATTEMPTS[ip] = recent
    return len(recent) >= _MAX_ATTEMPTS


# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------
def register_routes(app: Flask) -> None:
    # ------------------------------ public pages ------------------------------
    @app.get("/")
    def index():
        return render_template("index.html", complaints=db.get_active_complaints(20))

    @app.route("/submit", methods=["GET", "POST"])
    def submit_complaint():
        if request.method == "GET":
            return render_template("submit.html", form={})

        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        category = request.form.get("category", "")
        # The original app only stored the attachment *file names* (max 5).
        file_names = [
            os.path.basename(n)[:255] for n in request.form.getlist("file_name") if n.strip()
        ][:5]

        form = {"title": title, "description": description, "category": category}
        if not title or not description or category not in db.CATEGORY_LABELS:
            flash("Please fill in all required fields.", "error")
            return render_template("submit.html", form=form)
        if len(title) > 150 or len(description) > 5000:
            flash("Failed to submit complaint. Please try again.", "error")
            return render_template("submit.html", form=form)

        tracking_id = db.create_complaint(title, description, category, file_names)
        session["new_tracking_id"] = tracking_id
        return redirect(url_for("submit_done"))

    @app.get("/submit/done")
    def submit_done():
        tracking_id = session.pop("new_tracking_id", None)
        if not tracking_id:
            return redirect(url_for("submit_complaint"))
        return render_template("submit_done.html", tracking_id=tracking_id)

    @app.get("/track")
    def track_complaint():
        raw = request.args.get("id", "").strip()
        searched, complaint, history = bool(raw), None, []
        if searched:
            complaint = db.get_complaint_by_tracking_id(raw.upper())
            if complaint:
                history = db.get_history(complaint["id"])
        return render_template(
            "track.html", query=raw.upper(), searched=searched, complaint=complaint, history=history
        )

    @app.post("/track/delete")
    def track_delete():
        tracking_id = request.form.get("tracking_id", "").strip().upper()
        complaint = db.get_complaint_by_tracking_id(tracking_id)
        if complaint and db.delete_complaint(complaint["id"]):
            flash("Complaint deleted successfully.", "success")
        else:
            flash("Failed to delete complaint. Please try again.", "error")
        return redirect(url_for("track_complaint"))

    # ------------------------ comments (live feed on home) ------------------------
    def _comment_json(row):
        return {
            "id": row["id"],
            "author_name": row["author_name"],
            "content": row["content"],
            "created_at": row["created_at"],
        }

    @app.get("/api/complaints/<complaint_id>/comments")
    def api_get_comments(complaint_id):
        return jsonify([_comment_json(r) for r in db.get_comments(complaint_id)])

    @app.post("/api/complaints/<complaint_id>/comments")
    def api_post_comment(complaint_id):
        if not db.get_complaint(complaint_id):
            return jsonify(error="Complaint not found"), 404
        data = request.get_json(silent=True) or {}
        content = str(data.get("content", "")).strip()
        author = str(data.get("author_name", "")).strip() or "Anonymous Student"
        if not (1 <= len(content) <= 1000) or not (1 <= len(author) <= 50):
            return jsonify(error="Failed to post comment"), 400
        return jsonify(_comment_json(db.add_comment(complaint_id, author, content))), 201

    # ------------------------------ admin ------------------------------
    @app.route("/admin/login", methods=["GET", "POST"])
    def admin_login():
        if current_admin():
            return redirect(url_for("admin_dashboard"))
        if request.method == "POST":
            email = request.form.get("email", "").strip()
            password = request.form.get("password", "")
            if not email or not password:
                flash("Please enter your credentials.", "error")
                return render_template("admin_login.html", email=email)
            ip = request.remote_addr or "?"
            if _too_many_attempts(ip):
                flash("Too many login attempts. Please try again later.", "error")
                return render_template("admin_login.html", email=email)
            admin = db.get_admin_by_email(email)
            if not admin or not check_password_hash(admin["password_hash"], password):
                _LOGIN_ATTEMPTS.setdefault(ip, []).append(time.time())
                flash("Invalid login credentials", "error")
                return render_template("admin_login.html", email=email)
            session.clear()
            session.permanent = True
            session["admin_id"] = admin["id"]
            flash("Logged in successfully!", "success")
            return redirect(url_for("admin_dashboard"))
        return render_template("admin_login.html", email="")

    @app.post("/admin/logout")
    def admin_logout():
        session.clear()
        return redirect(url_for("index"))

    def _dash_redirect(open_id=None):
        """Back to the dashboard, keeping the filters and the expanded complaint."""
        params = {}
        if request.form.get("status_filter"):
            params["status"] = request.form["status_filter"]
        if request.form.get("category_filter"):
            params["category"] = request.form["category_filter"]
        if open_id:
            params["open"] = open_id
        return redirect(url_for("admin_dashboard", **params))

    @app.get("/admin")
    @admin_required
    def admin_dashboard():
        status = request.args.get("status", "all")
        category = request.args.get("category", "all")
        status_q = status if status in db.STATUS_CONFIG else None
        category_q = category if category in db.CATEGORY_LABELS else None
        complaints = db.list_complaints(status_q, category_q)
        ids = [c["id"] for c in complaints]
        # stats are computed from the (filtered) list - exactly like the original
        stats = {
            "total": len(complaints),
            "received": sum(1 for c in complaints if c["status"] == "received"),
            "in_review": sum(1 for c in complaints if c["status"] == "in_review"),
            "resolved": sum(1 for c in complaints if c["status"] == "resolved"),
        }
        return render_template(
            "admin_dashboard.html",
            complaints=complaints,
            history=db.get_history_for(ids),
            comments=db.get_comments_for(ids),
            stats=stats,
            status_filter=status_q or "all",
            category_filter=category_q or "all",
            open_id=request.args.get("open", ""),
        )

    @app.post("/admin/complaints/<complaint_id>/status")
    @admin_required
    def admin_update_status(complaint_id):
        status = request.form.get("status", "")
        if status not in db.STATUS_CONFIG:
            flash("Failed to update status", "error")
            return _dash_redirect(complaint_id)
        note = request.form.get("note", "").strip()
        remark = request.form.get("remark", "").strip()
        # Same behaviour as the original: public note and personal remark are
        # combined into one note saved with the status history.
        combined = " | ".join(p for p in [note, f"[Remark] {remark}" if remark else ""] if p) or None
        if db.update_status(complaint_id, status, combined, session["admin_id"]):
            flash("Status updated!", "success")
        else:
            flash("Failed to update status", "error")
        return _dash_redirect(complaint_id)

    @app.post("/admin/complaints/<complaint_id>/delete")
    @admin_required
    def admin_delete_complaint(complaint_id):
        if db.delete_complaint(complaint_id):
            flash("Complaint deleted successfully", "success")
        else:
            flash("Failed to delete complaint", "error")
        return _dash_redirect()

    @app.post("/admin/comments/<comment_id>/delete")
    @admin_required
    def admin_delete_comment(comment_id):
        comment = db.get_comment(comment_id)
        if comment and db.delete_comment(comment_id):
            flash("Comment deleted", "success")
        else:
            flash("Failed to delete comment", "error")
        return _dash_redirect(comment["complaint_id"] if comment else None)

    # ------------------------------ misc ------------------------------
    @app.get("/favicon.ico")
    def favicon():
        return send_from_directory(
            app.static_folder + "/images",
            "favicon.ico",
            mimetype="image/vnd.microsoft.icon",
        )

    @app.get("/robots.txt")
    def robots():
        return send_from_directory(app.static_folder, "robots.txt")

    @app.errorhandler(404)
    def not_found(_e):
        return render_template("404.html"), 404


# --------------------------------------------------------------------------
# Command line helper:  flask --app app create-admin
# --------------------------------------------------------------------------
def register_cli(app: Flask) -> None:
    import click

    @app.cli.command("create-admin")
    @click.option("--email", prompt=True)
    @click.option("--password", prompt=True, hide_input=True, confirmation_prompt=True)
    @click.option("--role", type=click.Choice(["admin", "moderator"]), default="admin")
    def create_admin_cmd(email, password, role):
        """Create (or fail on duplicate) an authority account."""
        if db.get_admin_by_email(email):
            click.echo("An account with that email already exists.")
            return
        db.create_admin(email, password, role=role)
        click.echo(f"Created {role} account for {email}")


app = create_app()

if __name__ == "__main__":
    app.run(
        host=os.environ.get("HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", "5000")),
        debug=os.environ.get("FLASK_DEBUG") == "1",
    )
