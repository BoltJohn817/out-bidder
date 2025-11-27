from flask import Flask
from flask_bcrypt import Bcrypt
from flask_socketio import SocketIO
from pymongo import MongoClient
import jwt
import ssl
import sys

from config import Config

bcrypt = Bcrypt()
socketio = SocketIO(async_mode="gevent", cors_allowed_origins="*")


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

# Configure MongoDB client with proper SSL/TLS settings for Python 3.13
# This fixes SSL handshake issues with MongoDB Atlas
mongodb_uri = Config.MONGODB_URI

# For MongoDB Atlas (connection strings with mongodb+srv://), add connection parameters
# Python 3.13 has stricter SSL/TLS requirements
if "mongodb+srv://" in mongodb_uri or ".mongodb.net" in mongodb_uri:
    # Python 3.13 compatibility: Create SSL context that works with MongoDB Atlas
    # The issue is that Python 3.13's default SSL context is too strict
    try:
        # Try to create a compatible SSL context
        ssl_context = ssl.create_default_context()
        # For Python 3.13, we need to ensure TLS 1.2+ is supported
        if sys.version_info >= (3, 13):
            # Python 3.13: Set minimum TLS version explicitly
            if hasattr(ssl, 'TLSVersion'):
                ssl_context.minimum_version = ssl.TLSVersion.TLSv1_2
        else:
            # Older Python versions
            ssl_context.check_hostname = True
            ssl_context.verify_mode = ssl.CERT_REQUIRED
        
        mongo_client = MongoClient(
            mongodb_uri,
            serverSelectionTimeoutMS=30000,  # 30 seconds
            connectTimeoutMS=30000,
            socketTimeoutMS=30000,
            retryWrites=True,
            retryReads=True,
            ssl_context=ssl_context,
        )
    except Exception as e:
        # Fallback: Let pymongo handle SSL automatically
        print(f"Warning: Could not set custom SSL context: {e}. Using default.")
        mongo_client = MongoClient(
            mongodb_uri,
            serverSelectionTimeoutMS=30000,
            connectTimeoutMS=30000,
            socketTimeoutMS=30000,
            retryWrites=True,
            retryReads=True,
        )
else:
    # For local MongoDB without SSL
    mongo_client = MongoClient(
        mongodb_uri,
        serverSelectionTimeoutMS=30000,
        connectTimeoutMS=30000,
        socketTimeoutMS=30000,
    )

db = mongo_client.get_default_database()


