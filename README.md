# jkxx

A small Django time-tracking dashboard for study sessions.

## Features

- Dashboard for daily and weekly study time progress.
- Categories for math, English, major course, and training sessions.
- Active-session full-screen focus timer.
- Recent record preview and 90-day heatmap.
- Recent 30-day and all-time aggregate statistics.
- CSV export for completed time logs.
- Environment-based token, host, goal, and exam-date configuration.

## Setup

Python 3.8+ is supported.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py runserver 0.0.0.0:8000
```

Open `http://127.0.0.1:8000/`.

## Configuration

Environment variables:

- `DJANGO_SECRET_KEY`: Django secret key. Required for production.
- `DJANGO_DEBUG`: `true` or `false`. Defaults to `false`.
- `DJANGO_ALLOWED_HOSTS`: comma-separated host list.
- `TRACKER_API_TOKEN`: token used by `/api/action/`.
- `TRACKER_DAILY_TARGET_MINUTES`: daily target minutes shown on the dashboard.
- `TRACKER_WEEKLY_TARGET_MINUTES`: weekly target minutes shown on the dashboard.
- `TRACKER_EXAM_DATE`: countdown target date, formatted as `YYYY-MM-DD`.

## Commands

Start a task:

```bash
python manage.py track start math
```

Stop the active task:

```bash
python manage.py track stop
```

Show statistics:

```bash
python manage.py stats --days 7
```

## CSV Export

Set the token in the dashboard first, then use the `导出CSV` button.

The backend endpoint is:

```text
GET /api/export.csv?days=365
Authorization: <TRACKER_API_TOKEN>
```

The exported columns are:

- `start_time`
- `end_time`
- `category`
- `category_label`
- `duration_minutes`
- `note`

## Maintenance

Run checks and tests:

```bash
python manage.py check
python manage.py test
```

For deployment, collect static files locally on the target machine:

```bash
python manage.py collectstatic --noinput
```

See [MIGRATION.md](MIGRATION.md) for moving the project and SQLite data to a
new server.
