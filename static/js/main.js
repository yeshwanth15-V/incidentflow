/**
 * IncidentFlow Main Frontend Controller
 * Handles CSRF injection, confirmation modals, responsive sidebar, toasts
 */

document.addEventListener("DOMContentLoaded", function () {
    // 1. Sidebar Toggle for Mobile
    const sidebarToggle = document.getElementById("sidebarToggle");
    const sidebar = document.getElementById("sidebar");
    if (sidebarToggle && sidebar) {
        sidebarToggle.addEventListener("click", function () {
            sidebar.classList.toggle("toggled");
        });
    }

    // 2. Setup CSRF Token for all XMLHttpRequest & Fetch Calls
    const csrfTokenMeta = document.querySelector('meta[name="csrf-token"]');
    if (csrfTokenMeta) {
        window.csrfToken = csrfTokenMeta.getAttribute("content");
    }

    // 3. Auto-dismiss alerts after 6 seconds
    const alerts = document.querySelectorAll(".alert-dismissible");
    alerts.forEach(function (alert) {
        setTimeout(function () {
            const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
            if (bsAlert) bsAlert.close();
        }, 6000);
    });
});

/**
 * Global Confirm Action Modal
 * Replaces browser prompt() and confirm() with modern Bootstrap modal
 */
function confirmDelete(incidentId, referenceId, title) {
    const modal = new bootstrap.Modal(document.getElementById("confirmActionModal"));
    const titleEl = document.getElementById("confirmModalTitle");
    const bodyEl = document.getElementById("confirmModalBody");
    const formEl = document.getElementById("confirmModalForm");
    const btnEl = document.getElementById("confirmModalBtn");

    titleEl.textContent = `Delete Incident ${referenceId}?`;
    bodyEl.innerHTML = `
        <div class="d-flex align-items-center mb-3">
            <i class="bi bi-exclamation-triangle-fill text-danger fs-2 me-3"></i>
            <div>
                <strong>Warning:</strong> You are about to permanently delete <strong>${referenceId}</strong>:
                <div class="text-muted small mt-1">"${title}"</div>
            </div>
        </div>
        <p class="small text-danger mb-0">This will remove the incident and its complete activity audit history. This action cannot be undone.</p>
    `;

    formEl.action = `/incidents/${incidentId}/delete`;
    btnEl.className = "btn btn-danger";
    btnEl.textContent = "Permanently Delete";

    modal.show();
}

/**
 * Universal API helper for JSON calls with CSRF support
 */
async function apiRequest(url, method = "GET", data = null) {
    const headers = {
        "Content-Type": "application/json",
        "Accept": "application/json"
    };

    if (window.csrfToken && method !== "GET") {
        headers["X-CSRFToken"] = window.csrfToken;
    }

    const options = {
        method: method,
        headers: headers
    };

    if (data && method !== "GET") {
        options.body = JSON.stringify(data);
    }

    try {
        const response = await fetch(url, options);
        const result = await response.json();
        if (!response.ok) {
            throw new Error(result.error || result.message || "Request failed");
        }
        return result;
    } catch (err) {
        console.error("API Request Error:", err);
        throw err;
    }
}
