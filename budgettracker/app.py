import os
import sqlite3
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask
from sqlalchemy import event, inspect
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

    with app.app_context():
        _ensure_database_initialized(app)

    @app.context_processor
    def inject_env():
        """Передаёт переменные окружения в шаблоны."""
        return {"flask_env": app.config.get("FLASK_ENV", "development")}

    return app


def _ensure_database_initialized(app):
    """Создаёт таблицы автоматически для локальной SQLite-базы, если схема ещё не инициализирована."""
    database_uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
    if not database_uri.startswith("sqlite"):
        return

    _ensure_sqlite_storage_path(app, database_uri)

    inspector = inspect(db.engine)
    if inspector.has_table("users"):
        return

    # Для локальной разработки приложение должно стартовать даже без ручного запуска миграций.
    db.create_all()


def _ensure_sqlite_storage_path(app, database_uri):
    """Гарантирует, что каталог для SQLite-файла существует до первого подключения."""
    sqlite_prefix = "sqlite:///"
    if not database_uri.startswith(sqlite_prefix):
        return

    database_path = database_uri[len(sqlite_prefix):]
    if not database_path or database_path == ":memory:":
        return

    # Относительный путь SQLite во Flask обычно живёт внутри instance-папки.
    if not Path(database_path).is_absolute():
        Path(app.instance_path).mkdir(parents=True, exist_ok=True)
        return

    Path(database_path).parent.mkdir(parents=True, exist_ok=True)


app = create_app()


if __name__ == "__main__":
    app.run(
        host=os.getenv("FLASK_RUN_HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
        debug=app.config.get("FLASK_ENV") == "development",
    )
