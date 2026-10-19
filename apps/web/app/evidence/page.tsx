"use client";

import { useSearchParams, useRouter } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { Shell } from "@/components/Shell";

type Item = { id: string; label: string; status: "pass" | "warn" | "fail"; detail: string };

function EvidenceBuilder() {
  const params = useSearchParams();
  const router = useRouter();
  const analysisId = params.get("analysis") || "";
  const [items, setItems] = useState<Item[]>([]);
  const [ready, setReady] = useState(false);
  const [ack, setAck] = useState(false);
  const [submissionMode, setSubmissionMode] = useState<"wallet" | "relay">("wallet");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!analysisId) return;
    fetch("/v1/evidence/preflight", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ analysis_id: analysisId }),
    })
      .then(async (response) => {
        if (!response.ok) throw new Error("missing");
        return response.json();
      })
      .then((body) => {
        setItems(body.items);
        setReady(body.ready);
      })
      .catch(() => setError("This analysis is not available. Run it again from the lab."));
  }, [analysisId]);

  async function createClaim() {
    setSaving(true);
    setError("");
    try {
      const response = await fetch("/v1/claims", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ analysis_id: analysisId, acknowledged: true, submission_mode: submissionMode }),
      });
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail || "Claim was not created");
      router.push(`/claims/${body.id}`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Claim was not created");
      setSaving(false);
    }
  }

  return (
    <Shell active="/lab">
      <header className="page-head">
        <div>
          <p className="kicker">Evidence builder</p>
          <h1>Checklist</h1>
        </div>
      </header>
      {!analysisId ? <p className="callout">Open this page from a finished lab run.</p> : null}
      {error ? <p className="callout fail">{error}</p> : null}
      <section className="panel">
        <h2>Required before a local claim</h2>
        <div className="checks">
          {items.map((item) => (
            <div key={item.id} className="check">
              <b className={item.status}>{item.status}</b>
              <div>
                <strong>{item.label}</strong>
                <div className="muted">{item.detail}</div>
              </div>
            </div>
          ))}
        </div>
        <label className="ack">
          <input type="checkbox" checked={ack} onChange={(event) => setAck(event.target.checked)} />
          <span>I understand this review checks the evidence package. It does not confirm a planet or a signal.</span>
        </label>
        <label className="fine">GenLayer submission
          <select value={submissionMode} onChange={event => setSubmissionMode(event.target.value as "wallet" | "relay")}>
            <option value="wallet">My wallet sends transactions (default)</option>
            <option value="relay">DeepSight relay sends transactions</option>
          </select>
        </label>
        <button className="primary" type="button" disabled={!ready || !ack || saving} onClick={createClaim}>
          {saving ? "Writing claim…" : "Create evidence claim"}
        </button>
        <p className="fine muted">{submissionMode === "wallet" ? "The claim is bound to your wallet. On its detail page, you send registration and review transactions and pay StudioNet fees." : "The relay is the on-chain claimant and pays StudioNet fees. You authorize each action with a wallet message signature."}</p>
        {!ready && items.length > 0 ? <p className="fine muted">Fix failing checklist rows before creating a claim.</p> : null}
      </section>
    </Shell>
  );
}

export default function EvidencePage() {
  return (
    <Suspense fallback={<p className="workspace muted">Loading checklist…</p>}>
      <EvidenceBuilder />
    </Suspense>
  );
}
