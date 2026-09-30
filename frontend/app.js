// Step 1: Register Service Worker Network Proxy
if ("serviceWorker" in navigator) {
    window.addEventListener("load", async () => {
        try {
            const registration = await navigator.serviceWorker.register("./proxy-worker.js");
            console.log("[Frontend Proxy] Registered successfully with scope:", registration.scope);
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

// Step 3: Trigger the Proxy using relative URLs (intercepted by proxy-worker.js)
const API_URL = "/api/v1/routes/optimize/";
const HEALTH_URL = "/api/health/";

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

// Frontend in-memory response cache with 5-minute TTL
const clientCache = new Map();
const CLIENT_CACHE_TTL_MS = 5 * 60 * 1000; // 5 minutes

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

const form = document.getElementById("route-form");
const errorBox = document.getElementById("error");
const loading = document.getElementById("loading");
const results = document.getElementById("results");

form.addEventListener("submit", async (event) => {
    event.preventDefault();

    const start = document.getElementById("start").value.trim();
    const finish = document.getElementById("finish").value.trim();

    clearError();

    // Check client cache first
    const cachedData = getCachedRoute(start, finish);
    if (cachedData) {
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

            body: JSON.stringify({
                start,
                finish,
            }),
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(
                data.error || "Unable to calculate route."
            );
        }

        setCachedRoute(start, finish, data);
        renderRoute(data);
        renderResults(data);

    } catch (error) {
        showError(error.message);
    } finally {
        setLoading(false);
    }
});

function renderRoute(data) {

    if (routeLayer) {
        map.removeLayer(routeLayer);
    }

    markers.forEach((marker) => {
        map.removeLayer(marker);
    });

    markers = [];

    routeLayer = L.geoJSON(
        data.route.geometry,
        {
            style: {
                color: "#b8f35a",
                weight: 5,
                opacity: 0.9,
            },
        }
    ).addTo(map);

    map.fitBounds(
        routeLayer.getBounds(),
        {
            padding: [40, 40],
        }
    );

    addEndpointMarker(
        data.start,
        "START"
    );

    addEndpointMarker(
        data.finish,
        "FINISH"
    );

    if (Array.isArray(data.fuel_stops)) {
        data.fuel_stops.forEach(
            (stop) => {
                if (stop.latitude == null || stop.longitude == null) {
                    return;
                }

                const marker = L.circleMarker(
                    [
                        stop.latitude,
                        stop.longitude,
                    ],
                    {
                        radius: 7,
                        color: "#080b0d",
                        weight: 2,
                        fillColor: "#b8f35a",
                        fillOpacity: 1,
                    }
                )
                .addTo(map);

                marker.bindPopup(`
                    <strong>${stop.name}</strong><br>
                    ${stop.city}, ${stop.state}<br>
                    $${stop.price_per_gallon.toFixed(2)}/gal
                `);

                markers.push(marker);
            }
        );
    }
}

function renderResults(data) {

    results.classList.remove("hidden");

    document.getElementById("distance").textContent =
        `${data.route.distance_miles.toFixed(1)} mi`;

    document.getElementById("duration").textContent =
        formatDuration(data.route.duration_minutes);

    document.getElementById("fuel-used").textContent =
        `${data.fuel.consumed_gallons.toFixed(1)} gal`;

    document.getElementById("fuel-cost").textContent =
        `$${data.fuel.total_cost.toFixed(2)}`;

    document.getElementById("stop-count").textContent =
        `${data.fuel_stops.length} STOPS`;

    const list = document.getElementById("stops-list");

    if (data.fuel_stops.length === 0) {
        list.innerHTML = `
            <div class="stop-empty">
                No refueling stops needed. Vehicle range (500 mi) is sufficient for this route.
            </div>
        `;
        return;
    }

    list.innerHTML = data.fuel_stops
        .map((stop, index) => `
            <div class="stop">

                <div class="stop-number">
                    ${String(index + 1).padStart(2, "0")}
                </div>

                <div>
                    <div class="stop-name">
                        ${stop.name}
                    </div>

                    <div class="stop-location">
                        ${stop.city}, ${stop.state}
                    </div>
                </div>

                <div class="stop-price">
                    $${stop.price_per_gallon.toFixed(2)}/gal
                </div>

                <div class="stop-distance">
                    ${stop.route_mile.toFixed(1)} mi
                </div>

            </div>
        `)
        .join("");
}

function formatDuration(minutes) {

    const hours = Math.floor(minutes / 60);
    const remaining = Math.round(minutes % 60);

    return `${hours}h ${remaining}m`;
}

function addEndpointMarker(location, label) {
    if (!location || location.latitude == null || location.longitude == null) {
        return;
    }

    const marker = L.marker([
        location.latitude,
        location.longitude,
    ])
    .addTo(map);

    marker.bindPopup(`<strong>${label}</strong><br>${location.label || ""}`);

    markers.push(marker);
}

function setLoading(value) {
    loading.classList.toggle("hidden", !value);
    const submitBtn = form.querySelector('button[type="submit"]');
    if (submitBtn) {
        submitBtn.disabled = value;
    }
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
            if (text) text.textContent = "API ONLINE";
        } else {
            dot?.classList.add("offline");
            if (text) text.textContent = "API DEGRADED";
        }
    } catch {
        // If server is not yet running, keep default UI
    }
}
