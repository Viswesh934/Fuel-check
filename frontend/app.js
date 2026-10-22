// Step 1: Register Service Worker Network Proxy (for Codespaces & Same-Origin requests)
if ("serviceWorker" in navigator) {
    window.addEventListener("load", async () => {
        try {
            const registration = await navigator.serviceWorker.register("./proxy-worker.js");
            console.log("[Frontend Proxy] Registered with scope:", registration.scope);
            checkHealth();
        } catch (error) {
            console.error("[Frontend Proxy] Registration failed:", error);
            checkHealth();
        }
    });
} else {
    window.addEventListener("load", () => {
        checkHealth();
    });
}

// API Endpoints
const API_URL = "/api/v1/routes/optimize/";
const VOICE_API_URL = "/api/v1/voice/query/";
const HEALTH_URL = "/api/health/";

// Initialize Leaflet Map
const map = L.map("map", {
    zoomControl: false,
}).setView([39.8283, -98.5795], 4);

L.control.zoom({
    position: "bottomright",
}).addTo(map);

L.tileLayer(
    "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}",
    {
        maxZoom: 16,
        attribution: "Tiles &copy; Esri &mdash; Esri, DeLorme, NAVTEQ",
    }
).addTo(map);

L.tileLayer(
    "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Reference/MapServer/tile/{z}/{y}/{x}",
    {
        maxZoom: 16,
    }
).addTo(map);

let routeLayer = null;
let markers = [];
let currentRouteData = null;

// Client Cache
const clientCache = new Map();
const CLIENT_CACHE_TTL_MS = 5 * 60 * 1000;

function getCachedRoute(start, finish) {
    const key = `${start.trim().toLowerCase()}|${finish.trim().toLowerCase()}`;
    const entry = clientCache.get(key);
    if (!entry) return null;
    if (Date.now() - entry.timestamp > CLIENT_CACHE_TTL_MS) {
        clientCache.delete(key);
        return null;
    }
    return entry.data;
}

function setCachedRoute(start, finish, data) {
    const key = `${start.trim().toLowerCase()}|${finish.trim().toLowerCase()}`;
    clientCache.set(key, { timestamp: Date.now(), data });
}

// Elements
const form = document.getElementById("route-form");
const errorBox = document.getElementById("error");
const loading = document.getElementById("loading");
const results = document.getElementById("results");
const voiceForm = document.getElementById("voice-query-form");
const voiceInput = document.getElementById("voice-input");
const voiceResponse = document.getElementById("voice-response");
const voiceAnswerText = document.getElementById("voice-answer-text");
const voiceAiBadge = document.getElementById("voice-ai-badge");
const speakBtn = document.getElementById("speak-answer-btn");

// Handle Route Planning Submission
form.addEventListener("submit", async (event) => {
    event.preventDefault();

    const start = document.getElementById("start").value.trim();
    const finish = document.getElementById("finish").value.trim();

    clearError();

    // Check client cache first
    const cachedData = getCachedRoute(start, finish);
    if (cachedData) {
        currentRouteData = cachedData;
        renderRoute(cachedData);
        renderResults(cachedData);
        return;
    }

    setLoading(true);

    try {
        const response = await fetch(API_URL, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({ start, finish }),
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || "Unable to calculate route.");
        }

        currentRouteData = data;
        setCachedRoute(start, finish, data);
        renderRoute(data);
        renderResults(data);

    } catch (error) {
        showError(error.message);
    } finally {
        setLoading(false);
    }
});

