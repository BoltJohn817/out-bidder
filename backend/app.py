from flask import Flask
from flask_cors import CORS

from config import Config
from extensions import bcrypt, jwt_manager, mongo_client, socketio
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
    socketio.init_app(app, cors_allowed_origins="*")

    # Make Mongo client available via app
    app.mongo_client = mongo_client  # type: ignore[attr-defined]

    # Blueprints
    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(profile_bp, url_prefix="/api/profiles")
    app.register_blueprint(bid_bp, url_prefix="/api/bids")

    return app


if __name__ == "__main__":
    application = create_app()
    socketio.run(application, host="0.0.0.0", port=5001, debug=True)


