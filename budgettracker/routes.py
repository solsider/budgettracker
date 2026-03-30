from calendar import monthrange
from datetime import date, datetime
from decimal import Decimal
from urllib.parse import urlencode

import pandas as pd
from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import case, func

from extensions import db
from forms import CategoryDeleteForm, CategoryForm, ConfirmDeleteForm, LoginForm, RegisterForm, TransactionForm
from models import Category, Transaction, User
from utils.export import (
    TYPE_LABELS,
    build_transactions_dataframe,
    export_transactions_csv,
    export_transactions_excel,
    export_transactions_pdf,
    make_export_filename,
)

main_bp = Blueprint("main", __name__)


def _shift_months(base_date, delta_months):
    """Смещает дату на указанное число месяцев."""
    month_index = base_date.month - 1 + delta_months
    year = base_date.year + month_index // 12
    month = month_index % 12 + 1
    day = min(base_date.day, monthrange(year, month)[1])
    return date(year, month, day)


def _month_bounds(target_date):
    """Возвращает первый и последний день месяца."""
    start = target_date.replace(day=1)
    end = target_date.replace(day=monthrange(target_date.year, target_date.month)[1])
    return start, end


def _parse_date(value):
    """Безопасно преобразует строку в дату."""
    if not value:
        return None

    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _query_string_with_updates(**updates):
    """Возвращает query string с учётом новых параметров."""
    params = request.args.to_dict(flat=True)
    for key, value in updates.items():
        if value in (None, "", 0):
            params.pop(key, None)
        else:
            params[key] = value
    return urlencode(params)


def _get_filtered_transactions(user, args, include_pagination=True):
    """Фильтрует транзакции пользователя по параметрам запроса."""
    query = (
        Transaction.query.filter_by(user_id=user.id)
        .join(Category)
        .order_by(Transaction.date.desc(), Transaction.id.desc())
    )

    start_date = _parse_date(args.get("date_from"))
    end_date = _parse_date(args.get("date_to"))
    transaction_type = args.get("type") or ""
    category_id = args.get("category_id", type=int)

    if start_date:
        query = query.filter(Transaction.date >= start_date)
    if end_date:
        query = query.filter(Transaction.date <= end_date)
    if transaction_type:
        query = query.filter(Transaction.type == transaction_type)
    if category_id:
        query = query.filter(Transaction.category_id == category_id)

    filters = {
        "date_from": start_date.isoformat() if start_date else "",
        "date_to": end_date.isoformat() if end_date else "",
        "type": transaction_type,
        "type_label": TYPE_LABELS.get(transaction_type, "Все"),
        "category_id": category_id or "",
        "category_label": "Все",
    }

    if category_id:
        category = Category.query.filter_by(id=category_id, user_id=user.id).first()
        filters["category_label"] = category.name if category else "Все"

    if include_pagination:
        page = args.get("page", 1, type=int)
        per_page = args.get("per_page", 10, type=int)
        per_page = per_page if per_page in (10, 25, 50) else 10
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        return query, filters, pagination, per_page

    return query, filters


def _get_period_dates(period, custom_start=None, custom_end=None):
    """Определяет диапазон дат для аналитики."""
    today = date.today()

    if period == "previous_month":
        base = _shift_months(today.replace(day=1), -1)
        start, end = _month_bounds(base)
        label = f"Прошлый месяц ({start.strftime('%d.%m.%Y')} - {end.strftime('%d.%m.%Y')})"
        return start, end, label

    if period == "last_3_months":
        start = _shift_months(today.replace(day=1), -2)
        return start, today, f"Последние 3 месяца ({start.strftime('%d.%m.%Y')} - {today.strftime('%d.%m.%Y')})"

    if period == "last_6_months":
        start = _shift_months(today.replace(day=1), -5)
        return start, today, f"Последние 6 месяцев ({start.strftime('%d.%m.%Y')} - {today.strftime('%d.%m.%Y')})"

    if period == "year":
        start = date(today.year, 1, 1)
        return start, today, f"Текущий год ({start.strftime('%d.%m.%Y')} - {today.strftime('%d.%m.%Y')})"

    if period == "custom":
        start = _parse_date(custom_start) or today.replace(day=1)
        end = _parse_date(custom_end) or today
        if start > end:
            start, end = end, start
        return start, end, f"Произвольный период ({start.strftime('%d.%m.%Y')} - {end.strftime('%d.%m.%Y')})"

    start = today.replace(day=1)
    return start, today, f"Текущий месяц ({start.strftime('%d.%m.%Y')} - {today.strftime('%d.%m.%Y')})"


