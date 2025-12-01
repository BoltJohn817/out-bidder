from flask import Flask
from flask_cors import CORS

from config import Config
from extensions import bcrypt, jwt_manager, mongo_client
from routes.auth_routes import auth_bp
from routes.profile_routes import profile_bp
from routes.bid_routes import bid_bp


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)

    # Extensions
    bcrypt.init_app(app)
    jwt_manager.init_app(app)
    CORS(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=True)

    # Make Mongo client available via app
    app.mongo_client = mongo_client  # type: ignore[attr-defined]

    # Create database indexes on startup (idempotent operation)
    try:
        from utils.db_indexes import create_indexes
        create_indexes()
    except Exception:
        # Silently fail if indexes already exist or on first run
        pass

    # Blueprints
    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(profile_bp, url_prefix="/api/profiles")
    app.register_blueprint(bid_bp, url_prefix="/api/bids")

    return app


# Create application instance for gunicorn
application = create_app()

if __name__ == "__main__":
    application.run(host="0.0.0.0", port=5001, debug=True)


