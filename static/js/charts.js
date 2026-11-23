/**
 * IncidentFlow Dashboard Chart Controller
 * Visualizes live database analytics using Chart.js
 */

document.addEventListener("DOMContentLoaded", function () {
    if (!window.INCIDENT_CHART_DATA) {
        return;
    }

    const data = window.INCIDENT_CHART_DATA;

    // Common Chart Defaults
    Chart.defaults.font.family = "'Inter', system-ui, sans-serif";
    Chart.defaults.font.size = 12;
    Chart.defaults.color = "#64748b";

    // 1. 7-Day Ingestion Trend Line Chart
    const trendCtx = document.getElementById("trendChart");
    if (trendCtx && data.trend) {
        new Chart(trendCtx, {
            type: "line",
            data: {
                labels: data.trend.labels,
                datasets: [{
                    label: "Incidents Ingested",
                    data: data.trend.data,
                    borderColor: "#2563eb",
                    backgroundColor: "rgba(37, 99, 235, 0.1)",
                    borderWidth: 2.5,
                    fill: true,
                    tension: 0.35,
                    pointBackgroundColor: "#2563eb",
                    pointRadius: 4,
                    pointHoverRadius: 6
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        padding: 10,
                        backgroundColor: "#1e293b",
                        titleFont: { weight: "600" }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: { stepSize: 1, precision: 0 },
                        grid: { color: "#f1f5f9" }
                    },
                    x: {
                        grid: { display: false }
                    }
                }
            }
        });
    }

    // 2. Priority Distribution Donut Chart
    const priorityCtx = document.getElementById("priorityChart");
    if (priorityCtx && data.priority) {
        new Chart(priorityCtx, {
            type: "doughnut",
            data: {
                labels: data.priority.labels,
                datasets: [{
                    data: data.priority.data,
                    backgroundColor: [
                        "#dc2626", // Critical - Red
                        "#ea580c", // High - Orange
                        "#2563eb", // Medium - Blue
                        "#94a3b8"  // Low - Slate
                    ],
                    borderWidth: 2,
                    borderColor: "#ffffff"
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: "bottom",
                        labels: { boxWidth: 12, padding: 12 }
                    }
                },
                cutout: "68%"
            }
        });
    }

    // 3. Status Breakdown Bar Chart
    const statusCtx = document.getElementById("statusChart");
    if (statusCtx && data.status) {
        new Chart(statusCtx, {
            type: "bar",
            data: {
                labels: data.status.labels,
                datasets: [{
                    label: "Incidents",
                    data: data.status.data,
                    backgroundColor: [
                        "#ef4444", // Open
                        "#f59e0b", // In Progress
                        "#10b981", // Resolved
                        "#64748b"  // Closed
                    ],
                    borderRadius: 6
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: { stepSize: 1, precision: 0 },
                        grid: { color: "#f1f5f9" }
                    },
                    x: {
                        grid: { display: false }
                    }
                }
            }
        });
    }

    // 4. Category Breakdown Horizontal Bar Chart
    const categoryCtx = document.getElementById("categoryChart");
    if (categoryCtx && data.category) {
        new Chart(categoryCtx, {
            type: "bar",
            data: {
                labels: data.category.labels,
                datasets: [{
                    label: "Incidents",
                    data: data.category.data,
                    backgroundColor: "#6366f1",
                    borderRadius: 6
                }]
            },
            options: {
                indexAxis: "y",
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    x: {
                        beginAtZero: true,
                        ticks: { stepSize: 1, precision: 0 },
                        grid: { color: "#f1f5f9" }
                    },
                    y: {
                        grid: { display: false }
                    }
                }
            }
        });
    }

    // 5. Workload Distribution Bar Chart
    const workloadCtx = document.getElementById("workloadChart");
    if (workloadCtx && data.workload) {
        new Chart(workloadCtx, {
            type: "bar",
            data: {
                labels: data.workload.labels,
                datasets: [{
                    label: "Active Incidents",
                    data: data.workload.data,
                    backgroundColor: "#0ea5e9",
                    borderRadius: 6
                }]
            },
            options: {
                indexAxis: "y",
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    x: {
                        beginAtZero: true,
                        ticks: { stepSize: 1, precision: 0 },
                        grid: { color: "#f1f5f9" }
                    },
                    y: {
                        grid: { display: false }
                    }
                }
            }
        });
    }
});