def _transactions_to_dataframe(user_id, start_date, end_date):
    """Загружает транзакции за период в DataFrame."""
    transactions = (
        db.session.query(Transaction, Category)
        .join(Category, Category.id == Transaction.category_id)
        .filter(Transaction.user_id == user_id, Transaction.date.between(start_date, end_date))
        .order_by(Transaction.date.asc(), Transaction.id.asc())
        .all()
    )

    rows = []
    for transaction, category in transactions:
        rows.append(
            {
                "id": transaction.id,
                "date": pd.to_datetime(transaction.date),
                "amount": float(transaction.amount),
                "type": transaction.type,
                "category_name": category.name,
                "description": transaction.description or "",
            }
        )

    if not rows:
        return pd.DataFrame(columns=["id", "date", "amount", "type", "category_name", "description"])

    return pd.DataFrame(rows)


def _build_analytics_payload(user, period, start_raw=None, end_raw=None):
    """Готовит агрегированные данные для аналитики и PDF-отчёта."""
    start_date, end_date, period_label = _get_period_dates(period, start_raw, end_raw)
    dataframe = _transactions_to_dataframe(user.id, start_date, end_date)

    expenses_by_category = {"labels": [], "values": [], "colors": []}
    monthly_summary = {"labels": [], "income": [], "expense": []}
    balance_trend = {"labels": [], "values": []}
    metrics = {
        "average_expense_per_day": "0.00",
        "largest_expense": "Нет данных",
        "top_expense_category": "Нет данных",
    }

    if not dataframe.empty:
        expense_df = dataframe[dataframe["type"] == "expense"].copy()
        if not expense_df.empty:
            grouped = (
                expense_df.groupby("category_name", as_index=False)["amount"]
                .sum()
                .sort_values("amount", ascending=False)
            )
            expense_colors = {
                category.name: category.color
                for category in Category.query.filter(
                    Category.user_id == user.id,
                    Category.type == "expense",
                ).all()
            }
            expenses_by_category = {
                "labels": grouped["category_name"].tolist(),
                "values": grouped["amount"].round(2).tolist(),
                "colors": [expense_colors.get(name, "#6c757d") for name in grouped["category_name"].tolist()],
            }

            total_days = max((end_date - start_date).days + 1, 1)
            metrics["average_expense_per_day"] = f"{expense_df['amount'].sum() / total_days:.2f}"
            largest_expense = expense_df.sort_values("amount", ascending=False).iloc[0]
            metrics["largest_expense"] = f"{largest_expense['amount']:.2f} ({largest_expense['category_name']})"
            metrics["top_expense_category"] = grouped.iloc[0]["category_name"] if not grouped.empty else "Нет данных"

        monthly_start = _shift_months(date.today().replace(day=1), -5)
        monthly_df = _transactions_to_dataframe(user.id, monthly_start, end_date)
        full_month_range = pd.period_range(start=monthly_start, end=end_date, freq="M")
        labels = [period.strftime("%m.%Y") for period in full_month_range.to_timestamp()]
        if not monthly_df.empty:
            monthly_df["month"] = monthly_df["date"].dt.to_period("M")
            grouped_months = (
                monthly_df.groupby(["month", "type"], as_index=False)["amount"]
                .sum()
                .pivot(index="month", columns="type", values="amount")
                .fillna(0)
                .reindex(full_month_range, fill_value=0)
                .sort_index()
            )
            monthly_summary = {
                "labels": labels,
                "income": grouped_months["income"].round(2).tolist() if "income" in grouped_months.columns else [0.0] * len(labels),
                "expense": grouped_months["expense"].round(2).tolist() if "expense" in grouped_months.columns else [0.0] * len(labels),
            }
        else:
            monthly_summary = {
                "labels": labels,
                "income": [0.0] * len(labels),
                "expense": [0.0] * len(labels),
            }

        signed_df = dataframe.copy()
        signed_df["signed_amount"] = signed_df.apply(
            lambda row: row["amount"] if row["type"] == "income" else -row["amount"],
            axis=1,
        )
        daily_series = signed_df.groupby(signed_df["date"].dt.date)["signed_amount"].sum()
        full_range = pd.date_range(start=start_date, end=end_date, freq="D")
        aligned_series = daily_series.reindex(full_range.date, fill_value=0.0)

        opening_balance = (
            db.session.query(
                func.coalesce(
                    func.sum(case((Transaction.type == "income", Transaction.amount), else_=-Transaction.amount)),
                    Decimal("0.00"),
                )
            )
            .filter(Transaction.user_id == user.id, Transaction.date < start_date)
            .scalar()
        )
        cumulative = aligned_series.cumsum() + float(opening_balance or 0)
        balance_trend = {
            "labels": [point.strftime("%d.%m") for point in full_range],
            "values": cumulative.round(2).tolist(),
        }

    return {
        "period_label": period_label,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "expenses_by_category": expenses_by_category,
        "monthly_summary": monthly_summary,
        "balance_trend": balance_trend,
        "metrics": metrics,
    }


