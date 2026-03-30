import sys
from pathlib import Path

import pytest
from sqlalchemy.pool import StaticPool

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app, db
from models import User


@pytest.fixture
def app_instance():
    """Создаёт тестовый экземпляр приложения с in-memory SQLite."""
    app = create_app(
        {
            "TESTING": True,
            "WTF_CSRF_ENABLED": False,
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "SQLALCHEMY_ENGINE_OPTIONS": {
                "connect_args": {"check_same_thread": False},
                "poolclass": StaticPool,
            },
        }
    )

    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app_instance):
    """Возвращает тестовый HTTP-клиент."""
    return app_instance.test_client()


@pytest.fixture
def user(app_instance):
    """Создаёт тестового пользователя с базовыми категориями."""
    with app_instance.app_context():
        account = User(username="tester")
        account.set_password("secret123")
        db.session.add(account)
        db.session.flush()
        account.create_default_categories()
        db.session.commit()
        return account
