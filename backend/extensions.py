from flask import Flask
from flask_bcrypt import Bcrypt
from flask_socketio import SocketIO
from pymongo import MongoClient
import jwt

from config import Config

bcrypt = Bcrypt()
# Configure SocketIO for Railway/production deployment
# Allow both polling and websocket transports for better compatibility
socketio = SocketIO(
    async_mode="gevent",
    cors_allowed_origins="*",
    allow_upgrades=True,
    transports=["polling", "websocket"],
    ping_timeout=60,
    ping_interval=25,
    max_http_buffer_size=1e6,
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