def _prepare_transaction_form(form, user, selected_type=None):
    """Заполняет форму транзакции категориями пользователя."""
    categories = Category.query.filter_by(user_id=user.id).order_by(Category.type.asc(), Category.name.asc()).all()
    form.category_id.choices = [(category.id, category.name) for category in categories]

    selected_type = selected_type or form.type.data or "expense"
    matching_categories = [category for category in categories if category.type == selected_type]
    if matching_categories and not form.category_id.data:
        form.category_id.data = matching_categories[0].id

    return categories


@main_bp.route("/register", methods=["GET", "POST"])
def register():
    """Регистрирует нового пользователя."""
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    form = RegisterForm()
    if form.validate_on_submit():
        existing_user = User.query.filter(func.lower(User.username) == form.username.data.lower()).first()
        if existing_user:
            flash("Пользователь с таким именем уже существует.", "danger")
            return render_template("register.html", form=form)

        user = User(username=form.username.data.strip())
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.flush()
        user.create_default_categories()
        db.session.commit()
        flash("Регистрация прошла успешно. Теперь войдите в аккаунт.", "success")
        return redirect(url_for("main.login"))

    return render_template("register.html", form=form)


@main_bp.route("/login", methods=["GET", "POST"])
def login():
    """Авторизует пользователя."""
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter(func.lower(User.username) == form.username.data.lower()).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            flash("Вы вошли в систему.", "success")
            next_url = request.args.get("next")
            return redirect(next_url or url_for("main.index"))

        flash("Неверное имя пользователя или пароль.", "danger")

    return render_template("login.html", form=form)


@main_bp.route("/logout")
@login_required
def logout():
    """Завершает сессию пользователя."""
    logout_user()
    flash("Вы вышли из аккаунта.", "info")
    return redirect(url_for("main.login"))


@main_bp.route("/")
@login_required
def index():
    """Отображает главную страницу пользователя."""
    today = date.today()
    start_month = today.replace(day=1)
    end_month = _month_bounds(today)[1]

    current_month_income = (
        db.session.query(func.coalesce(func.sum(Transaction.amount), Decimal("0.00")))
        .filter(
            Transaction.user_id == current_user.id,
            Transaction.type == "income",
            Transaction.date.between(start_month, end_month),
        )
        .scalar()
    )
    current_month_expense = (
        db.session.query(func.coalesce(func.sum(Transaction.amount), Decimal("0.00")))
        .filter(
            Transaction.user_id == current_user.id,
            Transaction.type == "expense",
            Transaction.date.between(start_month, end_month),
        )
        .scalar()
    )

    recent_transactions = (
        Transaction.query.filter_by(user_id=current_user.id)
        .order_by(Transaction.date.desc(), Transaction.id.desc())
        .limit(10)
        .all()
    )

    return render_template(
        "index.html",
        balance=current_user.balance,
        current_month_income=current_month_income,
        current_month_expense=current_month_expense,
        recent_transactions=recent_transactions,
    )


@main_bp.route("/transactions")
@login_required
def transactions():
    """Показывает список транзакций с фильтрами."""
    query, filters, pagination, per_page = _get_filtered_transactions(current_user, request.args)
    categories = Category.query.filter_by(user_id=current_user.id).order_by(Category.name.asc()).all()
    delete_form = ConfirmDeleteForm()

    return render_template(
        "transactions.html",
        pagination=pagination,
        filters=filters,
        categories=categories,
        per_page=per_page,
        delete_form=delete_form,
        query_string_with_updates=_query_string_with_updates,
    )


