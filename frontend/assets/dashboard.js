let applicationChart;
let statusChart;
let currentUser = null;

async function initializeDashboard() {
    try {
        const response = await fetch("/auth/me", { credentials: "same-origin" });

        if (!response.ok) {
            window.location.replace("/frontend/login.html");
            return;
        }

        const data = await response.json();
        currentUser = data.user;

        const accountInfo = document.getElementById("accountInfo");
        if (accountInfo) {
            accountInfo.textContent = `${currentUser.email} (${currentUser.role})`;
        }

        const adminOnlyElements = document.querySelectorAll(".admin-only");
        adminOnlyElements.forEach(element => {
            element.hidden = currentUser.role !== "admin";
        });

        await loadDashboard();

        if (currentUser.role === "admin") {
            await loadDependencyGraph();
        }
    } catch (error) {
        console.error("Authentication check failed:", error);
        window.location.replace("/frontend/login.html");
    }
}

async function fetchJSON(url, options = {}) {
    const response = await fetch(url, options);
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
        tbody.innerHTML = '<tr><td colspan="7" class="empty-state">No incidents recorded yet.</td></tr>';
        return;
    }

    tbody.innerHTML = incidents.map(incident => {
        const status = incident.status || "unknown";
        const health = incident.health_status || "unknown";
        const severity = incident.severity || "Not classified";
        const cause = incident.predicted_root_cause || "Not available";
        const confidence = incident.confidence_percent;

        return `
            <tr>
                <td><button class="incident-link" onclick="viewIncident(&quot;${escapeHTML(incident.incident_id || "")}&quot;)">${escapeHTML(incident.incident_id || "—")}</button></td>
                <td>${escapeHTML(incident.application_name || "—")}</td>
                <td>${escapeHTML(severity)}</td>
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

function renderComponentHealth(applications, checks, graph) {
    const tbody = document.getElementById("componentHealthTable");
    if (!tbody) return;

    const rows = [];
    const dependencyNames = new Set(
        (graph.nodes || [])
            .filter(node => node.type === "dependency")
            .map(node => node.id)
    );

    for (const app of applications) {
        const healthy = Boolean(app.healthy) && Boolean(app.process_running);
        rows.push(`
            <tr>
                <td>${escapeHTML(app.application_name)}</td>
                <td>Application</td>
                <td><span class="pill ${healthy ? "healthy" : "unhealthy"}">${healthy ? "Healthy" : "Unhealthy"}</span></td>
                <td>${app.status_code ?? "—"} / Process ${app.process_running ? "Running" : "Stopped"}</td>
                <td>CPU ${Number(app.cpu_percent ?? 0).toFixed(1)}% · RAM ${Number(app.memory_percent ?? 0).toFixed(1)}% · Disk ${Number(app.disk_percent ?? 0).toFixed(1)}%</td>
                <td>${escapeHTML(formatDate(app.checked_at))}</td>
            </tr>
        `);
    }

    const latestChecks = new Map();
    for (const check of checks) {
        if (!latestChecks.has(check.website_name)) {
            latestChecks.set(check.website_name, check);
        }
    }

    for (const check of latestChecks.values()) {
        const available = Boolean(check.available);
        rows.push(`
            <tr>
                <td>${escapeHTML(check.website_name || "—")}</td>
                <td>${dependencyNames.has(check.website_name) ? "Service Dependency" : "External Website"}</td>
                <td><span class="pill ${available ? "available" : "failed"}">${available ? "Available" : "Unavailable"}</span></td>
                <td>${check.status_code ?? "—"}</td>
                <td>${check.response_time_ms == null ? "—" : Number(check.response_time_ms).toFixed(1) + " ms"}</td>
                <td>${escapeHTML(formatDate(check.checked_at))}</td>
            </tr>
        `);
    }

    const priority = row =>
        row.includes("<td>Application</td>") ? 0 :
        row.includes("<td>Service Dependency</td>") ? 1 : 2;

    rows.sort((a, b) => priority(a) - priority(b));

    tbody.innerHTML = rows.length
        ? rows.join("")
        : '<tr><td colspan="6" class="empty-state">No component health data available yet.</td></tr>';
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
    const date = new Date(/Z$|[+-]\d{2}:?\d{2}$/.test(value) ? value : value + "Z");
    return Number.isNaN(date.getTime()) ? value : date.toLocaleString("en-IN", { timeZone: "Asia/Kolkata" });
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
                fetchJSON("/website-checks?limit=100")
            ]);

        let applicationHealth = { applications: [] };
        let dependencyGraph = { nodes: [], edges: [] };

        if (currentUser && currentUser.role === "admin") {
            [applicationHealth, dependencyGraph] = await Promise.all([
                fetchJSON("/application-health"),
                fetchJSON("/dependency-graph")
            ]);
        }

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

        const severityCounts = incidentSummary.by_severity || [];
        const countSeverity = severity =>
            severityCounts
                .filter(item => item.severity === severity)
                .reduce((sum, item) => sum + item.incident_count, 0);

        setText("criticalIncidents", countSeverity("Critical"));
        setText("highIncidents", countSeverity("High"));
        setText("mediumIncidents", countSeverity("Medium"));
        setText("lowIncidents", countSeverity("Low"));

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
        renderComponentHealth(
            applicationHealth.applications || [],
            websiteData.checks || [],
            dependencyGraph
        );

        setText("lastUpdated", "Updated " + new Date().toLocaleTimeString("en-IN", { timeZone: "Asia/Kolkata" }));
    } catch (error) {
        console.error("Dashboard loading failed:", error);
        setText("lastUpdated", "Could not load API data. Check server connection.");
    } finally {
        refreshButton.disabled = false;
        refreshButton.textContent = "↻ Refresh";
    }
}

document.getElementById("refreshButton").addEventListener("click", loadDashboard);

document.getElementById("logoutButton").addEventListener("click", async () => {
    try {
        await fetch("/auth/logout", {
            method: "POST",
            credentials: "same-origin"
        });
    } finally {
        window.location.replace("/frontend/login.html");
    }
});

initializeDashboard();
setInterval(() => {
    if (currentUser) loadDashboard();
}, 15000);


let probabilityChart;
let selectedIncidentId = null;

async function viewIncident(incidentId) {
    selectedIncidentId = incidentId;
    const selectedLabel = document.getElementById("aiSelectedIncident");
    if (selectedLabel) selectedLabel.textContent = "Selected incident: " + incidentId;

    const section = document.getElementById("incidentDetails");
    section.hidden = false;
    section.scrollIntoView({ behavior: "smooth" });

    setText("detailIncidentId", "Loading " + incidentId + "...");

    try {
        const incident = await fetchJSON(
            "/incidents/" + encodeURIComponent(incidentId)
        );

        const aiButton = document.getElementById("generateAIButton");
        aiButton.onclick = () => generateAIInvestigation(incidentId);
        aiButton.disabled = false;
        document.getElementById("aiInvestigationResult").hidden = true;
        document.getElementById("aiInvestigationStatus").textContent =
            "AI investigation has not been generated.";

        setText("detailIncidentId", incident.incident_id);
        setText("detailCause", incident.predicted_root_cause || "Not available");
        setText("detailSeverity", incident.severity || "Not classified");
        setText(
            "detailConfidence",
            incident.confidence_percent == null
                ? "—"
                : Number(incident.confidence_percent).toFixed(1) + "%"
        );
        const isWebsiteIncident = String(incident.application_name || "").startsWith("Website:");

        document.getElementById("applicationCpuCard").hidden = isWebsiteIncident;
        document.getElementById("applicationMemoryCard").hidden = isWebsiteIncident;
        document.getElementById("websiteIncidentEvidence").hidden = !isWebsiteIncident;
        document.getElementById("detailDisk").hidden = isWebsiteIncident;

        if (isWebsiteIncident) {
            setText("detailWebsiteStatus", "HTTP status: " +
                (incident.website_status_code ?? "Not recorded"));
            setText("detailWebsiteResponse", "Response time: " +
                (incident.website_response_time_ms == null
                    ? "Not recorded"
                    : Number(incident.website_response_time_ms).toFixed(1) + " ms"));
            setText("detailWebsiteUrl", "Website URL: " +
                (incident.website_url || "Not recorded"));
        } else {
            setText("detailCPU", Number(incident.cpu_percent || 0).toFixed(1) + "%");
            setText("detailMemory", Number(incident.memory_percent || 0).toFixed(1) + "%");
            setText("detailDisk", "Disk usage: " + Number(incident.disk_percent || 0).toFixed(1) + "%");
        }

        setText("detailReason", "Detection reason: " + (incident.reasons || "Not recorded"));
        setText("detailHealth", "Health status: " + (incident.health_status || "Unknown"));
        setText("detailTimestamp", "Detected at: " + formatDate(incident.timestamp));
        renderIncidentTimeline(incident);

    const recommendations = incident.recommendations || [];
    document.getElementById("incidentRecommendations").innerHTML =
        recommendations.length
            ? recommendations.map(item => `<li>${escapeHTML(item)}</li>`).join("")
            : "<li>No recommendations available.</li>";

        const probabilityPanel = document.getElementById("rootCauseProbabilityPanel");
        probabilityPanel.hidden = isWebsiteIncident;

        if (probabilityChart) {
            probabilityChart.destroy();
            probabilityChart = null;
        }

        const probabilities = incident.root_cause_probabilities || {};
        const labels = Object.keys(probabilities);
        const values = Object.values(probabilities);

        if (!isWebsiteIncident && labels.length > 0) {
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
        }
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

// Dependency graph visualization
async function loadDependencyGraph() {
    const container = document.getElementById("dependencyGraphContainer");

    if (!currentUser || currentUser.role !== "admin") {
        if (container) container.textContent = "Administrator access required.";
        return;
    }

    try {
        const response = await fetch("/dependency-graph");

        if (!response.ok) {
            throw new Error("Unable to load dependency graph");
        }

        const data = await response.json();

        const nodes = data.nodes || [];
        const edges = data.edges || [];

        if (!nodes.length) {
            container.textContent = "No monitored components configured.";
            return;
        }

        const nodeWidth = 190;
        const nodeHeight = 70;
        const gap = 70;
        const width = Math.max(600, nodes.length * (nodeWidth + gap));
        const height = 180;

        const positions = nodes.map((node, index) => ({
            ...node,
            x: 30 + index * (nodeWidth + gap),
            y: 45
        }));

        const escape = value => String(value).replace(/[&<>"']/g, char => ({
            "&": "&amp;",
            "<": "&lt;",
            ">": "&gt;",
            '"': "&quot;",
            "'": "&#39;"
        })[char]);

        const nodePositions = Object.fromEntries(
            positions.map(node => [node.id, node])
        );

        const edgeMarkup = edges.map(edge => {
            const source = nodePositions[edge.source];
            const target = nodePositions[edge.target];

            if (!source || !target) return "";

            return `
                <line
                    x1="${source.x + nodeWidth}"
                    y1="${source.y + nodeHeight / 2}"
                    x2="${target.x}"
                    y2="${target.y + nodeHeight / 2}"
                    stroke="#94a3b8"
                    stroke-width="2"
                    marker-end="url(#dependencyArrow)"
                />
            `;
        }).join("");

        const nodeMarkup = positions.map(node => {
            const isApplication = node.type === "application";
            const isDependency = node.type === "dependency";

            const fill = isApplication
                ? "#dbeafe"
                : isDependency
                    ? "#ffedd5"
                    : "#dcfce7";

            const stroke = isApplication
                ? "#2563eb"
                : isDependency
                    ? "#ea580c"
                    : "#16a34a";

            const label = isApplication
                ? "APPLICATION"
                : isDependency
                    ? "SERVICE DEPENDENCY"
                    : "EXTERNAL WEBSITE";

            return `
                <g>
                    <rect
                        x="${node.x}" y="${node.y}"
                        width="${nodeWidth}" height="${nodeHeight}"
                        rx="10" fill="${fill}" stroke="${stroke}"
                        stroke-width="2"
                    />
                    <text
                        x="${node.x + nodeWidth / 2}"
                        y="${node.y + 29}"
                        text-anchor="middle"
                        font-size="15"
                        font-weight="600"
                        fill="#172554"
                    >${escape(node.id)}</text>
                    <text
                        x="${node.x + nodeWidth / 2}"
                        y="${node.y + 49}"
                        text-anchor="middle"
                        font-size="10"
                        fill="#475569"
                    >${label}</text>
                </g>
            `;
        }).join("");

        container.innerHTML = `
            <div style="overflow-x:auto;">
                <svg
                    viewBox="0 0 ${width} ${height}"
                    style="width:100%; min-width:600px; height:auto;"
                    role="img"
                    aria-label="Application and website dependency graph"
                >
                    <defs>
                        <marker
                            id="dependencyArrow"
                            markerWidth="8"
                            markerHeight="8"
                            refX="6"
                            refY="3"
                            orient="auto"
                        >
                            <path d="M0,0 L0,6 L6,3 z" fill="#94a3b8"/>
                        </marker>
                    </defs>
                    ${edgeMarkup}
                    ${nodeMarkup}
                </svg>
            </div>
            <p>${nodes.length} monitored components · ${edges.length} dependencies</p>
        `;
    } catch (error) {
        container.textContent = "Dependency graph could not be loaded.";
        console.error(error);
    }
}

document.addEventListener("DOMContentLoaded", loadDependencyGraph);

async function generateAIInvestigation(incidentId) {
    const button = document.getElementById("generateAIButton");
    const status = document.getElementById("aiInvestigationStatus");
    const result = document.getElementById("aiInvestigationResult");

    button.disabled = true;
    button.textContent = "Generating...";
    status.textContent = "Requesting incident analysis from Groq...";
    result.hidden = true;

    try {
        const data = await fetchJSON(
            "/incidents/" + encodeURIComponent(incidentId) + "/ai-explanation",
            { method: "POST" }
        );

        const analysis = data.ai_analysis;

        if (!analysis || !analysis.available || !analysis.explanation) {
            throw new Error(analysis?.error || "AI analysis unavailable");
        }

        const explanation = analysis.explanation;

        const sections = {};
        const headingPattern =
            /(?:^|\n)\s{0,3}(?:#{1,3}\s*)?(?:\*\*)?\s*(SUMMARY|EVIDENCE|ACTIONS)\s*:?\s*(?:\*\*)?\s*:?\s*/gi;

        const headings = [...explanation.matchAll(headingPattern)];

        headings.forEach((match, index) => {
            const contentStart = match.index + match[0].length;
            const contentEnd = index + 1 < headings.length
                ? headings[index + 1].index
                : explanation.length;

            sections[match[1].toUpperCase()] =
                explanation.slice(contentStart, contentEnd).trim();
        });

        document.getElementById("aiSummary").textContent =
            sections.SUMMARY || "Not provided.";

        document.getElementById("aiEvidence").textContent =
            sections.EVIDENCE || "Not provided.";

        const actions = (sections.ACTIONS || "")
            .split("\n")
            .map(line => line.replace(/^\s*(?:[-*•]|\d+[.)])\s*/, "").trim())
            .filter(Boolean);
        const actionList = document.createElement("ul");

        actions.forEach(action => {
            const item = document.createElement("li");
            item.textContent = action;
            actionList.appendChild(item);
        });

        const actionsContainer = document.getElementById("aiActions");
        actionsContainer.replaceChildren(actionList);

        result.hidden = false;
        status.textContent = "AI investigation generated successfully.";
    } catch (error) {
        status.textContent =
            "Hosted AI unavailable. Use the rule-based recommendations below. " +
            error.message;
    } finally {
        button.disabled = false;
        button.textContent = "Generate AI Investigation";
    }
}

/* IncidentGraph AI page navigation */
function showDashboardPage(pageName) {
    const pages = {
        overview: ["overviewPage"],
        incidents: ["incidentsPage"],
        "ai-investigation": ["ai-investigationPage"],
        websites: ["websitesPage"],
        "dependency-graph": ["dependency-graphPage"]
    };

    if (!pages[pageName]) return;

    if (pageName === "dependency-graph" &&
        (!currentUser || currentUser.role !== "admin")) {
        showDashboardPage("overview");
        return;
    }

    document.querySelectorAll(".nav-link[data-page]").forEach(link => {
        const active = link.dataset.page === pageName;
        link.classList.toggle("active", active);
        if (active) link.setAttribute("aria-current", "page");
        else link.removeAttribute("aria-current");
    });

    document.querySelectorAll(".page-section").forEach(section => {
        section.hidden = !pages[pageName].includes(section.id);
    });

    if (pageName === "dependency-graph") loadDependencyGraph();

    if (pageName === "ai-investigation" && !selectedIncidentId) {
        document.getElementById("aiInvestigationStatus").textContent =
            "Select an incident from the Incidents page to begin investigation.";
        document.getElementById("generateAIButton").disabled = true;
    } else if (pageName === "ai-investigation") {
        document.getElementById("generateAIButton").disabled = false;
    }

    window.scrollTo({ top: 0, behavior: "smooth" });
}

document.querySelectorAll(".nav-link[data-page]").forEach(link => {
    link.addEventListener("click", event => {
        event.preventDefault();
        showDashboardPage(link.dataset.page);
        history.replaceState(null, "", link.getAttribute("href"));
    });
});

// User-owned website management
async function loadRegisteredWebsites() {
    const tbody = document.getElementById("registeredWebsitesTable");
    if (!tbody) return;

    try {
        const data = await fetchJSON("/websites");

        if (!data.websites.length) {
            tbody.innerHTML = '<tr><td colspan="4" class="empty-state">No websites registered yet. Add your first website above.</td></tr>';
            return;
        }

        tbody.innerHTML = data.websites.map(website => `
            <tr>
                <td>${escapeHTML(website.name)}</td>
                <td>${escapeHTML(website.url)}</td>
                <td>${escapeHTML(website.monitoring_status)}</td>
                <td>
                    <button type="button" class="delete-website-button"
                        data-website-id="${Number(website.id)}">Delete</button>
                </td>
            </tr>
        `).join("");
    } catch (error) {
        tbody.innerHTML = '<tr><td colspan="4" class="empty-state">Unable to load registered websites.</td></tr>';
        console.error("Website loading failed:", error);
    }
}

document.getElementById("addWebsiteForm").addEventListener("submit", async event => {
    event.preventDefault();

    const message = document.getElementById("websiteFormMessage");
    const button = event.currentTarget.querySelector('button[type="submit"]');
    button.disabled = true;
    message.textContent = "Registering website...";

    try {
        await fetchJSON("/websites", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                name: document.getElementById("websiteName").value.trim(),
                url: document.getElementById("websiteUrl").value.trim(),
                ownership_confirmed: document.getElementById("websiteOwnership").checked
            })
        });

        message.textContent = "Website registered. Monitoring status is Pending until it becomes reachable.";
        message.style.color = "#21865b";
        event.currentTarget.reset();
        await loadRegisteredWebsites();
    } catch (error) {
        message.textContent = error.message;
        message.style.color = "#c0392b";
    } finally {
        button.disabled = false;
    }
});

document.getElementById("registeredWebsitesTable").addEventListener("click", async event => {
    const button = event.target.closest(".delete-website-button");
    if (!button) return;

    const websiteId = button.dataset.websiteId;
    if (!confirm("Delete this registered website and its monitoring configuration?")) return;

    button.disabled = true;

    try {
        await fetchJSON(`/websites/${encodeURIComponent(websiteId)}`, {
            method: "DELETE"
        });
        await loadRegisteredWebsites();
    } catch (error) {
        alert("Could not delete website: " + error.message);
        button.disabled = false;
    }
});
