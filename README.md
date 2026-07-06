# jkxx

A small Django time-tracking dashboard for study sessions.

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