// Render Route Polyline, Fuel Stops & Travel Event Markers on Map
function renderRoute(data) {
    if (routeLayer) {
        map.removeLayer(routeLayer);
    }

    markers.forEach((marker) => {
        map.removeLayer(marker);
    });
    markers = [];

    // Render Neon Green Route Polyline
    routeLayer = L.geoJSON(data.route.geometry, {
        style: {
            color: "#b8f35a",
            weight: 5,
            opacity: 0.9,
        },
    }).addTo(map);

    map.fitBounds(routeLayer.getBounds(), {
        padding: [40, 40],
    });

    addEndpointMarker(data.start, "START");
    addEndpointMarker(data.finish, "FINISH");

    // Render Fuel Stops (Accent Green Circles)
    if (Array.isArray(data.fuel_stops)) {
        data.fuel_stops.forEach((stop) => {
            if (stop.latitude == null || stop.longitude == null) return;

            const marker = L.circleMarker([stop.latitude, stop.longitude], {
                radius: 8,
                color: "#080b0d",
                weight: 2,
                fillColor: "#b8f35a",
                fillOpacity: 1,
            }).addTo(map);

            marker.bindPopup(`
                <div style="font-family:sans-serif; min-width:180px;">
                    <div style="color:#8dbd35; font-size:10px; font-weight:700; letter-spacing:1px;">FUEL STOP</div>
                    <strong style="font-size:13px; color:#111;">${stop.name}</strong><br>
                    <span style="font-size:11px; color:#555;">${stop.city}, ${stop.state}</span><br>
                    <span style="font-size:13px; font-weight:700; color:#111;">$${stop.price_per_gallon.toFixed(2)}/gal</span>
                    <span style="font-size:11px; color:#666;"> &bull; Mile ${stop.route_mile.toFixed(1)}</span>
                </div>
            `);

            markers.push(marker);
        });
    }

    // Render Travel Events on Map (Distinct hazard pins)
    const travelEvents = data.travel_events;
    if (travelEvents && Array.isArray(travelEvents.all_candidate_events)) {
        travelEvents.all_candidate_events.forEach((evt) => {
            if (evt.latitude == null || evt.longitude == null) return;

            const isAffecting = evt.affects_route;
            const color = evt.severity === "CRITICAL" ? "#ff6b6b" : (evt.severity === "WARNING" ? "#ffb84d" : "#4da6ff");
            const iconSymbol = evt.type === "ROAD_CLOSURE" ? "⛔" : (evt.type === "WEATHER_HAZARD" ? "⚠️" : "🚧");

            const iconHtml = `
                <div style="
                    background:${color};
                    color:#080b0d;
                    width:26px;
                    height:26px;
                    border-radius:50%;
                    display:grid;
                    place-items:center;
                    font-size:13px;
                    font-weight:bold;
                    box-shadow:0 0 10px ${color};
                    border:2px solid #080b0d;
                    opacity: ${isAffecting ? "1.0" : "0.55"};
                ">${iconSymbol}</div>
            `;

            const customIcon = L.divIcon({
                html: iconHtml,
                className: "custom-hazard-icon",
                iconSize: [26, 26],
                iconAnchor: [13, 13],
            });

            const marker = L.marker([evt.latitude, evt.longitude], { icon: customIcon }).addTo(map);

            const simulatedBadge = evt.is_simulated
                ? `<span style="background:#444; color:#fff; font-size:9px; padding:2px 5px; border-radius:2px;">[SIMULATED EVENT]</span>`
                : `<span style="background:#059669; color:#fff; font-size:9px; padding:2px 5px; border-radius:2px;">[LIVE VERIFIED]</span>`;

            marker.bindPopup(`
                <div style="font-family:sans-serif; min-width:220px; line-height:1.4;">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
                        <span style="color:${color}; font-size:10px; font-weight:700;">${evt.severity} &bull; ${evt.type}</span>
                        ${simulatedBadge}
                    </div>
                    <strong style="font-size:13px; color:#111;">${evt.title}</strong><br>
                    <div style="font-size:11px; color:#444; margin:4px 0;">${evt.description}</div>
                    <div style="font-size:11px; color:#111; font-weight:600;">
                        ${isAffecting ? `🔴 Affects Route near Mile ${evt.route_mile || "N/A"}` : `⚪ Off Route (${evt.distance_to_route_miles} mi away)`}
                    </div>
                    <div style="font-size:11px; color:#666;">Delay: +${evt.estimated_delay_minutes} min</div>
                </div>
            `);

            markers.push(marker);
        });
    }
}