@main_bp.route("/transaction/add", methods=["GET", "POST"])
@login_required
def add_transaction():
    """Создаёт новую транзакцию."""
    form = TransactionForm()
    categories = _prepare_transaction_form(form, current_user, request.values.get("type"))

    if form.validate_on_submit():
        category = Category.query.filter_by(id=form.category_id.data, user_id=current_user.id).first()
        if not category or category.type != form.type.data:
            flash("Выберите корректную категорию для указанного типа операции.", "danger")
            return render_template("transaction_form.html", form=form, categories=categories, transaction=None)

        transaction = Transaction(
            user_id=current_user.id,
            amount=form.amount.data,
            category_id=category.id,
            description=form.description.data.strip() if form.description.data else None,
            date=form.date.data,
            type=form.type.data,
        )
        db.session.add(transaction)
        current_user.recalculate_balance()
        db.session.commit()
        flash("Транзакция добавлена.", "success")
        return redirect(url_for("main.transactions"))

    return render_template("transaction_form.html", form=form, categories=categories, transaction=None)


@main_bp.route("/transaction/<int:transaction_id>/edit", methods=["GET", "POST"])
@login_required
def edit_transaction(transaction_id):
    """Редактирует существующую транзакцию."""
    transaction = Transaction.query.filter_by(id=transaction_id, user_id=current_user.id).first_or_404()
    form = TransactionForm()

    if request.method == "GET":
        form.type.data = transaction.type
        form.category_id.data = transaction.category_id
        form.amount.data = transaction.amount
        form.date.data = transaction.date
        form.description.data = transaction.description

    categories = _prepare_transaction_form(form, current_user, request.values.get("type", transaction.type))

    if form.validate_on_submit():
        category = Category.query.filter_by(id=form.category_id.data, user_id=current_user.id).first()
        if not category or category.type != form.type.data:
            flash("Категория не соответствует выбранному типу операции.", "danger")
            return render_template("transaction_form.html", form=form, categories=categories, transaction=transaction)

        transaction.type = form.type.data
        transaction.category_id = category.id
        transaction.amount = form.amount.data
        transaction.date = form.date.data
        transaction.description = form.description.data.strip() if form.description.data else None
        current_user.recalculate_balance()
        db.session.commit()
        flash("Транзакция обновлена.", "success")
        return redirect(url_for("main.transactions"))

    return render_template("transaction_form.html", form=form, categories=categories, transaction=transaction)


@main_bp.route("/transaction/<int:transaction_id>/delete", methods=["POST"])
@login_required
def delete_transaction(transaction_id):
    """Удаляет транзакцию пользователя."""
    form = ConfirmDeleteForm()
    if not form.validate_on_submit():
        abort(400)

    transaction = Transaction.query.filter_by(id=transaction_id, user_id=current_user.id).first_or_404()
    db.session.delete(transaction)
    current_user.recalculate_balance()
    db.session.commit()
    flash("Транзакция удалена.", "info")
    return redirect(url_for("main.transactions"))


@main_bp.route("/categories")
@login_required
def categories():
    """Отображает категории пользователя."""
    items = Category.query.filter_by(user_id=current_user.id).order_by(Category.type.asc(), Category.name.asc()).all()
    return render_template("categories.html", categories=items)


@main_bp.route("/category/add", methods=["GET", "POST"])
@login_required
def add_category():
    """Создаёт категорию пользователя."""
    form = CategoryForm(color="#6c757d")
    if form.validate_on_submit():
        duplicate = Category.query.filter_by(
            user_id=current_user.id,
            name=form.name.data.strip(),
            type=form.type.data,
        ).first()
        if duplicate:
            flash("Такая категория уже существует.", "danger")
            return render_template("category_form.html", form=form, category=None)

        category = Category(
            user_id=current_user.id,
            name=form.name.data.strip(),
            type=form.type.data,
            color=form.color.data,
        )
        db.session.add(category)
        db.session.commit()
        flash("Категория создана.", "success")
        return redirect(url_for("main.categories"))

    return render_template("category_form.html", form=form, category=None)


@main_bp.route("/category/<int:category_id>/edit", methods=["GET", "POST"])
@login_required
def edit_category(category_id):
    """Редактирует категорию пользователя."""
    category = Category.query.filter_by(id=category_id, user_id=current_user.id).first_or_404()
    form = CategoryForm(obj=category)

    if request.method == "GET":
        form.name.data = category.name
        form.type.data = category.type
        form.color.data = category.color

    if form.validate_on_submit():
        duplicate = (
            Category.query.filter_by(
                user_id=current_user.id,
                name=form.name.data.strip(),
                type=form.type.data,
            )
            .filter(Category.id != category.id)
            .first()
        )
        if duplicate:
            flash("Категория с таким именем и типом уже существует.", "danger")
            return render_template("category_form.html", form=form, category=category)

        if category.transactions.count() and form.type.data != category.type:
            flash("Нельзя менять тип категории, пока к ней привязаны транзакции.", "warning")
            return render_template("category_form.html", form=form, category=category)

        category.name = form.name.data.strip()
        category.type = form.type.data
        category.color = form.color.data
        db.session.commit()
        flash("Категория обновлена.", "success")
        return redirect(url_for("main.categories"))

    return render_template("category_form.html", form=form, category=category)


