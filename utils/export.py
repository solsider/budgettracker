import io
import os
from datetime import datetime

import pandas as pd
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.linecharts import HorizontalLineChart
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.shapes import Drawing, String
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

TYPE_LABELS = {"income": "Доход", "expense": "Расход"}
CHART_COLORS = [
    "#0d6efd",
    "#198754",
    "#dc3545",
    "#ffc107",
    "#20c997",
    "#6f42c1",
    "#fd7e14",
    "#6c757d",
]


def make_export_filename(extension):
    """Возвращает имя файла экспорта с текущими датой и временем."""
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    return f"BudgetTracker_отчет_{stamp}.{extension}"


def build_transactions_dataframe(transactions):
    """Собирает DataFrame для экспорта транзакций."""
    rows = []
    for transaction in transactions:
        rows.append(
            {
                "Дата": transaction.date.strftime("%d.%m.%Y"),
                "Тип": TYPE_LABELS.get(transaction.type, transaction.type),
                "Категория": transaction.category.name,
                "Сумма": float(transaction.amount),
                "Описание": transaction.description or "",
            }
        )
    return pd.DataFrame(rows, columns=["Дата", "Тип", "Категория", "Сумма", "Описание"])


def export_transactions_csv(dataframe):
    """Формирует CSV-отчёт."""
    stream = io.StringIO()
    dataframe.to_csv(stream, index=False)
    return io.BytesIO(stream.getvalue().encode("utf-8-sig"))


def export_transactions_excel(dataframe):
    """Формирует Excel-отчёт."""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        dataframe.to_excel(writer, sheet_name="Транзакции", index=False)
    output.seek(0)
    return output


def _register_font():
    """Регистрирует шрифт с поддержкой кириллицы."""
    candidates = [
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "DejaVuSans"),
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "DejaVuSans-Bold"),
        ("C:\\Windows\\Fonts\\arial.ttf", "Arial"),
        ("C:\\Windows\\Fonts\\arialbd.ttf", "Arial-Bold"),
    ]

    regular_font = "Helvetica"
    bold_font = "Helvetica-Bold"

    for path, name in candidates:
        if os.path.exists(path):
            if name not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont(name, path))
            if "Bold" in name or "bd" in path.lower():
                bold_font = name
            else:
                regular_font = name

    return regular_font, bold_font


def _build_pie_chart(labels, values, font_name):
    """Создаёт круговую диаграмму расходов."""
    drawing = Drawing(420, 220)
    drawing.add(String(10, 205, "Расходы по категориям", fontSize=14, fontName=font_name))

    if not values:
        drawing.add(String(10, 100, "Нет данных для построения диаграммы.", fontSize=12, fontName=font_name))
        return drawing

    chart = Pie()
    chart.x = 120
    chart.y = 20
    chart.width = 150
    chart.height = 150
    chart.data = values
    chart.labels = labels
    chart.sideLabels = True
    chart.slices.fontName = font_name
    for index, _ in enumerate(values):
        chart.slices[index].fillColor = colors.HexColor(CHART_COLORS[index % len(CHART_COLORS)])
    drawing.add(chart)
    return drawing


def _build_bar_chart(labels, income_values, expense_values, font_name):
    """Создаёт столбчатую диаграмму по месяцам."""
    drawing = Drawing(460, 260)
    drawing.add(String(10, 240, "Доходы и расходы по месяцам", fontSize=14, fontName=font_name))

    if not labels:
        drawing.add(String(10, 120, "Нет данных для построения диаграммы.", fontSize=12, fontName=font_name))
        return drawing

    chart = VerticalBarChart()
    chart.x = 50
    chart.y = 50
    chart.height = 150
    chart.width = 360
    chart.data = [income_values, expense_values]
    chart.categoryAxis.categoryNames = labels
    chart.categoryAxis.labels.fontName = font_name
    chart.valueAxis.labels.fontName = font_name
    chart.valueAxis.valueMin = 0
    chart.bars[0].fillColor = colors.HexColor("#198754")
    chart.bars[1].fillColor = colors.HexColor("#dc3545")
    drawing.add(chart)
    drawing.add(String(320, 220, "Доходы", fillColor=colors.HexColor("#198754"), fontName=font_name))
    drawing.add(String(380, 220, "Расходы", fillColor=colors.HexColor("#dc3545"), fontName=font_name))
    return drawing


