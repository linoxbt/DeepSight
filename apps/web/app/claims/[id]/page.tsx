"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { Shell } from "@/components/Shell";

type Claim = {
  id: string;
  status: string;
  protocol_result: string;
  rationale: string;
  scientific_status: string;
  scientific_confirmation: boolean;
  manifest_hash: string;
  chain_status: string;
  chain_note: string;
  chain_claim_id: string;
  chain_tx: string;
  target_id: string;
  policy_version: string;
  manifest?: {
    limitations: string[];
    archive: { name: string };
    metrics: { name: string; value: number; unit: string; uncertainty: number | null }[];
  };
};

type Event = { status: string; note: string; observed_at: string };

export default function ClaimDetailPage() {
  const params = useParams<{ id: string }>();
  const [claim, setClaim] = useState<Claim | null>(null);
  const [events, setEvents] = useState<Event[]>([]);
  const [finality, setFinality] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");
  const [reason, setReason] = useState("");

  async function load() {
    const [claimResponse, timelineResponse, finalityResponse] = await Promise.all([
      fetch(`/v1/claims/${params.id}`),
      fetch(`/v1/claims/${params.id}/timeline`),
      fetch(`/v1/claims/${params.id}/finality`),
    ]);
    if (!claimResponse.ok) {
      setError("Claim not found.");
      return;
    }
    setClaim(await claimResponse.json());
    setEvents((await timelineResponse.json()).events);
    const final = await finalityResponse.json();
    setFinality(final.reason);
  }

  useEffect(() => {
    load().catch(() => setError("Claim could not be loaded."));
  }, [params.id]);

  async function act(path: string, body?: unknown) {
    setBusy(path);
    setError("");
    const response = await fetch(path, {
      method: "POST",
      headers: body ? { "content-type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      setError(payload.detail || "The request was not completed.");
      setBusy("");
      return;
    }
    await load();
    setBusy("");
  }

  return (
    <Shell active="/claims">
      <header className="page-head">
        <div>
          <p className="kicker">Claim detail</p>
          <h1 className="mono">{params.id}</h1>
        </div>
        <div className="actions">
          {claim?.status === "EVIDENCE_READY" ? (
            <button className="primary" type="button" onClick={() => act(`/v1/claims/${params.id}/review-request`)} disabled={busy !== ""}>
              {busy.endsWith("review-request") ? "Reviewing…" : "Run policy review"}
            </button>
          ) : null}
          {claim && claim.chain_status === "not_submitted" ? (
            <button className="ghost" type="button" onClick={() => act(`/v1/claims/${params.id}/submit`)} disabled={busy !== ""}>
              {busy.endsWith("submit") ? "Submitting…" : "Submit to StudioNet"}
            </button>
          ) : null}
        </div>
      </header>
      {error ? <p className="callout fail">{error}</p> : null}
      {claim ? (
        <div className="stack">
          <section className="split">
            <article className="panel">
              <h2>Scientific status</h2>
              <p className="mono">{claim.scientific_status}</p>
              <p className="muted">Confirmation flag: {claim.scientific_confirmation ? "true" : "false"}</p>
            </article>
            <article className="panel">
              <h2>Protocol evidence</h2>
              <p className="mono">{claim.protocol_result || "Not reviewed"}</p>
              <p className="muted">Policy {claim.policy_version}. Record status {claim.status}.</p>
            </article>
          </section>
          <section className="panel">
            <h2>Why</h2>
            <p>{claim.rationale || "The local policy has not been run. Chain submission is separate."}</p>
            <p className="hash mono">{claim.manifest_hash}</p>
            <p className="fine muted">{finality}</p>
            <p className="fine muted">Chain status {claim.chain_status}. {claim.chain_claim_id || "No chain claim id."}</p>
            {claim.chain_tx ? <p className="hash mono">{claim.chain_tx}</p> : null}
          </section>
          {claim.status === "FINALIZED" || claim.status === "NEEDS_REVIEW" ? (
            <section className="panel">
              <h2>Challenge</h2>
              <p className="fine muted">
                A challenge records a reason hash and moves the local record to CHALLENGED. If a chain claim exists, the same hash is sent to challenge_claim. This does not confirm or reject a planet.
              </p>
              <form
                className="actions"
                onSubmit={(event) => {
                  event.preventDefault();
                  act(`/v1/claims/${params.id}/challenge`, { reason });
                }}
              >
                <input aria-label="Challenge reason" value={reason} onChange={(event) => setReason(event.target.value)} style={{ background: "transparent", border: "1px solid var(--line)", padding: "8px 10px", minWidth: 280 }} />
                <button className="primary" type="submit" disabled={reason.trim().length < 20 || busy !== ""}>Record challenge</button>
              </form>
            </section>
          ) : null}
          {claim.chain_tx.includes("0x") ? (
            <section className="panel">
              <h2>Appeal the transaction</h2>
              <p className="fine muted">Appeal asks GenLayer validators to look at the transaction again. It is a network action, separate from the evidence challenge.</p>
              <button
                className="ghost"
                type="button"
                disabled={busy !== ""}
                onClick={() => {
                  const match = claim.chain_tx.match(/0x[a-fA-F0-9]{64}/);
                  if (!match) {
                    setError("No transaction hash is stored on this claim.");
                    return;
                  }
                  act(`/v1/claims/${params.id}/appeal`, { tx_hash: match[0] });
                }}
              >
                Appeal latest transaction
              </button>
            </section>
          ) : null}
          {claim.status !== "RETRACTED" && claim.status !== "SUPERSEDED" ? (
            <section className="panel">
              <button className="ghost" type="button" disabled={busy !== ""} onClick={() => act(`/v1/claims/${params.id}/retract`)}>
                Retract claim
              </button>
            </section>
          ) : null}
          {claim.manifest ? (
            <section className="panel">
              <h2>Manifest</h2>
              <p>Target {claim.target_id}. Archive {claim.manifest.archive.name}.</p>
              <div className="metrics">
                {claim.manifest.metrics.map((metric) => (
                  <div key={metric.name} className="metric">
                    <span>{metric.name}</span>
                    <strong>
                      {metric.value} {metric.unit}
                    </strong>
                  </div>
                ))}
              </div>
              <ul className="flags">
                {claim.manifest.limitations.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </section>
          ) : null}
          <section className="stack">
            {events.map((event) => (
              <article key={event.observed_at + event.status} className="event">
                <strong>{event.status}</strong>
                <div>{event.note}</div>
                <div className="muted">{event.observed_at}</div>
              </article>
            ))}
          </section>
        </div>
      ) : null}
    </Shell>
  );
}
