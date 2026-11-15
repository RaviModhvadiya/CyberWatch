# CyberWatch - Mini SIEM (SEIM Dashboard)

Flask + MySQL + ApexCharts, light theme, built from the SEIM Dashboard SRS. Fonts, icons and charts are bundled in `app/static/vendor`, so the app works fully offline.

## Run it

1. Start Apache and MySQL in XAMPP. Open http://localhost/phpmyadmin, go to the SQL tab, paste or import `database/cyberwatch.sql` and press Go. This creates the `cyberwatch` database, all tables, the default rules and the admin account. (Skipping this is fine too: the app creates everything itself on first start.)
2. Open a terminal in this folder:

```
python -m venv venv
venv\Scripts\activate
python -m pip install -r requirements.txt
python run.py
```

If `python -m venv venv` hangs, use `python -m venv venv --without-pip`, activate it, then run `python -m ensurepip --default-pip` before installing the requirements.

3. Open http://127.0.0.1:5000 and sign in with the admin from `.env` (`admin@cyberwatch.local` / `Admin@12345`). Change it after the first login.

No MySQL? Leave `DATABASE_URL=` empty in `.env` and a local SQLite file is used instead.

## Try it

Upload the files in `sample_logs/` (Apache, SSH, Windows and CSV) and watch the dashboard, alerts and charts fill in.

## Interface highlights

- Dashboard figures, charts and tables are clickable: a chart slice, bar or figure opens the matching filtered alerts or log view.
- Live dashboard refresh with a visible "updated" indicator and a manual refresh button.
- Alerts are grouped by status tabs with counts, colour-coded by severity, and every row opens its detail page.
- Press `/` anywhere to search by IP. Click the clipboard icon next to any IP or log line to copy it.
- Buttons show a loading state to prevent double submits, uploads show progress, pages fade between navigations, and the layout adapts to tablets and phones.

## Roles

- **Analyst**: uploads logs, explores entries, opens an alert, adds a note on how it was solved and changes its status (Open, Investigating, Resolved, False positive). Closing needs a note. One tick applies the update to every open alert from the same IP in that file. Analysts only see their own data.
- **Administrator**: everything above across all accounts, plus system overview (health, charts, per-analyst workload), user management, detection rule tuning and the activity trail.

## Configuration

- `.env`: database, admin seed, paging, thresholds for the dashboard, upload limits.
- `app/data/defaults.json`: roles, statuses, severity weights, CSV column aliases and the starting detection rules. Rules are copied into the database on first run and then edited from Administration > Detection rules.

## Layout

```
run.py, config.py
app/
  models.py            tables
  parsers/             apache, nginx, ssh, windows, csv
  services/            detector, pipeline, stats, reports
  routes/              auth, main, logs, alerts, reports, admin
  templates/, static/
```