def _build_line_chart(labels, values, font_name):
    """Создаёт линейный график динамики баланса."""
    drawing = Drawing(460, 260)
    drawing.add(String(10, 240, "Динамика баланса", fontSize=14, fontName=font_name))

    if not values:
        drawing.add(String(10, 120, "Нет данных для построения графика.", fontSize=12, fontName=font_name))
        return drawing

    chart = HorizontalLineChart()
    chart.x = 40
    chart.y = 50
    chart.height = 150
    chart.width = 370
    chart.data = [values]
    chart.categoryAxis.categoryNames = labels
    chart.categoryAxis.labels.fontName = font_name
    chart.valueAxis.labels.fontName = font_name
    chart.lines[0].strokeColor = colors.HexColor("#0d6efd")
    chart.lines[0].symbol = None
    chart.joinedLines = 1
    drawing.add(chart)
    return drawing


def export_transactions_pdf(dataframe, filters, analytics_payload):
    """Формирует PDF-отчёт с транзакциями, метриками и графиками."""
    regular_font, bold_font = _register_font()
    output = io.BytesIO()
    doc = SimpleDocTemplate(
        output,
        pagesize=A4,
        rightMargin=15 * mm,
        leftMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
    )

    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="TitleRu",
            parent=styles["Title"],
            fontName=bold_font,
            fontSize=18,
        )
    )
    styles.add(
        ParagraphStyle(
            name="BodyRu",
            parent=styles["BodyText"],
            fontName=regular_font,
            fontSize=10,
            leading=13,
        )
    )

    story = [
        Paragraph("BudgetTracker: финансовый отчёт", styles["TitleRu"]),
        Spacer(1, 6 * mm),
        Paragraph(f"Период: {analytics_payload['period_label']}", styles["BodyRu"]),
        Paragraph(
            "Фильтры: "
            f"тип — {filters.get('type_label', 'Все')}, "
            f"категория — {filters.get('category_label', 'Все')}",
            styles["BodyRu"],
        ),
        Spacer(1, 4 * mm),
    ]

    metrics = analytics_payload["metrics"]
    metric_rows = [
        ["Метрика", "Значение"],
        ["Средний расход в день", metrics["average_expense_per_day"]],
        ["Самая крупная трата", metrics["largest_expense"]],
        ["Категория с максимальными расходами", metrics["top_expense_category"]],
    ]
    metric_table = Table(metric_rows, colWidths=[80 * mm, 95 * mm])
    metric_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0d6efd")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), bold_font),
                ("FONTNAME", (0, 1), (-1, -1), regular_font),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#dee2e6")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8f9fa")]),
                ("PADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.extend([metric_table, Spacer(1, 5 * mm)])

    story.append(
        _build_pie_chart(
            analytics_payload["expenses_by_category"]["labels"],
            analytics_payload["expenses_by_category"]["values"],
            regular_font,
        )
    )
    story.append(Spacer(1, 5 * mm))
    story.append(
        _build_bar_chart(
            analytics_payload["monthly_summary"]["labels"],
            analytics_payload["monthly_summary"]["income"],
            analytics_payload["monthly_summary"]["expense"],
            regular_font,
        )
    )
    story.append(Spacer(1, 5 * mm))
    story.append(
        _build_line_chart(
            analytics_payload["balance_trend"]["labels"],
            analytics_payload["balance_trend"]["values"],
            regular_font,
        )
    )
    story.append(Spacer(1, 5 * mm))
    story.append(Paragraph("Список транзакций", styles["TitleRu"]))
    story.append(Spacer(1, 3 * mm))

    if dataframe.empty:
        story.append(Paragraph("За выбранный период транзакции отсутствуют.", styles["BodyRu"]))
    else:
        table_data = [list(dataframe.columns)] + dataframe.values.tolist()
        transaction_table = Table(table_data, repeatRows=1, colWidths=[27 * mm, 25 * mm, 45 * mm, 25 * mm, 58 * mm])
        transaction_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#198754")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), bold_font),
                    ("FONTNAME", (0, 1), (-1, -1), regular_font),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#dee2e6")),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8f9fa")]),
                    ("PADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        story.append(transaction_table)

    doc.build(story)
    output.seek(0)
    return output
