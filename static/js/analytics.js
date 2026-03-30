document.addEventListener("DOMContentLoaded", () => {
    const periodSelect = document.getElementById("period-select");
    const applyButton = document.getElementById("apply-analytics-filter");
    const customRangeFields = document.querySelectorAll(".custom-range");
    const customStart = document.getElementById("custom-start");
    const customEnd = document.getElementById("custom-end");

    const metricAverageExpense = document.getElementById("metric-average-expense");
    const metricLargestExpense = document.getElementById("metric-largest-expense");
    const metricTopCategory = document.getElementById("metric-top-category");

    const expensesCtx = document.getElementById("expensesChart");
    const monthlyCtx = document.getElementById("monthlyChart");
    const balanceCtx = document.getElementById("balanceChart");

    const chartPalette = ["#0d6efd", "#198754", "#dc3545", "#ffb703", "#20c997", "#6f42c1", "#fd7e14"];

    const expensesChart = new Chart(expensesCtx, {
        type: "pie",
        data: { labels: [], datasets: [{ data: [], backgroundColor: chartPalette }] },
        options: { responsive: true, maintainAspectRatio: false }
    });

    const monthlyChart = new Chart(monthlyCtx, {
        type: "bar",
        data: {
            labels: [],
            datasets: [
                { label: "Доходы", data: [], backgroundColor: "#198754", borderRadius: 10 },
                { label: "Расходы", data: [], backgroundColor: "#dc3545", borderRadius: 10 }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: { y: { beginAtZero: true } }
        }
    });

    const balanceChart = new Chart(balanceCtx, {
        type: "line",
        data: {
            labels: [],
            datasets: [
                {
                    label: "Баланс",
                    data: [],
                    borderColor: "#0d6efd",
                    backgroundColor: "rgba(13, 110, 253, 0.18)",
                    fill: true,
                    tension: 0.3
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: { y: { beginAtZero: false } }
        }
    });

    const toggleCustomRange = () => {
        const isCustom = periodSelect.value === "custom";
        customRangeFields.forEach((field) => field.classList.toggle("d-none", !isCustom));
    };

    const loadAnalytics = async () => {
        const params = new URLSearchParams({
            type: "all",
            period: periodSelect.value
        });

        if (periodSelect.value === "custom") {
            params.set("start", customStart.value);
            params.set("end", customEnd.value);
        }

        const response = await fetch(`/api/analytics/data?${params.toString()}`);
        const payload = await response.json();

        expensesChart.data.labels = payload.expenses_by_category.labels;
        expensesChart.data.datasets[0].data = payload.expenses_by_category.values;
        expensesChart.data.datasets[0].backgroundColor = payload.expenses_by_category.colors.length
            ? payload.expenses_by_category.colors
            : chartPalette;
        expensesChart.update();

        monthlyChart.data.labels = payload.monthly_summary.labels;
        monthlyChart.data.datasets[0].data = payload.monthly_summary.income;
        monthlyChart.data.datasets[1].data = payload.monthly_summary.expense;
        monthlyChart.update();

        balanceChart.data.labels = payload.balance_trend.labels;
        balanceChart.data.datasets[0].data = payload.balance_trend.values;
        balanceChart.update();

        metricAverageExpense.textContent = payload.metrics.average_expense_per_day;
        metricLargestExpense.textContent = payload.metrics.largest_expense;
        metricTopCategory.textContent = payload.metrics.top_expense_category;
    };

    periodSelect.addEventListener("change", toggleCustomRange);
    applyButton.addEventListener("click", loadAnalytics);

    toggleCustomRange();
    loadAnalytics();
});
