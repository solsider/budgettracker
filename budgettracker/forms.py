from datetime import date

from flask_wtf import FlaskForm
from wtforms import (
    DateField,
    DecimalField,
    PasswordField,
    RadioField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import DataRequired, EqualTo, Length, NumberRange, Optional


def optional_int(value):
    """Преобразует значение select в число или None."""
    return int(value) if value not in (None, "", "None") else None


class RegisterForm(FlaskForm):
    """Форма регистрации пользователя."""

    username = StringField(
        "Имя пользователя",
        validators=[DataRequired(), Length(min=3, max=80)],
    )
    password = PasswordField(
        "Пароль",
        validators=[DataRequired(), Length(min=6, max=128)],
    )
    confirm_password = PasswordField(
        "Подтверждение пароля",
        validators=[DataRequired(), EqualTo("password")],
    )
    submit = SubmitField("Зарегистрироваться")


class LoginForm(FlaskForm):
    """Форма входа пользователя."""

    username = StringField("Имя пользователя", validators=[DataRequired()])
    password = PasswordField("Пароль", validators=[DataRequired()])
    submit = SubmitField("Войти")


class TransactionForm(FlaskForm):
    """Форма создания и редактирования транзакции."""

    type = RadioField(
        "Тип операции",
        choices=[("income", "Доход"), ("expense", "Расход")],
        validators=[DataRequired()],
        default="expense",
    )
    category_id = SelectField(
        "Категория",
        coerce=int,
        choices=[],
        validators=[DataRequired()],
        validate_choice=False,
    )
    amount = DecimalField(
        "Сумма",
        places=2,
        validators=[DataRequired(), NumberRange(min=0.01)],
    )
    date = DateField(
        "Дата",
        validators=[DataRequired()],
        default=date.today,
        format="%Y-%m-%d",
    )
    description = TextAreaField("Описание", validators=[Optional(), Length(max=255)])
    submit = SubmitField("Сохранить")


class CategoryForm(FlaskForm):
    """Форма категории."""

    name = StringField(
        "Название категории",
        validators=[DataRequired(), Length(min=2, max=120)],
    )
    type = RadioField(
        "Тип категории",
        choices=[("income", "Доход"), ("expense", "Расход")],
        validators=[DataRequired()],
        default="expense",
    )
    color = StringField("Цвет", validators=[DataRequired(), Length(min=4, max=7)])
    submit = SubmitField("Сохранить")


class CategoryDeleteForm(FlaskForm):
    """Форма удаления категории с возможным переназначением."""

    replacement_category_id = SelectField(
        "Переназначить транзакции в категорию",
        coerce=optional_int,
        choices=[],
        validators=[Optional()],
        validate_choice=False,
    )
    submit = SubmitField("Подтвердить удаление")


class ConfirmDeleteForm(FlaskForm):
    """Универсальная форма подтверждения удаления."""

    submit = SubmitField("Удалить")
