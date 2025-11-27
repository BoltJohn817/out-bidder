from flask import Flask
from flask_bcrypt import Bcrypt
from pymongo import MongoClient
import jwt

from config import Config

bcrypt = Bcrypt()


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

mongo_client = MongoClient(Config.MONGODB_URI)
db = mongo_client.get_default_database()


