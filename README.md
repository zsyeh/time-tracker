# jkxx

A small Django time-tracking dashboard for study sessions.

## Features

- Dashboard for daily and weekly study time progress.
- Daily study history page with session count, first start time, effective time,
  and target progress.
- Categories for math, English, and major course sessions.
- Distraction-free full-screen focus view with only the subject, Shanghai time,
  and an end-session control.
- Recent record preview and 180-day GitHub-style heatmap.
- Recent 30-day, all-time, active-day, best-day, and streak statistics.
- CSV export for completed time logs.
- Denormalized daily statistics that are backfilled by migration and kept in sync
  when completed logs are saved, moved, or deleted.
- Button-triggered, responsive summer schedule with timeline, training, quota,
  and rule views.
- Header-protected dashboard, APIs, exports, and administration routes.
- Environment-based token, host, goal, and exam-date configuration.

## Setup

Python 3.8+ is supported.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Set a private, non-empty `TRACKER_API_TOKEN` in `.env`; the checked-in example
intentionally leaves it blank so a missing configuration fails closed. Then run:

```bash
python manage.py migrate
python manage.py runserver 0.0.0.0:8000
```

Open `http://127.0.0.1:8000/`.

The complete daily history is available at `http://127.0.0.1:8000/daily-stats/`.

## Configuration

Environment variables:

- `DJANGO_SECRET_KEY`: Django secret key. Required for production.
- `DJANGO_DEBUG`: `true` or `false`. Defaults to `false`.
- `DJANGO_ALLOWED_HOSTS`: comma-separated host list.
- `TRACKER_API_TOKEN`: required token supplied in the raw `Authorization` header
  for every application request. It has no default; an empty value keeps the
  entire site locked. Use a long random ASCII value and make sure any reverse
  proxy forwards the header unchanged.
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

Rebuild the derived daily statistics after a manual or bulk database change:

```bash
python manage.py rebuild_daily_stats
```

## Daily Statistics

`DailyStudyStat` stores one derived row per active study date. Its study count,
first start time, and total effective minutes are calculated from completed
`TimeLog` records using the configured `Asia/Shanghai` timezone. A session that
crosses midnight belongs to the date on which it started.

Migration `0004_dailystudystat` automatically backfills all existing completed
records. Normal model saves and deletes then keep the derived rows synchronized.
Because bulk SQL updates bypass Django signals, run `rebuild_daily_stats` after
any such maintenance.

## CSV Export

The site returns no study data until the configured token is supplied as the raw
`Authorization` header. Browser page entries use a blank authentication gate:
it reads the value saved by the `eh专用` control (or asks for it), then requests
the protected page with the header. Invalid or cancelled authentication leaves
the page blank.

After authentication, use the `导出CSV` button to export records.

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

## Summer Schedule

The schedule shown by the `暑假作息` dialog is maintained in
`tracker/schedule.py`. Its timeline, weekly training, study quotas, and rules
are structured separately, so later adjustments only require editing that
configuration module; the dashboard template and JavaScript do not need to be
rewritten.

## Maintenance

Run checks and tests:

```bash
python manage.py check
python manage.py test
```

Always run `python manage.py migrate` during deployment. The daily-statistics
migration performs the one-time historical backfill on the target database.

For deployment, collect static files locally on the target machine:

```bash
python manage.py collectstatic --noinput
```

See [MIGRATION.md](MIGRATION.md) for moving the project and SQLite data to a
new server.
