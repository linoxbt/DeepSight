export async function api<T = any>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(path, { ...init, credentials: "same-origin" });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(typeof body.detail === "string" ? body.detail : `Request failed (${response.status})`);
  return body as T;
}

export async function runJob(kind: "analysis" | "import" | "radio", input: Record<string, string> = {}, onStatus?: (text: string) => void) {
  const job = await api("/v1/jobs", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ kind, ...input }) });
  onStatus?.("Queued");
  // The job persists independently of this page and can be resumed by its ID.
  sessionStorage.setItem("deepsight-job", job.id);
  return waitForJob(job.id, onStatus);
}

export async function waitForJob(id: string, onStatus?: (text: string) => void) {
  for (let attempt = 0; attempt < 900; attempt++) {
    const job = await api(`/v1/jobs/${id}`);
    onStatus?.(job.status === "running" ? "Analyzing" : "Queued");
    if (job.status === "succeeded") { sessionStorage.removeItem("deepsight-job"); return job.result; }
    if (job.status === "failed") { sessionStorage.removeItem("deepsight-job"); throw new Error(job.error); }
    await new Promise(resolve => setTimeout(resolve, 2000));
  }
  throw new Error(`Job ${id} is still running. Reopen the lab to resume.`);
}
