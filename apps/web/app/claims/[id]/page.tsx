"use client";

import { useParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { ChainAction } from "@/components/ChainAction";
import { api } from "@/lib/api";
import { Shell } from "@/components/Shell";

type Claim = {
  id: string;
  owner: string;
  chain_protocol_result: string;
  chain_rationale: string;
  chain_execution: string;
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
type Attestation = { id: string; reviewer: string; decision: string; note: string; conflict_disclosure: string; manifest_hash: string; created_at: string };

export default function ClaimDetailPage() {
  const params = useParams<{ id: string }>();
  const [claim, setClaim] = useState<Claim | null>(null);
  const [events, setEvents] = useState<Event[]>([]);
  const [finality, setFinality] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");
  const [reason, setReason] = useState("");
  const [viewer, setViewer] = useState("");
  const [operations, setOperations] = useState<{ id: string; action: string; stage: string; status: string; error: string; tx_hash: string }[]>([]);
  const [attestations, setAttestations] = useState<Attestation[]>([]);
  const refreshSeq = useRef(0);
  const owns = !!viewer && viewer === claim?.owner;

  async function load() {
    const sequence = ++refreshSeq.current;
    const record = await api<Claim>(`/v1/claims/${params.id}`);
    if (sequence !== refreshSeq.current) return;
    setClaim(record);
    setError("");
    const [ops, viewerSession, timeline, finalityResult, reviews] = await Promise.allSettled([
      api<{ operations: typeof operations }>(`/v1/claims/${params.id}/operations`),
      api<{ address: string }>("/v1/auth/session"),
      api<{ events: Event[] }>(`/v1/claims/${params.id}/timeline`),
      api<{ reason: string }>(`/v1/claims/${params.id}/finality`),
      api<{ attestations: Attestation[] }>(`/v1/research/attestations?claim_id=${encodeURIComponent(params.id)}`),
    ]);
    if (sequence !== refreshSeq.current) return;
    if (ops.status === "fulfilled") setOperations(ops.value.operations);
    setViewer(viewerSession.status === "fulfilled" ? viewerSession.value.address : "");
    if (timeline.status === "fulfilled") setEvents(timeline.value.events);
    if (finalityResult.status === "fulfilled") setFinality(finalityResult.value.reason);
    if (reviews.status === "fulfilled") setAttestations(reviews.value.attestations);
    if ([ops, timeline, finalityResult, reviews].some(result => result.status === "rejected")) setError("Some claim details could not be loaded. Refresh to retry.");
  }

  useEffect(() => {
    const refresh = () => { load().catch(() => setError("Claim could not be loaded.")); };
    refresh();
    const timer = setInterval(refresh, 5000);
    window.addEventListener("deepsight-auth", refresh);
    return () => { ++refreshSeq.current; clearInterval(timer); window.removeEventListener("deepsight-auth", refresh); };
  }, [params.id]);

  async function act(path: string, body?: unknown) {
    setBusy(path);
    setError("");
    try {
      await api(path, { method: "POST", headers: { "content-type": "application/json" }, body: body ? JSON.stringify(body) : undefined });
      await load();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Request failed"); }
    finally { setBusy(""); }
  }

  return (
    <Shell active="/claims">
      <header className="page-head">
        <div>
          <p className="kicker">Claim detail</p>
          <h1 className="mono">{params.id}</h1>
        </div>
        <div className="actions">
          {owns && !claim?.chain_claim_id && claim?.status === "EVIDENCE_READY" ? (
            <button className="primary" type="button" onClick={() => act(`/v1/claims/${params.id}/review-request`)} disabled={busy !== ""}>
              {busy.endsWith("review-request") ? "Reviewing…" : "Run policy review"}
            </button>
          ) : null}
          {owns && claim && !claim.chain_claim_id && ["EVIDENCE_READY", "FINALIZED", "NEEDS_REVIEW"].includes(claim.status) ? (
            <ChainAction claimId={claim.id} action="submit" label="Sign and submit to StudioNet" onQueued={load} />
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
              <h2>Local policy preview</h2>
              <p className="mono">{claim.protocol_result || "Not reviewed"}</p>
              <p className="muted">Policy {claim.policy_version}. Record status {claim.status}.</p>
            </article>
          </section>
          <section className="panel">
            <h2>Chain evidence decision</h2>
            <p className="mono">{claim.chain_protocol_result || "No chain decision"}</p>
            <p>{claim.chain_rationale}</p>
            <p>Consensus: {claim.chain_status} · Execution: {claim.chain_execution || "Not submitted"}</p>
            <p className="fine muted">Chain actions require your signature. The DeepSight relay pays fees and is the on-chain claimant.</p>
            {operations.map(op => <div key={op.id} className="event"><strong>{op.action} · {op.stage} · {op.status}</strong><p className="hash mono">{op.tx_hash}</p>{op.error && <p role="alert">{op.error}</p>}</div>)}
          </section>
          <section className="panel">
            <h2>Why</h2>
            <p>{claim.rationale || "The local policy has not been run. Chain submission is separate."}</p>
            <p className="hash mono">{claim.manifest_hash}</p>
            <p className="fine muted">{finality}</p>
            <p className="fine muted">Chain status {claim.chain_status}. {claim.chain_claim_id || "No chain claim id."}</p>
            {claim.chain_tx ? <p className="hash mono">{claim.chain_tx}</p> : null}
          </section>
          {viewer && (claim.status === "FINALIZED" || claim.status === "NEEDS_REVIEW") ? (
            <section className="panel">
              <h2>Challenge</h2>
              <p className="fine muted">
                A challenge records a reason hash and moves the local record to CHALLENGED. If a chain claim exists, the same hash is sent to challenge_claim. This does not confirm or reject a planet.
              </p>
              <form
                className="actions"
                onSubmit={(event) => {
                  event.preventDefault();
                  if (!claim.chain_claim_id) act(`/v1/claims/${params.id}/challenge`, { reason });
                }}
              >
                <input aria-label="Challenge reason" value={reason} onChange={(event) => setReason(event.target.value)} style={{ background: "transparent", border: "1px solid var(--line)", padding: "8px 10px", minWidth: 280 }} />
                {!claim.chain_claim_id && <button className="primary" type="submit" disabled={reason.trim().length < 20 || busy !== ""}>Record challenge</button>}
              </form>
              {claim.chain_claim_id && <ChainAction claimId={claim.id} action="challenge" reason={reason} label="Sign challenge" onQueued={load} />}
            </section>
          ) : null}
          {owns && claim.chain_claim_id && claim.chain_tx.includes("0x") && (
            <section className="panel"><h2>Appeal</h2>
              <p className="fine muted">Choose the transaction to appeal. Availability and fees depend on the network.</p>
              {Object.entries(JSON.parse(claim.chain_tx || "{}") as Record<string, string>).map(([kind, hash]) => <ChainAction key={kind} claimId={claim.id} action="appeal" txHash={hash} label={`Sign appeal: ${kind}`} onQueued={load} />)}
            </section>
          )}
          {owns && !["RETRACTED", "SUPERSEDED"].includes(claim.status) && (
            <section className="panel actions">
              {claim.chain_claim_id ? <ChainAction claimId={claim.id} action="retract" label="Sign retraction" onQueued={load} /> : <button className="ghost" disabled={!!busy} onClick={() => act(`/v1/claims/${params.id}/retract`)}>Retract local claim</button>}
              {["FINALIZED", "NEEDS_REVIEW", "CHALLENGED"].includes(claim.status) && (claim.chain_claim_id ? <ChainAction claimId={claim.id} action="supersede" label="Sign replacement" onQueued={load} /> : <button className="ghost" disabled={!!busy} onClick={() => act(`/v1/claims/${params.id}/supersede`)}>Create replacement</button>)}
            </section>
          )}
          {claim.manifest ? (
            <section className="panel">
              <h2>Manifest</h2>
              <div className="actions"><a href={`/v1/claims/${claim.id}/manifest`}>Download canonical manifest</a><a href={`/v1/claims/${claim.id}/bundle`}>Download reproducible evidence bundle</a></div>
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
            {attestations.length > 0 ? <section className="panel"><h2>Independent attestations</h2>{attestations.map(item => <article key={item.id} className="event"><strong>{item.decision.replaceAll("_", " ")}</strong><p>{item.note}</p><p className="fine muted">Reviewer {item.reviewer} · Conflict disclosure: {item.conflict_disclosure} · {item.created_at}</p><p className="hash mono">Manifest {item.manifest_hash}</p></article>)}</section> : null}
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
