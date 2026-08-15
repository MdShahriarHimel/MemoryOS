package com.memoryos;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.Map;

/**
 * Official MEMORY OS Java SDK (v0.3). Model-independent; callers supply embeddings.
 */
public class MemoryOS {
    private final String baseUrl;
    private final String apiKey;
    private final HttpClient http = HttpClient.newBuilder()
            .connectTimeout(Duration.ofSeconds(15)).build();
    private final ObjectMapper mapper = new ObjectMapper();

    public MemoryOS(String apiKey) {
        this(apiKey, System.getenv().getOrDefault("MEMORY_OS_API_URL", "http://localhost:8000"));
    }

    public MemoryOS(String apiKey, String baseUrl) {
        this.apiKey = apiKey;
        this.baseUrl = baseUrl;
    }

    public static class ApiException extends RuntimeException {
        public final String code;
        public final String requestId;
        public ApiException(String code, String message, String requestId) {
            super("[" + code + "] " + message + " (request_id=" + requestId + ")");
            this.code = code;
            this.requestId = requestId;
        }
    }

    public JsonNode createMemory(Map<String, Object> input) { return post("/v1/memory", input); }
    public JsonNode search(Map<String, Object> input) { return post("/v1/memory/search", input); }
    public JsonNode extract(Map<String, Object> input) { return post("/v1/memory/extract", input); }
    public JsonNode buildContext(Map<String, Object> input) { return post("/v1/context", input); }
    public JsonNode timeline(String memoryId) { return get("/v1/memory/" + memoryId + "/timeline"); }
    public JsonNode provenance(String memoryId) { return get("/v1/memory/" + memoryId + "/provenance"); }

    public JsonNode createSession(Map<String, Object> input) { return post("/v1/sessions", input); }
    public JsonNode listSessions(int limit, int offset) {
        return get("/v1/sessions?limit=" + limit + "&offset=" + offset);
    }
    public JsonNode sessionEvents(String sessionId) { return get("/v1/sessions/" + sessionId + "/events"); }
    public JsonNode appendSessionEvent(String sessionId, Map<String, Object> input) {
        return post("/v1/sessions/" + sessionId + "/events", input);
    }

    public JsonNode reflection(int staleDays) {
        return post("/v1/operations/reflection?stale_days=" + staleDays, Map.of());
    }
    public JsonNode reflectionExecute(Map<String, Object> input) {
        return post("/v1/operations/reflection/execute", input);
    }

    private JsonNode get(String path) { return request("GET", path, null); }
    private JsonNode post(String path, Map<String, Object> body) { return request("POST", path, body); }

    private JsonNode request(String method, String path, Map<String, Object> body) {
        try {
            HttpRequest.Builder b = HttpRequest.newBuilder()
                    .uri(URI.create(baseUrl + path))
                    .timeout(Duration.ofSeconds(15))
                    .header("Content-Type", "application/json");
            if (apiKey != null && !apiKey.isEmpty()) {
                b.header("Authorization", "Bearer " + apiKey);
            }
            if ("POST".equals(method)) {
                String json = mapper.writeValueAsString(body != null ? body : Map.of());
                b.POST(HttpRequest.BodyPublishers.ofString(json));
            } else {
                b.GET();
            }
            HttpResponse<String> resp = http.send(b.build(), HttpResponse.BodyHandlers.ofString());
            JsonNode node = mapper.readTree(resp.body());
            if (resp.statusCode() >= 400) {
                JsonNode err = node.get("error");
                throw new ApiException(
                        err.path("code").asText("UNKNOWN"),
                        err.path("message").asText("error"),
                        err.path("request_id").asText(null));
            }
            return node;
        } catch (ApiException e) {
            throw e;
        } catch (Exception e) {
            throw new RuntimeException(e);
        }
    }
}
