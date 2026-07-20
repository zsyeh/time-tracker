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
- Header-protected dashboard, APIs, and exports; session-protected administration.
- Environment-based token, host, goal, and exam-date configuration.
- A Streamable HTTP MCP server for ChatGPT queries and task control.

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
  for tracker pages and API requests. It has no default; an empty value keeps
  those routes locked. Use a long random ASCII value and make sure any reverse
  proxy forwards the header unchanged. Django Admin uses its own staff login
  instead so normal browser navigation and form submissions work.
- `TRACKER_DAILY_TARGET_MINUTES`: daily target minutes shown on the dashboard.
- `TRACKER_WEEKLY_TARGET_MINUTES`: weekly target minutes shown on the dashboard.
- `TRACKER_EXAM_DATE`: countdown target date, formatted as `YYYY-MM-DD`.
- `MCP_HOST`: MCP listener address. Defaults to loopback (`127.0.0.1`).
- `MCP_PORT`: MCP listener port. Defaults to `8001`.
- `MCP_URL_KEY`: private URL segment used by a personal remote MCP endpoint.
  Use 24-128 letters, digits, underscores, or hyphens; 64 random hex characters
  are recommended.
- `MCP_ALLOW_UNAUTHENTICATED`: permits `/mcp` without a URL key. Leave this
  `false` unless the listener is loopback-only and reached through a trusted
  private tunnel.
- `LEARNING_REPO`: optional GitHub repository (for example
  `owner/study-learning-log`) where completed MCP task reports are committed.
- `LEARNING_REPO_PATH`: local checkout used for learning-log commits. If the
  checkout or remote repository does not exist, the authenticated `gh` CLI
  clones or creates a private repository automatically.

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

## ChatGPT MCP

The MCP process uses the same Django settings and SQLite database as the web
dashboard, but runs separately so its streaming HTTP lifecycle does not interfere
with the Django web server. It exposes these tools:

- `search` and `fetch`: ChatGPT-compatible knowledge retrieval.
- `get_tracker_status`: active task plus daily and weekly target progress.
- `list_recent_sessions` and `get_study_summary`: history and aggregate queries.
- `start_task`: starts `math`, `english`, `major`, or `training`.
- `stop_task`: ends the active task and stores the required summary/report. A
  session shorter than 25 minutes is discarded, matching the dashboard rule.

Apply the report-field migration and generate a personal URL key:

```bash
python manage.py migrate
openssl rand -hex 32
```

Put the generated value in `.env` as `MCP_URL_KEY`, then start the service:

```bash
python manage.py runmcp
```

The private endpoint is:

```text
http://127.0.0.1:8001/<MCP_URL_KEY>/mcp
```

ChatGPT requires a reachable HTTPS MCP URL. For local use, expose this loopback
service with OpenAI Secure MCP Tunnel or another HTTPS tunnel. For a server
deployment, reverse-proxy the endpoint with TLS, streaming/buffering disabled,
and access logging disabled for this route because the URL contains a credential.
Do not expose port 8001 directly to the internet.

To connect it in ChatGPT:

1. Open **Settings → Security and login** and enable Developer mode.
2. Open **Settings → Plugins**, create a developer-mode app, and enter
   `https://your-host/<MCP_URL_KEY>/mcp` as its MCP server URL.
3. In a new ordinary chat, choose the app from **+ → More**.

Example prompts include “我今天学习了多久？”, “开始数学任务”, and “结束任务，
总结：完成二次函数错题复盘，仍需整理第 3 题”. ChatGPT uses the tool annotations
to distinguish read-only lookups from changes and may ask for confirmation based
on the selected app permission level.

`MCP_URL_KEY` is a pragmatic credential for one private developer-mode app, not
a multi-user authentication system. Use OAuth before sharing or publishing the
integration. Never commit the key or include it in screenshots, shell history,
proxy logs, or support messages.

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

## Administration

Create an administrator account once on each new database:

```bash
python manage.py createsuperuser
```

Then open `http://127.0.0.1:8000/admin/` and sign in with that account. The
administration site is protected by Django's session-based staff login and does
not require the tracker `Authorization` header. When accessing the service by
its server IP, include that IP in `DJANGO_ALLOWED_HOSTS`.

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
