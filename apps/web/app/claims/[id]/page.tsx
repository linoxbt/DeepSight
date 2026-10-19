"use client";

import { useParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { ChainAction } from "@/components/ChainAction";
import { WalletChainAction } from "@/components/WalletChainAction";
import { api } from "@/lib/api";
import { studioContractUrl, studioTransactionUrl } from "@/lib/genlayer";
import { Shell } from "@/components/Shell";

type Claim = {
  id: string;
  owner: string;
  submission_mode?: "wallet" | "relay";
  public: boolean;
  chain_protocol_result: string;
  chain_rationale: string;
  chain_execution: string;
  status: string;
  protocol_result: string;
  rationale: string;
  scientific_status: string;
  scientific_confirmation: boolean;
  review_resolution: string;
  manifest_hash: string;
  chain_status: string;
  chain_note: string;
  chain_claim_id: string;
  chain_contract_address: string;
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
type ChainConfig = { configured: boolean; contract_address: string | null; relay_enabled: boolean };

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
  const [chainConfig, setChainConfig] = useState<ChainConfig | null>(null);
  const refreshSeq = useRef(0);
  const owns = !!viewer && viewer === claim?.owner;
  const chainPending = operations.some(op => ["queued", "broadcasting", "submitted", "reconciling", "unknown"].includes(op.status));

  async function load() {
    const sequence = ++refreshSeq.current;
    const record = await api<Claim>(`/v1/claims/${params.id}`);
    if (sequence !== refreshSeq.current) return;
    setClaim(record);
    setError("");
    const [ops, viewerSession, timeline, finalityResult, reviews, network] = await Promise.allSettled([
      api<{ operations: typeof operations }>(`/v1/claims/${params.id}/operations`),
      api<{ address: string }>("/v1/auth/session"),
      api<{ events: Event[] }>(`/v1/claims/${params.id}/timeline`),
      api<{ reason: string }>(`/v1/claims/${params.id}/finality`),
      api<{ attestations: Attestation[] }>(`/v1/research/attestations?claim_id=${encodeURIComponent(params.id)}`),
      api<ChainConfig>("/v1/chain/config"),
    ]);
    if (sequence !== refreshSeq.current) return;
    if (ops.status === "fulfilled") setOperations(ops.value.operations);
    setViewer(viewerSession.status === "fulfilled" ? viewerSession.value.address : "");
    if (timeline.status === "fulfilled") setEvents(timeline.value.events);
    if (finalityResult.status === "fulfilled") setFinality(finalityResult.value.reason);
    if (reviews.status === "fulfilled") setAttestations(reviews.value.attestations);
    setChainConfig(network.status === "fulfilled" ? network.value : null);
    if ([ops, timeline, finalityResult, reviews, network].some(result => result.status === "rejected")) setError("Some claim details could not be loaded. Refresh to retry.");
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
          {owns && claim && !claim.public && !["RETRACTED", "SUPERSEDED"].includes(claim.status) ? (
            <button className="ghost" type="button" onClick={() => act(`/v1/claims/${params.id}/publish`, { acknowledged: true })} disabled={busy !== ""}>
              {busy.endsWith("publish") ? "Publishing…" : "Publish claim and evidence publicly"}
            </button>
          ) : null}
          {owns && claim && !claim.chain_claim_id && ["EVIDENCE_READY", "FINALIZED", "NEEDS_REVIEW"].includes(claim.status) ? (
            claim.submission_mode === "wallet" && chainConfig?.configured
              ? <WalletChainAction claimId={claim.id} action="submit" label="Send registration from my wallet" pending={chainPending} onQueued={load} />
              : claim.submission_mode !== "wallet" && chainConfig?.relay_enabled
                ? <ChainAction claimId={claim.id} action="submit" label="Sign relay submission" onQueued={load} /> : null
          ) : null}
          {owns && claim?.submission_mode === "wallet" && claim.chain_claim_id && claim.status === "EVIDENCE_READY" && chainConfig?.configured ? (
            <WalletChainAction claimId={claim.id} action="review" label="Send on-chain evidence review" pending={chainPending} onQueued={load} />
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
            <p className="fine muted">{claim.submission_mode === "wallet" ? "Your connected wallet sends and pays for each GenLayer transaction. Registration anchors the manifest hash; the separate review transaction runs contract policy. The manifest, evidence, and wallet address become public." : "Signing a relay submission publishes this claim, its evidence, and your wallet address. The DeepSight relay pays fees and is the on-chain claimant."}</p>
            {claim.submission_mode === "wallet" ? <p className="fine muted">Need test GEN? Open <a href="https://studio.genlayer.com" target="_blank" rel="noopener noreferrer">GenLayer Studio ↗</a> and use the faucet in its account selector.</p> : null}
            {(claim.chain_contract_address || chainConfig?.contract_address) ? <p className="fine"><a href={studioContractUrl(claim.chain_contract_address || chainConfig!.contract_address!)} target="_blank" rel="noopener noreferrer">View Proof of Discovery on GenLayer StudioNet ↗</a></p> : null}
            {chainConfig && !chainConfig.configured ? <p className="callout">StudioNet submissions are temporarily unavailable. Existing chain records remain visible.</p> : null}
            {operations.map(op => <div key={op.id} className="event"><strong>{op.action} · {op.stage} · {op.status}</strong><p className="hash mono">{op.tx_hash ? <a href={studioTransactionUrl(op.tx_hash)} target="_blank" rel="noopener noreferrer">{op.tx_hash} ↗</a> : "Awaiting transaction"}</p>{op.error && <p role="alert">{op.error}</p>}</div>)}
          </section>
          <section className="panel">
            <h2>Why</h2>
            <p>{claim.rationale || "The local policy has not been run. Chain submission is separate."}</p>
            <p className="hash mono">{claim.manifest_hash}</p>
            <p className="fine muted">{finality}</p>
            <p className="fine muted">Chain status {claim.chain_status}. {claim.chain_claim_id || "No chain claim id."}</p>
            <p className="fine muted">Human review: {claim.review_resolution?.replaceAll("_", " ") || "pending"}.</p>
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
              {claim.chain_claim_id && (claim.submission_mode === "wallet" ? chainConfig?.configured && <WalletChainAction claimId={claim.id} action="challenge" reason={reason} label="Send challenge from my wallet" pending={chainPending} onQueued={load} /> : chainConfig?.relay_enabled && <ChainAction claimId={claim.id} action="challenge" reason={reason} label="Sign challenge" onQueued={load} />)}
            </section>
          ) : null}
          {owns && !["RETRACTED", "SUPERSEDED"].includes(claim.status) && (
            <section className="panel actions">
              {claim.chain_claim_id ? (claim.submission_mode === "wallet" ? chainConfig?.configured && <WalletChainAction claimId={claim.id} action="retract" label="Send retraction from my wallet" pending={chainPending} onQueued={load} /> : chainConfig?.relay_enabled && <ChainAction claimId={claim.id} action="retract" label="Sign retraction" onQueued={load} />) : <button className="ghost" disabled={!!busy} onClick={() => act(`/v1/claims/${params.id}/retract`)}>Retract local claim</button>}
              {["FINALIZED", "NEEDS_REVIEW", "CHALLENGED"].includes(claim.status) && (claim.chain_claim_id ? (claim.submission_mode === "wallet" ? chainConfig?.configured && <WalletChainAction claimId={claim.id} action="supersede" label="Send replacement from my wallet" pending={chainPending} onQueued={load} /> : chainConfig?.relay_enabled && <ChainAction claimId={claim.id} action="supersede" label="Sign replacement" onQueued={load} />) : <button className="ghost" disabled={!!busy} onClick={() => act(`/v1/claims/${params.id}/supersede`)}>Create replacement</button>)}
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
