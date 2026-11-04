/** Dependency-free JavaScript client for AI OS (Node 18+ or modern browsers). */
export class AIOSAPIError extends Error {
  constructor(status, message) {
    super(message);
    this.name = "AIOSAPIError";
    this.status = status;
  }
}

export class AIOSClient {
  constructor({ baseUrl = "http://localhost:8000", apiKey, fetchImpl = globalThis.fetch } = {}) {
    if (typeof fetchImpl !== "function") throw new TypeError("A fetch implementation is required");
    this.baseUrl = baseUrl.replace(/\/$/, "");
    if (!this.baseUrl.endsWith("/api/v1")) this.baseUrl += "/api/v1";
    this.apiKey = apiKey;
    this.fetch = fetchImpl;
  }

  async request(path, { method = "GET", body } = {}) {
    const headers = { Accept: "application/json" };
    if (this.apiKey) headers.Authorization = `Bearer ${this.apiKey}`;
    if (body !== undefined) headers["Content-Type"] = "application/json";
    const response = await this.fetch(`${this.baseUrl}/${path.replace(/^\//, "")}`, {
      method, headers, ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    });
    const data = response.status === 204 ? null : await response.json();
    if (!response.ok) throw new AIOSAPIError(response.status, data?.error || `HTTP ${response.status}`);
    return data;
  }

  health() { return this.request("health"); }
  identity() { return this.request("me"); }
  capabilities() { return this.request("capabilities"); }
  workflowTemplates() { return this.request("workflow-templates"); }
  registerAgent(agent) { return this.request("agents", { method: "POST", body: agent }); }
  proposeObjective(objective) { return this.request("objectives", { method: "POST", body: objective }); }
  listTasks(agentId) {
    const query = agentId ? `?agent_id=${encodeURIComponent(agentId)}` : "";
    return this.request(`tasks${query}`);
  }
  claimTask(taskId, agentId) {
    return this.request(`tasks/${encodeURIComponent(taskId)}/claim`, {
      method: "POST", body: agentId ? { agent_id: agentId } : {},
    });
  }
  reportTask(taskId, report) {
    return this.request(`tasks/${encodeURIComponent(taskId)}`, { method: "PATCH", body: report });
  }
}
