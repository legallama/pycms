# pycms

Single-site CRM + CMS built with Python + Flask, with a UIkit admin and a UIkit-based default public theme.

## Quickstart (Windows PowerShell)

Create and activate a virtualenv:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install dependencies:

```powershell
pip install -r requirements.txt
```

Set environment variables (or create a `.env` file from `.env.example`):

```powershell
Copy-Item .env.example .env
```

Initialize the database and create an admin user:

```powershell
py manage.py db init
py manage.py db migrate -m "init"
py manage.py db upgrade
py manage.py create-admin admin@example.com "ChangeMeNow!"
```

Run:

```powershell
py manage.py run
```

Then visit:
- Public site: `http://127.0.0.1:5000/`
- Admin: `http://127.0.0.1:5000/admin/`

## Database (SQLite now, Postgres later)

Set `DATABASE_URL` to switch databases. Examples:
- SQLite: `sqlite:///instance/app.db`
- Postgres: `postgresql+psycopg://user:pass@localhost:5432/pycms`

