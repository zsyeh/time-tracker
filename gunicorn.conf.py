import multiprocessing
import os


bind = os.environ.get('GUNICORN_BIND', '127.0.0.1:8000')
workers = int(os.environ.get('GUNICORN_WORKERS', min(4, multiprocessing.cpu_count() * 2 + 1)))
worker_class = 'sync'
timeout = 60
graceful_timeout = 30
keepalive = 5

# Launch Token credentials occur in request paths. Nginx is responsible for
# ordinary access logging and explicitly suppresses launch endpoints.
accesslog = None
errorlog = '-'
loglevel = os.environ.get('GUNICORN_LOG_LEVEL', 'info')
