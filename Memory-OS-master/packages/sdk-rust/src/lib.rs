//! Official MEMORY OS Rust SDK (v0.3). Model-independent; callers supply embeddings.

use serde::{Deserialize, Serialize};

#[derive(Debug, thiserror::Error)]
pub enum Error {
    #[error("http error: {0}")]
    Http(#[from] reqwest::Error),
    #[error("api error [{code}] {message} (request_id={request_id:?})")]
    Api { code: String, message: String, request_id: Option<String> },
}

#[derive(Serialize)]
pub struct CreateMemory {
    pub content: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub memory_type: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub embedding: Option<Vec<f32>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub confidence: Option<f32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub session_id: Option<String>,
}

#[derive(Serialize)]
pub struct Search {
    pub query: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub mode: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub embedding: Option<Vec<f32>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub top_k: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub session_id: Option<String>,
}

#[derive(Serialize)]
pub struct SessionEventInput {
    pub event_type: String,
    pub detail: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub latency_ms: Option<u32>,
}

#[derive(Deserialize)]
struct ApiErrorEnvelope { error: ApiError }
#[derive(Deserialize)]
struct ApiError { code: String, message: String, request_id: Option<String> }

pub struct MemoryOS {
    base_url: String,
    api_key: Option<String>,
    http: reqwest::Client,
}

impl MemoryOS {
    pub fn new(api_key: Option<String>) -> Self {
        let base_url = std::env::var("MEMORY_OS_API_URL")
            .unwrap_or_else(|_| "http://localhost:8000".to_string());
        Self { base_url, api_key, http: reqwest::Client::new() }
    }

    pub async fn create_memory(&self, input: CreateMemory) -> Result<serde_json::Value, Error> {
        self.post("/v1/memory", &input).await
    }

    pub async fn search(&self, input: Search) -> Result<serde_json::Value, Error> {
        self.post("/v1/memory/search", &input).await
    }

    pub async fn build_context(&self, query: &str) -> Result<serde_json::Value, Error> {
        self.post("/v1/context", &serde_json::json!({ "query": query })).await
    }

    pub async fn create_session(&self) -> Result<serde_json::Value, Error> {
        self.post("/v1/sessions", &serde_json::json!({})).await
    }

    pub async fn session_events(&self, session_id: &str) -> Result<serde_json::Value, Error> {
        self.get(&format!("/v1/sessions/{session_id}/events")).await
    }

    pub async fn append_session_event(
        &self, session_id: &str, input: SessionEventInput,
    ) -> Result<serde_json::Value, Error> {
        self.post(&format!("/v1/sessions/{session_id}/events"), &input).await
    }

    pub async fn reflection(&self, stale_days: u32) -> Result<serde_json::Value, Error> {
        self.post(&format!("/v1/operations/reflection?stale_days={stale_days}"), &serde_json::json!({})).await
    }

    pub async fn reflection_execute(&self, dry_run: bool) -> Result<serde_json::Value, Error> {
        self.post("/v1/operations/reflection/execute", &serde_json::json!({
            "dry_run": dry_run,
            "stale_days": 90,
        })).await
    }

    async fn get(&self, path: &str) -> Result<serde_json::Value, Error> {
        let mut req = self.http.get(format!("{}{}", self.base_url, path));
        if let Some(k) = &self.api_key {
            req = req.bearer_auth(k);
        }
        self.handle(req.send().await?).await
    }

    async fn post<T: Serialize>(&self, path: &str, body: &T) -> Result<serde_json::Value, Error> {
        let mut req = self.http.post(format!("{}{}", self.base_url, path)).json(body);
        if let Some(k) = &self.api_key {
            req = req.bearer_auth(k);
        }
        self.handle(req.send().await?).await
    }

    async fn handle(&self, resp: reqwest::Response) -> Result<serde_json::Value, Error> {
        if resp.status().is_client_error() || resp.status().is_server_error() {
            let env: ApiErrorEnvelope = resp.json().await?;
            return Err(Error::Api {
                code: env.error.code,
                message: env.error.message,
                request_id: env.error.request_id,
            });
        }
        Ok(resp.json().await?)
    }
}
