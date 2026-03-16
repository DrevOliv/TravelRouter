from flask import Flask, session

from .routes import bp


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "change-me"
    app.register_blueprint(bp)

    @app.context_processor
    def inject_ui_feedback() -> dict:
        return {"ui_feedback": session.get("ui_feedback")}

    return app
