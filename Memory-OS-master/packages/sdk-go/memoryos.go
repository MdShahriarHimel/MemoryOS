// Package memoryos is the official MEMORY OS Go SDK.
// MEMORY OS is model-independent; callers supply embeddings.
package memoryos

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"time"
)

type Client struct {
	BaseURL string
	APIKey  string
	http    *http.Client
}

type Option func(*Client)

func WithBaseURL(u string) Option { return func(c *Client) { c.BaseURL = u } }

func New(apiKey string, opts ...Option) *Client {
	c := &Client{
		BaseURL: envOr("MEMORY_OS_API_URL", "http://localhost:8000"),
		APIKey:  apiKey,
		http:    &http.Client{Timeout: 15 * time.Second},
	}
	for _, o := range opts {
		o(c)
	}
	return c
}

type Memory struct {
	ID         string                 `json:"id"`
	Content    string                 `json:"content"`
	MemoryType string                 `json:"memory_type"`
	Confidence float64                `json:"confidence"`
	Metadata   map[string]interface{} `json:"metadata"`
}

type CreateMemoryInput struct {
	Content    string                 `json:"content"`
	MemoryType string                 `json:"memory_type,omitempty"`
	Embedding  []float64              `json:"embedding,omitempty"`
	Metadata   map[string]interface{} `json:"metadata,omitempty"`
	Confidence float64                `json:"confidence,omitempty"`
}

type SearchInput struct {
	Query     string    `json:"query"`
	Mode      string    `json:"mode,omitempty"`
	Embedding []float64 `json:"embedding,omitempty"`
	TopK      int       `json:"top_k,omitempty"`
	SessionID string    `json:"session_id,omitempty"`
}

type APIError struct {
	Code      string `json:"code"`
	Message   string `json:"message"`
	RequestID string `json:"request_id"`
}

func (e *APIError) Error() string {
	return fmt.Sprintf("[%s] %s (request_id=%s)", e.Code, e.Message, e.RequestID)
}

func (c *Client) CreateMemory(ctx context.Context, in CreateMemoryInput) (*Memory, error) {
	var out Memory
	if err := c.do(ctx, http.MethodPost, "/v1/memory", in, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

func (c *Client) Search(ctx context.Context, in SearchInput) (map[string]interface{}, error) {
	var out map[string]interface{}
	if err := c.do(ctx, http.MethodPost, "/v1/memory/search", in, &out); err != nil {
		return nil, err
	}
	return out, nil
}

func (c *Client) Extract(ctx context.Context, content string, store bool) (map[string]interface{}, error) {
	var out map[string]interface{}
	body := map[string]interface{}{"content": content, "store": store}
	if err := c.do(ctx, http.MethodPost, "/v1/memory/extract", body, &out); err != nil {
		return nil, err
	}
	return out, nil
}

func (c *Client) BuildContext(ctx context.Context, query string) (map[string]interface{}, error) {
	var out map[string]interface{}
	body := map[string]string{"query": query}
	if err := c.do(ctx, http.MethodPost, "/v1/context", body, &out); err != nil {
		return nil, err
	}
	return out, nil
}

func (c *Client) Provenance(ctx context.Context, memoryID string) (map[string]interface{}, error) {
	var out map[string]interface{}
	if err := c.do(ctx, http.MethodGet, "/v1/memory/"+memoryID+"/provenance", nil, &out); err != nil {
		return nil, err
	}
	return out, nil
}

func (c *Client) Timeline(ctx context.Context, memoryID string) (map[string]interface{}, error) {
	var out map[string]interface{}
	if err := c.do(ctx, http.MethodGet, "/v1/memory/"+memoryID+"/timeline", nil, &out); err != nil {
		return nil, err
	}
	return out, nil
}

func (c *Client) RunBenchmark(ctx context.Context, name string, scale int) (map[string]interface{}, error) {
	var out map[string]interface{}
	body := map[string]interface{}{"name": name, "scale": scale}
	if err := c.do(ctx, http.MethodPost, "/v1/benchmarks/run", body, &out); err != nil {
		return nil, err
	}
	return out, nil
}

func (c *Client) CreateSession(ctx context.Context, agentID string) (map[string]interface{}, error) {
	var out map[string]interface{}
	body := map[string]interface{}{}
	if agentID != "" {
		body["agent_id"] = agentID
	}
	if err := c.do(ctx, http.MethodPost, "/v1/sessions", body, &out); err != nil {
		return nil, err
	}
	return out, nil
}

func (c *Client) ListSessions(ctx context.Context, limit, offset int) (map[string]interface{}, error) {
	var out map[string]interface{}
	path := fmt.Sprintf("/v1/sessions?limit=%d&offset=%d", limit, offset)
	if err := c.do(ctx, http.MethodGet, path, nil, &out); err != nil {
		return nil, err
	}
	return out, nil
}

func (c *Client) SessionEvents(ctx context.Context, sessionID string) (map[string]interface{}, error) {
	var out map[string]interface{}
	if err := c.do(ctx, http.MethodGet, "/v1/sessions/"+sessionID+"/events", nil, &out); err != nil {
		return nil, err
	}
	return out, nil
}

func (c *Client) AppendSessionEvent(ctx context.Context, sessionID, eventType, detail string) (map[string]interface{}, error) {
	var out map[string]interface{}
	body := map[string]string{"event_type": eventType, "detail": detail}
	if err := c.do(ctx, http.MethodPost, "/v1/sessions/"+sessionID+"/events", body, &out); err != nil {
		return nil, err
	}
	return out, nil
}

func (c *Client) Reflection(ctx context.Context, staleDays int) (map[string]interface{}, error) {
	var out map[string]interface{}
	path := fmt.Sprintf("/v1/operations/reflection?stale_days=%d", staleDays)
	if err := c.do(ctx, http.MethodPost, path, nil, &out); err != nil {
		return nil, err
	}
	return out, nil
}

func (c *Client) ReflectionExecute(ctx context.Context, dryRun bool, staleDays int) (map[string]interface{}, error) {
	var out map[string]interface{}
	body := map[string]interface{}{"dry_run": dryRun, "stale_days": staleDays}
	if err := c.do(ctx, http.MethodPost, "/v1/operations/reflection/execute", body, &out); err != nil {
		return nil, err
	}
	return out, nil
}

func (c *Client) do(ctx context.Context, method, path string, body, out interface{}) error {
	var buf bytes.Buffer
	if body != nil {
		if err := json.NewEncoder(&buf).Encode(body); err != nil {
			return err
		}
	}
	req, err := http.NewRequestWithContext(ctx, method, c.BaseURL+path, &buf)
	if err != nil {
		return err
	}
	req.Header.Set("Content-Type", "application/json")
	if c.APIKey != "" {
		req.Header.Set("Authorization", "Bearer "+c.APIKey)
	}
	resp, err := c.http.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode >= 400 {
		var env struct {
			Error APIError `json:"error"`
		}
		_ = json.NewDecoder(resp.Body).Decode(&env)
		return &env.Error
	}
	if out != nil {
		return json.NewDecoder(resp.Body).Decode(out)
	}
	return nil
}

func envOr(k, def string) string {
	if v := os.Getenv(k); v != "" {
		return v
	}
	return def
}
