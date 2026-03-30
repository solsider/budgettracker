from datetime import date
from decimal import Decimal

from app import db
from models import Category, Transaction, User


def login(client, username="tester", password="secret123"):
    """Выполняет вход тестового пользователя."""
    return client.post(
        "/login",
        data={"username": username, "password": password},
        follow_redirects=True,
    )


def test_user_creation_and_default_categories(app_instance):
    """Проверяет создание пользователя и предустановленных категорий."""
    with app_instance.app_context():
        user = User(username="alice")
        user.set_password("password123")
        db.session.add(user)
        db.session.flush()
        user.create_default_categories()
        db.session.commit()

        assert user.check_password("password123")
        assert user.categories.count() == 11


def test_balance_recalculation(app_instance, user):
    """Проверяет корректность пересчёта баланса."""
    with app_instance.app_context():
        user = User.query.filter_by(username="tester").first()
        income_category = Category.query.filter_by(user_id=user.id, type="income").first()
        expense_category = Category.query.filter_by(user_id=user.id, type="expense").first()

        db.session.add(
            Transaction(
                user_id=user.id,
                amount=Decimal("150.00"),
                category_id=income_category.id,
                date=date.today(),
                type="income",
            )
        )
        db.session.add(
            Transaction(
                user_id=user.id,
                amount=Decimal("80.00"),
                category_id=expense_category.id,
                date=date.today(),
                type="expense",
            )
        )
        user.recalculate_balance()
        db.session.commit()

        assert user.balance == Decimal("70.00")


def test_requires_login_redirect(client):
    """Проверяет редирект неавторизованного пользователя на страницу входа."""
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_login_route(client, user):
    """Проверяет успешный вход пользователя."""
    response = login(client)
    assert response.status_code == 200
    assert "Вы вошли в систему.".encode("utf-8") in response.data


def test_add_transaction_route(client, app_instance, user):
    """Проверяет создание транзакции через маршрут."""
    with app_instance.app_context():
        income_category = Category.query.filter_by(type="income").first()

    login(client)
    response = client.post(
        "/transaction/add",
        data={
            "type": "income",
            "category_id": income_category.id,
            "amount": "250.00",
            "date": date.today().isoformat(),
            "description": "Тестовый доход",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    with app_instance.app_context():
        account = User.query.filter_by(username="tester").first()
        transaction = Transaction.query.filter_by(description="Тестовый доход").first()
        assert transaction is not None
        assert account.balance == Decimal("250.00")


def test_export_csv_contains_headers(client, app_instance, user):
    """Проверяет CSV-экспорт и русские заголовки."""
    with app_instance.app_context():
        expense_category = Category.query.filter_by(type="expense").first()
        db.session.add(
            Transaction(
                user_id=user.id,
                amount=Decimal("55.00"),
                category_id=expense_category.id,
                date=date.today(),
                type="expense",
                description="Обед",
            )
        )
        user.recalculate_balance()
        db.session.commit()

    login(client)
    response = client.get("/export/csv")

    assert response.status_code == 200
    content = response.data.decode("utf-8-sig")
    assert "Дата,Тип,Категория,Сумма,Описание" in content
