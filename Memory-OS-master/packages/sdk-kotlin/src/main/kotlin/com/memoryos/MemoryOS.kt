package com.memoryos

import kotlinx.serialization.json.*
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import java.util.concurrent.TimeUnit

/** Official MEMORY OS Kotlin SDK (v0.3). Model-independent; callers supply embeddings. */
class MemoryOSException(val code: String, message: String, val requestId: String?) :
    RuntimeException("[$code] $message (request_id=$requestId)")

class MemoryOS(
    private val apiKey: String? = null,
    private val baseUrl: String = System.getenv("MEMORY_OS_API_URL") ?: "http://localhost:8000",
) {
    private val http = OkHttpClient.Builder()
        .callTimeout(15, TimeUnit.SECONDS).build()
    private val jsonMedia = "application/json".toMediaType()

    fun createMemory(body: JsonObject): JsonElement = post("/v1/memory", body)
    fun search(body: JsonObject): JsonElement = post("/v1/memory/search", body)
    fun extract(body: JsonObject): JsonElement = post("/v1/memory/extract", body)
    fun buildContext(body: JsonObject): JsonElement = post("/v1/context", body)
    fun timeline(memoryId: String): JsonElement = get("/v1/memory/$memoryId/timeline")
    fun provenance(memoryId: String): JsonElement = get("/v1/memory/$memoryId/provenance")

    fun createSession(body: JsonObject = buildJsonObject {}): JsonElement = post("/v1/sessions", body)
    fun listSessions(limit: Int = 25, offset: Int = 0): JsonElement =
        get("/v1/sessions?limit=$limit&offset=$offset")
    fun sessionEvents(sessionId: String): JsonElement = get("/v1/sessions/$sessionId/events")
    fun appendSessionEvent(sessionId: String, body: JsonObject): JsonElement =
        post("/v1/sessions/$sessionId/events", body)

    fun reflection(staleDays: Int = 90): JsonElement =
        post("/v1/operations/reflection?stale_days=$staleDays", buildJsonObject {})
    fun reflectionExecute(body: JsonObject): JsonElement =
        post("/v1/operations/reflection/execute", body)

    private fun get(path: String): JsonElement = request("GET", path, null)
    private fun post(path: String, body: JsonObject): JsonElement = request("POST", path, body)

    private fun request(method: String, path: String, body: JsonObject?): JsonElement {
        val reqBuilder = Request.Builder().url("$baseUrl$path")
            .header("Content-Type", "application/json")
        apiKey?.let { reqBuilder.header("Authorization", "Bearer $it") }
        if (method == "POST") {
            reqBuilder.post((body ?: buildJsonObject {}).toString().toRequestBody(jsonMedia))
        } else {
            reqBuilder.get()
        }

        http.newCall(reqBuilder.build()).execute().use { resp ->
            val text = resp.body?.string() ?: "{}"
            val node = Json.parseToJsonElement(text)
            if (!resp.isSuccessful) {
                val err = node.jsonObject["error"]!!.jsonObject
                throw MemoryOSException(
                    err["code"]?.jsonPrimitive?.content ?: "UNKNOWN",
                    err["message"]?.jsonPrimitive?.content ?: "error",
                    err["request_id"]?.jsonPrimitive?.contentOrNull,
                )
            }
            return node
        }
    }
}
