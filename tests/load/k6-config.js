# ---- Load Testing Configuration ------------------------------------------
# k6 load test script for API endpoints.
# Install k6: https://k6.io/docs/get-started/installation/
# Run: k6 run tests/load/k6-config.js

import http from "k6/http";
import { check, sleep } from "k6";

export const options = {
    stages: [
        { duration: "30s", target: 10 },   // Ramp up to 10 users
        { duration: "1m", target: 50 },    // Ramp up to 50 users
        { duration: "2m", target: 50 },    // Stay at 50 users
        { duration: "30s", target: 100 },  // Spike to 100 users
        { duration: "1m", target: 100 },   // Stay at 100
        { duration: "30s", target: 0 },    // Ramp down
    ],
    thresholds: {
        http_req_duration: ["p(95)<500"],     // 95% of requests under 500ms
        http_req_failed: ["rate<0.01"],       // Less than 1% failure rate
        http_reqs: ["rate>100"],              // At least 100 req/s
    },
};

const BASE_URL = __ENV.BASE_URL || "http://localhost:8000";

export default function () {
    // Health check
    const healthRes = http.get(`${BASE_URL}/api/v1/health`);
    check(healthRes, {
        "health status 200": (r) => r.status === 200,
        "health response time < 100ms": (r) => r.timings.duration < 100,
    });

    // Root endpoint
    const rootRes = http.get(`${BASE_URL}/`);
    check(rootRes, {
        "root status 200": (r) => r.status === 200,
    });

    // Metrics endpoint
    const metricsRes = http.get(`${BASE_URL}/api/v1/metrics`);
    check(metricsRes, {
        "metrics status 200": (r) => r.status === 200,
    });

    // List cases (requires auth in production)
    const casesRes = http.get(`${BASE_URL}/api/v1/cases`, {
        headers: { "Authorization": `Bearer ${__ENV.AUTH_TOKEN || "test"}` },
    });
    check(casesRes, {
        "cases responds": (r) => r.status < 500,
    });

    sleep(1);
}