// Render Results & Co-Pilot Panels
function renderResults(data) {
    results.classList.remove("hidden");

    // Metrics
    document.getElementById("distance").textContent = `${data.route.distance_miles.toFixed(1)} mi`;
    document.getElementById("duration").textContent = formatDuration(data.route.duration_minutes);
    document.getElementById("fuel-used").textContent = `${data.fuel.consumed_gallons.toFixed(1)} gal`;
    document.getElementById("fuel-cost").textContent = `$${data.fuel.total_cost.toFixed(2)}`;

    // Travel Alert Metric
    const travelEvents = data.travel_events || {};
    const activeAlerts = travelEvents.active_route_alerts || [];
    const alertMetricCard = document.getElementById("hazard-metric-card");
    const alertSummary = document.getElementById("alert-summary");
    const alertBadge = document.getElementById("alert-badge");

    if (activeAlerts.length > 0) {
        alertSummary.textContent = `${activeAlerts.length} HAZARD${activeAlerts.length > 1 ? "S" : ""} (+${travelEvents.total_delay_minutes}m)`;
        alertMetricCard.classList.add("highlight-warning");
        alertBadge.textContent = `${activeAlerts.length} ACTIVE ALERTS`;
        alertBadge.classList.add("has-alerts");
    } else {
        alertSummary.textContent = `CLEAR (0)`;
        alertMetricCard.classList.remove("highlight-warning");
        alertBadge.textContent = `ROUTE CLEAR`;
        alertBadge.classList.remove("has-alerts");
    }

    // Co-Pilot Briefing
    const briefingBox = document.getElementById("copilot-briefing");
    const briefingText = document.getElementById("briefing-text");
    const aiModelTag = document.getElementById("ai-model-tag");

    const copilotAdv = data.copilot_advisory || {};
    briefingText.textContent = copilotAdv.message || "Route analyzed. Proceed with normal caution.";
    aiModelTag.textContent = copilotAdv.llm_used ? `AWS BEDROCK (${copilotAdv.model})` : `DETERMINISTIC CO-PILOT (0 LLM COST)`;

    if (activeAlerts.length > 0) {
        briefingBox.classList.add("hazard-active");
    } else {
        briefingBox.classList.remove("hazard-active");
    }

    // Render Events List
    renderEventsList(activeAlerts, travelEvents.all_candidate_events || []);

    // Render Fuel Stops
    renderFuelStops(data.fuel_stops || []);
}

function renderEventsList(activeAlerts, allEvents) {
    const list = document.getElementById("events-list");

    if (!activeAlerts || activeAlerts.length === 0) {
        list.innerHTML = `
            <div class="stop-empty">
                ✓ No active road closures or weather hazards intersect your route corridor.
            </div>
        `;
        return;
    }

    list.innerHTML = activeAlerts.map((evt) => {
        const severityClass = evt.severity.toLowerCase();
        return `
            <div class="event-card severity-${severityClass}">
                <div class="event-header">
                    <span class="event-title">${evt.title}</span>
                    <div class="event-badges">
                        <span class="badge-mini ${severityClass}">${evt.severity}</span>
                        <span class="badge-mini simulated">[SIMULATED]</span>
                    </div>
                </div>
                <div class="event-meta">
                    <span>📍 Mile ${evt.route_mile != null ? evt.route_mile.toFixed(1) : "N/A"} (${evt.corridor})</span>
                    <span>⏱️ +${evt.estimated_delay_minutes} min delay</span>
                </div>
                <p class="event-desc">${evt.description}</p>
                <p class="event-action">👉 Co-Pilot Advice: ${evt.recommended_action}</p>
            </div>
        `;
    }).join("");
}

