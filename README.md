# IntelliMF

IntelliMF is a Flask app for mutual fund search, NAV analysis, SIP simulation, and investor basket analysis. It uses PostgreSQL in production and also supports SQLite for local development.

[Production site](https://intellimf.pranavmanoj.in) hosted on Railway.

## Run locally

Install the dependencies in your Python environment:

```bash
pip install -r requirements.txt
```

To use a separate local SQLite database:

```bash
DATABASE_URL=sqlite:///data/local.db COOKIE_SECURE=false python -m flask --app app run --debug --port 5001
```

Open `http://localhost:5001`. To use PostgreSQL instead, set `DATABASE_URL` to a working PostgreSQL connection string in your environment or `.env`.

## Set up admin access

There is no built-in admin password. The app disables accounts that still use the old default password. Create or reset an account with the hidden password prompt (use a password of 12–256 characters):

```bash
DATABASE_URL=sqlite:///data/local.db FLASK_DEBUG=true python -m flask --app app set-admin --username admin
```

Open **Admin Login** in the site footer or visit `/admin/login` directly. Use the same `DATABASE_URL` as the server. For PostgreSQL, omit the SQLite override and use the configured connection. Resetting a password invalidates existing sessions for that account. Existing accounts with a non-default password can keep using it. Legacy plaintext passwords are migrated to hashes, and the plaintext column is removed.

An explicitly configured `MF_ADMIN_USERNAME` and strong `MF_ADMIN_PASSWORD` can bootstrap a new account. These variables do not reset an existing account; use `set-admin` for that.

## Collect investor baskets

Share `/share-basket` to collect anonymous selections of up to 20 funds. One submission per browser session is counted, and no names, contact details, or investment amounts are requested. Admins can find and delete submissions from **Workspace → Public Baskets**. Each public submission and each admin-entered investor basket contributes separately to FP-Growth. Results are recalculated from the remaining baskets after deletion. The analysis reports recurring pairs and triples.

## Notes

- Fund details are loaded from MFAPI. If the catalogue refresh fails, the app uses its existing cache or the bundled scheme list.
- SIP comparisons hold the monthly budget constant and only count executions within the selected period.
- Preprocess the course NAV files with `python files/Data-Preprocessing.py`.
- Run the regression suite with `python -m unittest discover -s tests -v`.

## Deploy

The `Procfile` starts Gunicorn. Set a stable, random `FLASK_SECRET_KEY`, a working `DATABASE_URL`, and `COOKIE_SECURE=true` for HTTPS. Set `TRUST_PROXY=true` only when requests arrive through one trusted reverse proxy that sets the forwarded client IP and protocol. This lets request limits distinguish visitors behind that proxy. Configure admin bootstrap credentials or run `set-admin` against the deployment database.
