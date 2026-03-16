from flask import Flask, session

from .env import is_demo_mode, load_dotenv
from .routes import bp


def create_app() -> Flask:
    load_dotenv()
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "change-me"
    app.register_blueprint(bp)

    @app.context_processor
    def inject_ui_feedback() -> dict:
        return {
            "ui_feedback": session.get("ui_feedback"),
            "demo_mode": is_demo_mode(),
        }

    return app
