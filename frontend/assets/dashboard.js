let applicationChart;
let statusChart;

async function fetchJSON(url) {
    const response = await fetch(url);
    if (!response.ok) {
        throw new Error(`API error: ${response.status}`);
    }
    return response.json();
}

function setText(id, value) {
    document.getElementById(id).textContent = value;
}

function createCharts(summary) {
    const applications = summary.by_application || [];
    const statuses = summary.by_status || [];

    if (applicationChart) applicationChart.destroy();
    if (statusChart) statusChart.destroy();

    applicationChart = new Chart(document.getElementById("applicationChart"), {
        type: "bar",
        data: {
            labels: applications.map(item => item.application_name || "Unknown"),
            datasets: [{
                label: "Incidents",
                data: applications.map(item => item.incident_count),
                backgroundColor: "#647bff",
                borderRadius: 6
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: { y: { beginAtZero: true, ticks: { precision: 0 } } }
        }
    });

    statusChart = new Chart(document.getElementById("statusChart"), {
        type: "doughnut",
        data: {
            labels: statuses.map(item => item.status || "Unknown"),
            datasets: [{
                data: statuses.map(item => item.incident_count),
                backgroundColor: ["#647bff", "#22c98b", "#f5a64a", "#e66b72"],
                borderWidth: 0
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { position: "bottom" } }
        }
    });
}

function renderIncidents(incidents) {
    const tbody = document.getElementById("incidentTable");

    if (!incidents.length) {
        tbody.innerHTML = '<tr><td colspan="6" class="empty-state">No incidents recorded yet.</td></tr>';
        return;
    }

    tbody.innerHTML = incidents.map(incident => {
        const status = incident.status || "unknown";
        const health = incident.health_status || "unknown";
        const cause = incident.predicted_root_cause || "Not available";
        const confidence = incident.confidence_percent;

        return `
            <tr>
                <td><button class="incident-link" onclick="viewIncident(&quot;${escapeHTML(incident.incident_id || "")}&quot;)">${escapeHTML(incident.incident_id || "—")}</button></td>
                <td>${escapeHTML(incident.application_name || "—")}</td>
                <td><span class="pill ${healthClass(health)}">${escapeHTML(health)}</span></td>
                <td>${escapeHTML(cause)}</td>
                <td>${confidence == null ? "—" : Number(confidence).toFixed(1) + "%"}</td>
                <td><span class="pill ${statusClass(status)}">${escapeHTML(status)}</span></td>
            </tr>
        `;
    }).join("");
}

function renderWebsiteChecks(checks) {
    const tbody = document.getElementById("websiteTable");

    if (!checks.length) {
        tbody.innerHTML = '<tr><td colspan="6" class="empty-state">No website checks recorded yet.</td></tr>';
        return;
    }

    tbody.innerHTML = checks.map(check => `
        <tr>
            <td>${escapeHTML(check.website_name || "—")}</td>
            <td>${escapeHTML(check.url || "—")}</td>
            <td>${check.status_code ?? "—"}</td>
            <td>${check.response_time_ms == null ? "—" : Number(check.response_time_ms).toFixed(1) + " ms"}</td>
            <td><span class="pill ${check.available ? "available" : "failed"}">${check.available ? "Available" : "Unavailable"}</span></td>
            <td>${escapeHTML(formatDate(check.checked_at))}</td>
        </tr>
    `).join("");
}

function escapeHTML(value) {
    return String(value).replace(/[&<>"']/g, character => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;"
    })[character]);
}

function statusClass(status) {
    return String(status).toLowerCase() === "open" ? "open" :
        String(status).toLowerCase() === "resolved" ? "resolved" : "";
}

function healthClass(health) {
    return String(health).toLowerCase().includes("healthy") ? "healthy" : "unhealthy";
}

function formatDate(value) {
    if (!value) return "—";
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

async function loadDashboard() {
    const refreshButton = document.getElementById("refreshButton");
    refreshButton.disabled = true;
    refreshButton.textContent = "Loading...";

    try {
        const [incidentSummary, incidentData, websiteSummary, websiteData] =
            await Promise.all([
                fetchJSON("/incidents/summary"),
                fetchJSON("/incidents?limit=20"),
                fetchJSON("/website-checks/summary"),
                fetchJSON("/website-checks?limit=20")
            ]);

        const statuses = incidentSummary.by_status || [];
        const openCount = statuses
            .filter(item => String(item.status).toLowerCase() === "open")
            .reduce((sum, item) => sum + item.incident_count, 0);
        const resolvedCount = statuses
            .filter(item => String(item.status).toLowerCase() === "resolved")
            .reduce((sum, item) => sum + item.incident_count, 0);

        setText("totalIncidents", incidentSummary.total_incidents ?? 0);
        setText("openIncidents", openCount);
        setText("resolvedIncidents", resolvedCount);

        setText(
            "websiteAvailability",
            websiteSummary.availability_percent == null
                ? "—"
                : Number(websiteSummary.availability_percent).toFixed(1) + "%"
        );

        setText("totalChecks", websiteSummary.total_checks ?? 0);
        setText("successfulChecks", websiteSummary.successful_checks ?? 0);
        setText("failedChecks", websiteSummary.failed_checks ?? 0);
        setText(
            "averageResponse",
            Number(websiteSummary.average_response_time_ms || 0).toFixed(1) + " ms"
        );

        createCharts(incidentSummary);
        renderIncidents(incidentData.incidents || []);
        renderWebsiteChecks(websiteData.checks || []);

        setText("lastUpdated", "Updated " + new Date().toLocaleTimeString());
    } catch (error) {
        console.error("Dashboard loading failed:", error);
        setText("lastUpdated", "Could not load API data. Check server connection.");
    } finally {
        refreshButton.disabled = false;
        refreshButton.textContent = "↻ Refresh";
    }
}

document.getElementById("refreshButton").addEventListener("click", loadDashboard);

loadDashboard();
setInterval(loadDashboard, 15000);


let probabilityChart;

async function viewIncident(incidentId) {
    const section = document.getElementById("incidentDetails");
    section.hidden = false;
    section.scrollIntoView({ behavior: "smooth" });

    setText("detailIncidentId", "Loading " + incidentId + "...");

    try {
        const incident = await fetchJSON(
            "/incidents/" + encodeURIComponent(incidentId)
        );

        setText("detailIncidentId", incident.incident_id);
        setText("detailCause", incident.predicted_root_cause || "Not available");
        setText(
            "detailConfidence",
            incident.confidence_percent == null
                ? "—"
                : Number(incident.confidence_percent).toFixed(1) + "%"
        );
        setText("detailCPU", Number(incident.cpu_percent || 0).toFixed(1) + "%");
        setText("detailMemory", Number(incident.memory_percent || 0).toFixed(1) + "%");

        setText("detailReason", "Detection reason: " + (incident.reasons || "Not recorded"));
        setText("detailHealth", "Health status: " + (incident.health_status || "Unknown"));
        setText("detailDisk", "Disk usage: " + Number(incident.disk_percent || 0).toFixed(1) + "%");
        setText("detailTimestamp", "Detected at: " + formatDate(incident.timestamp));
        renderIncidentTimeline(incident);

    const recommendations = incident.recommendations || [];
    document.getElementById("incidentRecommendations").innerHTML =
        recommendations.length
            ? recommendations.map(item => `<li>${escapeHTML(item)}</li>`).join("")
            : "<li>No recommendations available.</li>";

        const probabilities = incident.root_cause_probabilities || {};
        const labels = Object.keys(probabilities);
        const values = Object.values(probabilities);

        if (probabilityChart) probabilityChart.destroy();

        probabilityChart = new Chart(
            document.getElementById("probabilityChart"),
            {
                type: "bar",
                data: {
                    labels,
                    datasets: [{
                        label: "Probability (%)",
                        data: values,
                        backgroundColor: "#647bff",
                        borderRadius: 6
                    }]
                },
                options: {
                    indexAxis: "y",
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false }
                    },
                    scales: {
                        x: {
                            beginAtZero: true,
                            max: 100,
                            ticks: { callback: value => value + "%" }
                        }
                    }
                }
            }
        );
    } catch (error) {
        console.error("Incident details loading failed:", error);
        setText("detailIncidentId", "Unable to load incident details.");
    }
}

function closeIncidentDetails() {
    document.getElementById("incidentDetails").hidden = true;

    if (probabilityChart) {
        probabilityChart.destroy();
        probabilityChart = null;
    }
}


function renderIncidentTimeline(incident) {
    const events = [
        {
            title: "Incident Detected",
            time: incident.timestamp,
            description: "Incident first detected by monitoring agent."
        },
        {
            title: "Last Observed",
            time: incident.last_seen_at,
            description: "Most recent monitoring observation."
        }
    ];

    if (incident.resolved_at) {
        events.push({
            title: "Incident Resolved",
            time: incident.resolved_at,
            description: "Application incident marked as resolved."
        });
    } else {
        events.push({
            title: "Awaiting Resolution",
            time: null,
            description: "Incident is currently open."
        });
    }

    document.getElementById("incidentTimeline").innerHTML =
        events.map(event => `
            <div class="timeline-event">
                <strong>${escapeHTML(event.title)}</strong>
                <p>${escapeHTML(event.description)}</p>
                <small>${escapeHTML(formatDate(event.time))}</small>
            </div>
        `).join("");
}
