
function updateIncident(id) {
    const status = prompt("Enter new status:");

    if (!status) return;

    fetch(`/incidents/${id}`, {
        method: "PUT",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            status: status
        })
    })
    .then(response => response.json())
    .then(data => {
        alert(data.message);
        location.reload();
    });
}

function deleteIncident(id) {
    if (!confirm("Are you sure you want to delete this incident?")) {
        return;
    }

    fetch(`/incidents/${id}`, {
        method: "DELETE"
    })
    .then(response => response.json())
    .then(data => {
        alert(data.message);
        location.reload();
    });
}