@main_bp.route("/category/<int:category_id>/delete", methods=["GET", "POST"])
@login_required
def delete_category(category_id):
    """Удаляет категорию или переназначает связанные транзакции."""
    category = Category.query.filter_by(id=category_id, user_id=current_user.id).first_or_404()
    form = CategoryDeleteForm()
    replacement_categories = (
        Category.query.filter_by(user_id=current_user.id, type=category.type)
        .filter(Category.id != category.id)
        .order_by(Category.name.asc())
        .all()
    )
    form.replacement_category_id.choices = [(None, "Не выбрано")] + [(item.id, item.name) for item in replacement_categories]
    linked_count = category.transactions.count()

    if form.validate_on_submit():
        if linked_count and not form.replacement_category_id.data:
            flash("У категории есть транзакции. Выберите новую категорию для переназначения.", "warning")
            return render_template("category_delete.html", category=category, form=form, linked_count=linked_count)

        if linked_count and form.replacement_category_id.data:
            replacement = Category.query.filter_by(
                id=form.replacement_category_id.data,
                user_id=current_user.id,
                type=category.type,
            ).first()
            if not replacement:
                flash("Не удалось найти выбранную категорию для переназначения.", "danger")
                return render_template("category_delete.html", category=category, form=form, linked_count=linked_count)

            Transaction.query.filter_by(category_id=category.id, user_id=current_user.id).update(
                {"category_id": replacement.id},
                synchronize_session=False,
            )

        db.session.delete(category)
        current_user.recalculate_balance()
        db.session.commit()
        flash("Категория удалена.", "info")
        return redirect(url_for("main.categories"))

    return render_template("category_delete.html", category=category, form=form, linked_count=linked_count)


@main_bp.route("/analytics")
@login_required
def analytics():
    """Отображает страницу аналитики."""
    today = date.today()
    return render_template(
        "analytics.html",
        default_start=today.replace(day=1).isoformat(),
        default_end=today.isoformat(),
    )


@main_bp.route("/api/analytics/data")
@login_required
def analytics_data():
    """Возвращает данные для графиков и метрик."""
    chart_type = request.args.get("type", "expenses_by_category")
    period = request.args.get("period", "current_month")
    payload = _build_analytics_payload(
        current_user,
        period,
        request.args.get("start"),
        request.args.get("end"),
    )

    if chart_type == "all":
        return jsonify(payload)
    if chart_type in payload:
        return jsonify(payload[chart_type])

    return jsonify({"error": "Неизвестный тип аналитики."}), 400


def _export_response(content_stream, mimetype, extension):
    """Отправляет пользователю сформированный файл."""
    return send_file(
        content_stream,
        mimetype=mimetype,
        as_attachment=True,
        download_name=make_export_filename(extension),
    )


@main_bp.route("/export/csv")
@login_required
def export_csv():
    """Экспортирует транзакции в CSV."""
    query, filters = _get_filtered_transactions(current_user, request.args, include_pagination=False)
    dataframe = build_transactions_dataframe(query.all())
    return _export_response(export_transactions_csv(dataframe), "text/csv; charset=utf-8", "csv")


@main_bp.route("/export/excel")
@login_required
def export_excel():
    """Экспортирует транзакции в Excel."""
    query, filters = _get_filtered_transactions(current_user, request.args, include_pagination=False)
    dataframe = build_transactions_dataframe(query.all())
    return _export_response(
        export_transactions_excel(dataframe),
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "xlsx",
    )


@main_bp.route("/export/pdf")
@login_required
def export_pdf():
    """Экспортирует транзакции и аналитику в PDF."""
    query, filters = _get_filtered_transactions(current_user, request.args, include_pagination=False)
    transactions = query.all()
    dataframe = build_transactions_dataframe(transactions)

    period = "custom" if filters["date_from"] or filters["date_to"] else "current_month"
    analytics_payload = _build_analytics_payload(
        current_user,
        period,
        filters["date_from"],
        filters["date_to"],
    )
    pdf_stream = export_transactions_pdf(dataframe, filters, analytics_payload)
    return _export_response(pdf_stream, "application/pdf", "pdf")
