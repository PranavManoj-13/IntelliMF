# IntelliMF

This is now a multi-page Flask application with:

- Frontend: Jinja templates, CSS, and JavaScript charts
- Backend: Python Flask app
- Database: PostgreSQL for admin users, MF scheme cache, and SIP orders

## Features

- Search mutual funds using MFAPI
- Show all matching funds on a dedicated search results page
- View scheme details, NAV history, trailing returns, and SIP simulations
- Calculate SIP performance using daily NAV times cumulative units held
- Recommend the optimal SIP frequency for the selected fund and date range
- Admin login to add survey-collected SIP orders
- Frequent itemset mining with FP-Growth for "frequently bought together" funds

## Run

```bash
pip install -r requirements.txt
flask --app app run
```

Or:

```bash
python3 app.py
```

## Admin Login

Default credentials:

- Username: `admin`
- Password: `admin123`

Override them if needed:

```bash
export MF_ADMIN_USERNAME="your_admin_name"
export MF_ADMIN_PASSWORD="your_secure_password"
export FLASK_SECRET_KEY="your_secret_key"
export DATABASE_URL="postgresql://..."
```

## Notes

- The database is read from `DATABASE_URL`. On Railway, use the PostgreSQL service connection string.
- If MFAPI is temporarily unavailable and a local `data/raw/Schemes-List.csv` exists, the app falls back to that cache for scheme listing.
- SIP recommendation is based on the highest return percentage for the same installment amount over the selected period.

## Railway Deployment

Set these Railway variables:

- `DATABASE_URL`
- `FLASK_SECRET_KEY`
- `MF_ADMIN_USERNAME`
- `MF_ADMIN_PASSWORD`
- `COOKIE_SECURE=true`

The repo includes a [Procfile](/Users/pranav/acad./SEM-06/DSC413/Course-Project/Procfile) for a `gunicorn` web process. Railway can use that directly.

`FLASK_SECRET_KEY` must be set to one stable value in Railway. If it is missing, admin sessions will not remain valid across page loads, container restarts, or multiple running instances.

For deployment, Railway should install from the root [requirements.txt](/Users/pranav/acad./SEM-06/DSC413/Course-Project/requirements.txt).
The older [files/requirements.txt](/Users/pranav/acad./SEM-06/DSC413/Course-Project/files/requirements.txt) can remain for legacy course scripts, but it is not needed for production.
