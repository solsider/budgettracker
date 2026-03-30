import os


class Config:
    """Базовая конфигурация приложения."""

    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-me")
    FLASK_ENV = os.getenv("FLASK_ENV", "development")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///budgettracker.db").replace(
        "postgres://", "postgresql://", 1
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    ITEMS_PER_PAGE_OPTIONS = [10, 25, 50]


class TestConfig(Config):
    """Конфигурация для тестов."""

    TESTING = True
    WTF_CSRF_ENABLED = False
