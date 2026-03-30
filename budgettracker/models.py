from decimal import Decimal

from flask_login import UserMixin
from sqlalchemy import Numeric, UniqueConstraint, func
from werkzeug.security import check_password_hash, generate_password_hash

from extensions import db, login_manager

DEFAULT_CATEGORIES = {
    "income": [
        ("Зарплата", "#198754"),
        ("Фриланс", "#20c997"),
        ("Подарки", "#0dcaf0"),
        ("Другое", "#6c757d"),
    ],
    "expense": [
        ("Еда", "#dc3545"),
        ("Транспорт", "#fd7e14"),
        ("Жильё", "#6f42c1"),
        ("Развлечения", "#d63384"),
        ("Здоровье", "#0d6efd"),
        ("Образование", "#198754"),
        ("Другое", "#6c757d"),
    ],
}


@login_manager.user_loader
def load_user(user_id):
    """Загружает пользователя для Flask-Login."""
    return User.query.get(int(user_id))


class User(UserMixin, db.Model):
    """Модель пользователя."""

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    balance = db.Column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    transactions = db.relationship(
        "Transaction",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )
    categories = db.relationship(
        "Category",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    def set_password(self, password):
        """Сохраняет хэш пароля пользователя."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Проверяет пароль пользователя."""
        return check_password_hash(self.password_hash, password)

    def create_default_categories(self):
        """Создаёт предустановленные категории для нового пользователя."""
        for category_type, items in DEFAULT_CATEGORIES.items():
            for name, color in items:
                db.session.add(
                    Category(user=self, name=name, type=category_type, color=color)
                )

    def recalculate_balance(self):
        """Пересчитывает баланс пользователя на основе транзакций."""
        income_total = (
            db.session.query(func.coalesce(func.sum(Transaction.amount), Decimal("0.00")))
            .filter_by(user_id=self.id, type="income")
            .scalar()
        )
        expense_total = (
            db.session.query(func.coalesce(func.sum(Transaction.amount), Decimal("0.00")))
            .filter_by(user_id=self.id, type="expense")
            .scalar()
        )
        self.balance = Decimal(income_total or 0) - Decimal(expense_total or 0)
        return self.balance


class Category(db.Model):
    """Модель категории."""

    __tablename__ = "categories"
    __table_args__ = (
        UniqueConstraint("user_id", "name", "type", name="uq_category_user_name_type"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    type = db.Column(db.String(20), nullable=False)
    color = db.Column(db.String(7), nullable=False, default="#6c757d")
    user = db.relationship("User", back_populates="categories")
    transactions = db.relationship("Transaction", back_populates="category", lazy="dynamic")


class Transaction(db.Model):
    """Модель финансовой транзакции."""

    __tablename__ = "transactions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    amount = db.Column(Numeric(12, 2), nullable=False)
    category_id = db.Column(
        db.Integer,
        db.ForeignKey("categories.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    description = db.Column(db.String(255))
    date = db.Column(db.Date, nullable=False, index=True)
    type = db.Column(db.String(20), nullable=False, index=True)
    user = db.relationship("User", back_populates="transactions")
    category = db.relationship("Category", back_populates="transactions")