function renderFuelStops(fuelStops) {
    document.getElementById("stop-count").textContent = `${fuelStops.length} STOPS`;
    const list = document.getElementById("stops-list");

    if (fuelStops.length === 0) {
        list.innerHTML = `
            <div class="stop-empty">
                Vehicle starting tank (500-mile range) is sufficient for this route. Zero intermediate fuel purchases required.
            </div>
        `;
        return;
    }

    list.innerHTML = fuelStops.map((stop, index) => `
        <div class="stop">
            <div class="stop-number">${String(index + 1).padStart(2, "0")}</div>
            <div>
                <div class="stop-name">${stop.name}</div>
                <div class="stop-location">${stop.city}, ${stop.state}</div>
            </div>
            <div class="stop-price">$${stop.price_per_gallon.toFixed(2)}/gal</div>
            <div class="stop-distance">Mile ${stop.route_mile.toFixed(1)}</div>
        </div>
    `).join("");
}

// Bolna Voice Interaction Query Form
voiceForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const query = voiceInput.value.trim();
    if (!query) return;

    await executeVoiceQuery(query);
});

async function executeVoiceQuery(query) {
    const start = document.getElementById("start").value.trim() || "Chicago, IL";
    const finish = document.getElementById("finish").value.trim() || "Little Rock, AR";

    voiceAnswerText.textContent = "Bolna Co-Pilot thinking...";
    voiceResponse.classList.remove("hidden");

    try {
        const res = await fetch(VOICE_API_URL, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ query, start, finish }),
        });

        const data = await res.json();
        if (!res.ok) {
            throw new Error(data.error || "Voice service unavailable.");
        }

        voiceAnswerText.textContent = data.spoken_answer;
        voiceAiBadge.textContent = data.llm_used ? `AWS BEDROCK (${data.ai_model})` : "DETERMINISTIC RULES";

        // Speak aloud using browser TTS
        speakText(data.spoken_answer);

    } catch (err) {
        voiceAnswerText.textContent = `Error: ${err.message}`;
    }
}

function speakText(text) {
    if ("speechSynthesis" in window) {
        window.speechSynthesis.cancel();
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.rate = 1.05;
        utterance.pitch = 1.0;
        window.speechSynthesis.speak(utterance);
    }
}

speakBtn.addEventListener("click", () => {
    const text = voiceAnswerText.textContent;
    if (text) {
        speakText(text);
    }
});

function askPresetQuery(text) {
    voiceInput.value = text;
    executeVoiceQuery(text);
}

function setRoute(start, finish) {
    document.getElementById("start").value = start;
    document.getElementById("finish").value = finish;
    form.dispatchEvent(new Event("submit"));
}

function formatDuration(minutes) {
    const hours = Math.floor(minutes / 60);
    const remaining = Math.round(minutes % 60);
    return `${hours}h ${remaining}m`;
}

function addEndpointMarker(location, label) {
    if (!location || location.latitude == null || location.longitude == null) return;

    const marker = L.marker([location.latitude, location.longitude]).addTo(map);
    marker.bindPopup(`<strong>${label}</strong><br>${location.label || ""}`);
    markers.push(marker);
}

function setLoading(value) {
    loading.classList.toggle("hidden", !value);
    const submitBtn = form.querySelector('button[type="submit"]');
    if (submitBtn) submitBtn.disabled = value;
}

function showError(message) {
    errorBox.textContent = message;
    errorBox.classList.remove("hidden");
}

function clearError() {
    errorBox.classList.add("hidden");
    errorBox.textContent = "";
}

async function checkHealth() {
    const dot = document.querySelector(".status-dot");
    const text = document.getElementById("api-status-text");
    try {
        const res = await fetch(HEALTH_URL, { method: "GET" });
        if (res.ok) {
            dot?.classList.remove("offline");
            if (text) text.textContent = "CO-PILOT ONLINE (OSRM + NOMINATIM)";
        } else {
            dot?.classList.add("offline");
            if (text) text.textContent = "CO-PILOT DEGRADED";
        }
    } catch {
        // Dev server may not be running yet
    }
}
