"""Gunicorn configuration file for Flask-SocketIO application."""

import multiprocessing
import os

# Server socket
# Use PORT environment variable if available (Railway, Heroku, etc.), otherwise default to 5001
port = os.getenv("PORT", "5001")
bind = f"0.0.0.0:{port}"
backlog = 2048

# Worker processes
# Use conservative defaults for Railway/cloud deployments (limited memory)
# Override with GUNICORN_WORKERS env var if needed
default_workers = os.getenv("GUNICORN_WORKERS")
if default_workers:
    workers = int(default_workers)
else:
    # Conservative default: 2 workers for cloud (Railway typically has 512MB-1GB RAM)
    # This prevents OOM (Out of Memory) issues on Railway's free tier
    # For local dev with more resources, set GUNICORN_WORKERS env var
    workers = 2

worker_class = "gevent"  # Required for Flask-SocketIO
# Reduced worker_connections for memory efficiency on Railway
worker_connections = int(os.getenv("GUNICORN_WORKER_CONNECTIONS", "100"))
timeout = 30
keepalive = 2
# Restart workers periodically to prevent memory leaks
max_requests = int(os.getenv("GUNICORN_MAX_REQUESTS", "1000"))
max_requests_jitter = int(os.getenv("GUNICORN_MAX_REQUESTS_JITTER", "50"))

# Logging
accesslog = "-"  # Log to stdout
errorlog = "-"  # Log to stderr
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process naming
proc_name = "outbidder_backend"

# Server mechanics
daemon = False
pidfile = None
umask = 0
user = None
group = None
tmp_upload_dir = None

# SSL (uncomment if needed)
# keyfile = None
# certfile = None

import psutil

def post_worker_init(worker):
    process = psutil.Process(os.getpid())
    rss = process.memory_info().rss / (1024 * 1024)
    worker.log.info(f"[INIT] Worker PID={os.getpid()} Memory={rss:.2f} MB")

def worker_int(worker):
    process = psutil.Process(os.getpid())
    rss = process.memory_info().rss / (1024 * 1024)
    worker.log.info(f"[INT] Worker PID={os.getpid()} Memory={rss:.2f} MB")