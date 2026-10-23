# Alard Speaks Freely (Alard University Anonymous Complaint Portal) - Python / Flask

This is the original Lovable project (React + Vite + Tailwind + Supabase) converted to
**Python, Flask, SQLite, Jinja2 templates and a little vanilla JavaScript**.
The design is carried over by keeping the original design tokens and the exact same
Tailwind class names in the templates.

## Run it in VS Code on Windows

1. Install Python 3.10+ from python.org (tick **"Add python.exe to PATH"**).
2. In VS Code: **File > Open Folder...** and choose this folder.
3. Open a terminal (**Terminal > New Terminal**, PowerShell) and run:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
python app.py
```

> If PowerShell blocks `Activate.ps1`, run once:
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, or use `.venv\Scripts\activate.bat` in Command Prompt.

4. Open <http://127.0.0.1:5000>.

The SQLite database is created automatically at `instance/alard.db`.
The Google Fonts (Playfair Display, Source Sans 3) load from the internet, as in the original.

### Admin ("Authorities") login
Supabase auth was replaced by a local `admin_users` table. On first run an account is created from
`ADMIN_EMAIL` / `ADMIN_PASSWORD` in `.env` (default `admin@alard.edu` / `ChangeMe123!`).
**Change the password in `.env` before the first run**, or add more accounts with:

```powershell
flask --app app create-admin
```

## Project structure

```
app.py            Flask routes, admin login, CSRF, comment API
database.py       SQLite schema + queries (replaces Supabase)
ui.py             Rebuilds the shadcn/ui class strings (cva + tailwind-merge) for Jinja
icons.py          Lucide icons as inline SVG (same glyphs as lucide-react)
templates/        Jinja2 pages (one per original React page) + base layout
static/css/theme.css       Original index.css tokens/fonts/base + Tailwind reset + widget styles
static/css/utilities.css   Tailwind utility classes used by the templates
static/js/app.js           Select, dialogs, toasts, animations, comments, menu
static/images/    favicon.ico, placeholder.svg (original assets)
```

## What was converted

| Original | Now |
|---|---|
| Supabase tables `complaints`, `complaint_status_history`, `complaint_comments` | SQLite tables of the same name (`database.py`) |
| Supabase auth + `user_roles` | `admin_users` table, Flask sessions, hashed passwords |
| Row-level-security rules | Flask route checks (`@admin_required`) |
| React Router pages | Flask routes: `/`, `/submit`, `/track`, `/admin/login`, `/admin`, 404 |
| React components / shadcn UI | Jinja templates + `ui.py` class builders |
| Radix Select / AlertDialog | HTML + `static/js/app.js` |
| framer-motion fade/slide | CSS transitions triggered by `app.js` |
| sonner toasts | small toast function in `app.js` (+ Flask `flash()` messages) |

**Retained as-is:** all copy/text, layout, colour tokens, fonts, gradients, icons, favicon, robots.txt,
tracking-ID format (`ALU-XXXXXXXX`), categories and statuses.

## Behaviour carried over from the original (read this)

These are faithful to the original app; you may want to change them:

* **The "Personal remark (internal note)" box is not private.** It is saved into the status note and
  shown on the public tracking timeline as `[Remark] ...`.
* **Anyone who knows a tracking ID can read and delete that complaint.** Tracking IDs are also
  displayed on the public home-page feed, so any visitor can delete active complaints.
* **Attachments are not uploaded.** Only file *names* (max 5) are stored, never the files.
* Home-page comments need no login. Anyone can post one.
* Admin dashboard statistics count the currently filtered list.

Small additions needed because Supabase is gone: CSRF protection on forms, and a basic limit on
repeated failed admin logins.
