/**
 * IncidentFlow Advanced Analytics Charts Controller
 */

document.addEventListener("DOMContentLoaded", function () {
    if (!window.ANALYTICS_DATA) return;
    const d = window.ANALYTICS_DATA;

    Chart.defaults.font.family = "'Inter', system-ui, sans-serif";
    Chart.defaults.font.size = 12;
    Chart.defaults.color = "#64748b";

    // 1. Velocity: Ingestion vs Resolution
    const velocityCtx = document.getElementById("velocityChart");
    if (velocityCtx && d.trend) {
        new Chart(velocityCtx, {
            type: "line",
            data: {
                labels: d.trend.labels,
                datasets: [
                    {
                        label: "Incidents Created",
                        data: d.trend.created,
                        borderColor: "#ef4444",
                        backgroundColor: "rgba(239, 68, 68, 0.08)",
                        borderWidth: 2,
                        tension: 0.35,
                        fill: true
                    },
                    {
                        label: "Incidents Resolved",
                        data: d.trend.resolved,
                        borderColor: "#10b981",
                        backgroundColor: "rgba(16, 185, 129, 0.08)",
                        borderWidth: 2,
                        tension: 0.35,
                        fill: true
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: "top", labels: { boxWidth: 12, padding: 16 } }
                },
                scales: {
                    y: { beginAtZero: true, ticks: { stepSize: 1 } },
                    x: { grid: { display: false } }
                }
            }
        });
    }

    // 2. Priority Donut
    const prioCtx = document.getElementById("analyticsPriorityChart");
    if (prioCtx && d.priority) {
        new Chart(prioCtx, {
            type: "doughnut",
            data: {
                labels: d.priority.labels,
                datasets: [{
                    data: d.priority.data,
                    backgroundColor: ["#dc2626", "#ea580c", "#2563eb", "#94a3b8"]
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { position: "bottom" } },
                cutout: "65%"
            }
        });
    }

    // 3. Status Bar
    const statusCtx = document.getElementById("analyticsStatusChart");
    if (statusCtx && d.status) {
        new Chart(statusCtx, {
            type: "bar",
            data: {
                labels: d.status.labels,
                datasets: [{
                    data: d.status.data,
                    backgroundColor: ["#ef4444", "#f59e0b", "#10b981", "#64748b"],
                    borderRadius: 6
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: { y: { beginAtZero: true, ticks: { stepSize: 1 } } }
            }
        });
    }

    // 4. Category Bar
    const catCtx = document.getElementById("analyticsCategoryChart");
    if (catCtx && d.category) {
        new Chart(catCtx, {
            type: "bar",
            data: {
                labels: d.category.labels,
                datasets: [{
                    data: d.category.data,
                    backgroundColor: "#8b5cf6",
                    borderRadius: 6
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: { y: { beginAtZero: true, ticks: { stepSize: 1 } } }
            }
        });
    }
});
