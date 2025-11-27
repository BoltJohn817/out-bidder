from flask import Flask
from flask_bcrypt import Bcrypt
from flask_socketio import SocketIO
from pymongo import MongoClient
import jwt

from config import Config

bcrypt = Bcrypt()
# Configure SocketIO for Railway/production deployment
import os
# Detect Railway environment - Railway's proxy doesn't support WebSocket upgrades
is_railway = bool(os.getenv("RAILWAY_ENVIRONMENT_NAME") or os.getenv("RAILWAY"))

socketio = SocketIO(
    async_mode="gevent",
    cors_allowed_origins="*",
    # CRITICAL: Disable WebSocket upgrades on Railway - only polling works
    allow_upgrades=not is_railway,
    transports=["polling", "websocket"] if not is_railway else ["polling"],
    ping_timeout=60,
    ping_interval=25,
    max_http_buffer_size=1e6,
    # Enable logging to debug connection issues
    logger=True,
    engineio_logger=True,
)


class JWTManager:
    def __init__(self) -> None:
        self.secret: str | None = None

    def init_app(self, app: Flask) -> None:
        self.secret = app.config["JWT_SECRET_KEY"]

    def encode(self, payload: dict) -> str:
        if not self.secret:
            raise RuntimeError("JWTManager not initialized")
        return jwt.encode(payload, self.secret, algorithm="HS256")

    def decode(self, token: str) -> dict:
        if not self.secret:
            raise RuntimeError("JWTManager not initialized")
        return jwt.decode(token, self.secret, algorithms=["HS256"])


jwt_manager = JWTManager()

print(f"Connected to MongoDB: {Config.MONGODB_URI}")
mongo_client = MongoClient(Config.MONGODB_URI)
db = mongo_client.get_default_database()


