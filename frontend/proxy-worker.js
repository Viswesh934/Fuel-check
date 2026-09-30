/**
 * Frontend Service Worker Network Proxy
 *
 * Uses existing origin since frontend and backend share the same domain.
 * Intercepts /api/* requests and proxies them cleanly within the browser.
 */

const urlParams = new URL(self.location.href).searchParams;
const BACKEND_TARGET = (urlParams.get("backend") || self.location.origin).replace(/\/+$/, "");

// Ensure the Service Worker activates immediately without waiting for reload
self.addEventListener("install", (event) => {
    self.skipWaiting();
});

self.addEventListener("activate", (event) => {
    event.waitUntil(clients.claim());
});

// Intercept fetch requests
self.addEventListener("fetch", (event) => {
    const requestUrl = new URL(event.request.url);

    // Intercept anything starting with /api
    if (requestUrl.pathname.startsWith("/api")) {
        const proxyTargetUrl = `${BACKEND_TARGET}${requestUrl.pathname}${requestUrl.search}`;

        console.log(`[Frontend Proxy] Intercepting: ${requestUrl.pathname} -> Forwarding to: ${proxyTargetUrl}`);

        event.respondWith(
            (async () => {
                let body = null;
                if (event.request.method !== "GET" && event.request.method !== "HEAD") {
                    body = await event.request.clone().blob();
                }

                const modifiedRequest = new Request(proxyTargetUrl, {
                    method: event.request.method,
                    headers: event.request.headers,
                    body: body,
                    referrer: event.request.referrer,
                    mode: "cors",
                    credentials: event.request.credentials,
                });

                return fetch(modifiedRequest);
            })()
        );
    }
});
