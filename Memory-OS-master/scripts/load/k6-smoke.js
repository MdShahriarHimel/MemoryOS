/**
 * MEMORY OS load smoke test (k6)
 *
 * Run: k6 run scripts/load/k6-smoke.js
 * Env:
 *   K6_API_URL      (default http://localhost:8000)
 *   K6_API_KEY      Bearer API key (required when MEMORY_OS_ALLOW_ANON=false)
 *   K6_ALLOW_ANON   set to "true" to skip auth header
 */
import http from "k6/http";
import { check, sleep } from "k6";

export const options = {
  vus: 10,
  duration: "30s",
  thresholds: {
    http_req_failed: ["rate<0.05"],
    http_req_duration: ["p(95)<2000"],
  },
};

const BASE = __ENV.K6_API_URL || "http://localhost:8000";
const API_KEY = __ENV.K6_API_KEY || "";
const ALLOW_ANON = (__ENV.K6_ALLOW_ANON || "false").toLowerCase() === "true";

function headers(extra = {}) {
  const h = { "Content-Type": "application/json", ...extra };
  if (!ALLOW_ANON && API_KEY) {
    h.Authorization = `Bearer ${API_KEY}`;
  }
  return h;
}

export default function () {
  const health = http.get(`${BASE}/v1/health`);
  check(health, { "health ok": (r) => r.status === 200 });

  const create = http.post(
    `${BASE}/v1/memory`,
    JSON.stringify({ content: `Load test memory vu=${__VU} iter=${__ITER}` }),
    { headers: headers() },
  );
  check(create, { "create ok": (r) => r.status === 201 });

  const search = http.post(
    `${BASE}/v1/memory/search`,
    JSON.stringify({ query: "load test", top_k: 5 }),
    { headers: headers() },
  );
  check(search, { "search ok": (r) => r.status === 200 });

  sleep(0.5);
}
