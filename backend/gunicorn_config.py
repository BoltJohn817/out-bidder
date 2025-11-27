"""Gunicorn configuration file for Flask-SocketIO application."""

import multiprocessing

# Server socket
# Azure Web Apps use PORT environment variable, fallback to 5001 for local dev
import os
port = os.getenv("PORT", "5001")
bind = f"0.0.0.0:{port}"
backlog = 2048

# Worker processes
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "gevent"  # Required for Flask-SocketIO (gevent has better Python 3.13 support)
worker_connections = 1000
timeout = 30
keepalive = 2

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