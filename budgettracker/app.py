import os
import sqlite3

from dotenv import load_dotenv
from flask import Flask
from sqlalchemy import event
from sqlalchemy.engine import Engine

load_dotenv()

from config import Config
from extensions import db, login_manager, migrate


@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Включает проверку внешних ключей для SQLite."""
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def create_app(test_config=None):
    """Создаёт и настраивает экземпляр Flask-приложения."""
    app = Flask(__name__)
    app.config.from_object(Config)

    if test_config:
        app.config.update(test_config)

    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)

    login_manager.login_view = "main.login"
    login_manager.login_message = "Для доступа к этой странице войдите в систему."
    login_manager.login_message_category = "warning"

    import models
    from routes import main_bp

    app.register_blueprint(main_bp)

    @app.context_processor
    def inject_env():
        """Передаёт переменные окружения в шаблоны."""
        return {"flask_env": app.config.get("FLASK_ENV", "development")}

    return app


app = create_app()


if __name__ == "__main__":
    app.run(
        host=os.getenv("FLASK_RUN_HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
        debug=app.config.get("FLASK_ENV") == "development",
    )
