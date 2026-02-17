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

    # Cleanup old job statuses on startup to prevent memory accumulation
    try:
        from models import cleanup_old_job_statuses
        deleted_count = cleanup_old_job_statuses(days_old=7)
        if deleted_count > 0:
            app.logger.info(f"Cleaned up {deleted_count} old job statuses on startup")
    except Exception:
        # Silently fail cleanup on startup - not critical
        pass

    # Blueprints
    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(profile_bp, url_prefix="/api/profiles")
    app.register_blueprint(bid_bp, url_prefix="/api/bids")

    return app


# Vercel looks for a variable named `app`; gunicorn traditionally uses `application`.
app = create_app()
application = app  # alias kept for gunicorn compatibility

if __name__ == "__main__":
    application.run(host="0.0.0.0", port=5001, debug=True)


