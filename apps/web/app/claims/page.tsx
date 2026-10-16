"use client";

import { useEffect, useState } from "react";
import { Shell } from "@/components/Shell";

type Claim = { id: string; target_id: string; status: string; protocol_result: string; chain_protocol_result: string; chain_status: string; chain_execution: string; scientific_status: string; created_at: string };
const readable = (value: string) => value.toLowerCase().replaceAll("_", " ");
export default function ClaimsPage() {
  const [claims, setClaims] = useState<Claim[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("all");
  useEffect(() => {
    fetch("/v1/claims").then(async response => {
      if (!response.ok) throw new Error();
      const body = await response.json();
      if (!Array.isArray(body.claims)) throw new Error();
      setClaims(body.claims);
      setNextCursor(body.next_cursor || null);
    }).catch(() => setError("Claims could not be loaded. Please try again later.")).finally(() => setLoading(false));
  }, []);
  async function loadMore() {
    if (!nextCursor || loadingMore) return;
    setLoadingMore(true); setError("");
    try {
      const response = await fetch(`/v1/claims?cursor=${encodeURIComponent(nextCursor)}`);
      if (!response.ok) throw new Error();
      const body = await response.json();
      if (!Array.isArray(body.claims)) throw new Error();
      setClaims(current => [...current, ...body.claims]);
      setNextCursor(body.next_cursor || null);
    } catch { setError("More claims could not be loaded. Try again."); }
    finally { setLoadingMore(false); }
  }
  const visible = claims.filter(claim => `${claim.id} ${claim.target_id}`.toLowerCase().includes(query.toLowerCase()) && (filter === "all" || (filter === "review" ? claim.status === "NEEDS_REVIEW" : filter === "local" ? claim.protocol_result === "EVIDENCE_SUFFICIENT" : claim.chain_protocol_result === "EVIDENCE_SUFFICIENT" && claim.chain_status === "FINALIZED" && claim.chain_execution === "SUCCESS")));
  return <Shell active="/claims">
    <header className="page-head"><div><p className="kicker">The evidence registry</p><h1>Claims, on the record.</h1></div><a className="primary" href="/lab">Start an investigation ↗</a></header>
    <p className="muted registry-intro">A record of the evidence, its review, and the questions that remain. Protocol outcomes do not establish scientific confirmation.</p>
    <div className="registry-controls"><div className="registry-filters" role="group" aria-label="Filter claims">{[["all","All claims"],["review","Needs review"],["local","Local preview sufficient"],["chain","Finalized chain sufficient"]].map(([value,label])=><button key={value} onClick={()=>setFilter(value)} aria-pressed={filter===value}>{label}</button>)}</div><input aria-label="Search claims" placeholder="Find a target or claim…" value={query} onChange={event=>setQuery(event.target.value)} /></div>
    {error ? <p className="callout fail" role="alert">{error}</p> : null}
    {loading ? <p className="empty muted" role="status">Loading the registry…</p> : null}
    {!loading && (claims.length > 0 || !error) ? <>
      <p className="micro" aria-live="polite">{visible.length} {visible.length === 1 ? "record" : "records"} loaded</p>
      {visible.length === 0 ? <div className="panel empty">
        <p className="kicker">The next question starts here</p>
        <h2>{claims.length ? "No matching records." : "An open page for your evidence."}</h2>
        <p className="muted">{claims.length ? "Try a different target or filter, or load more records." : "Run an analysis in the Discovery Lab to prepare an evidence manifest."}</p>
        {!claims.length && <a className="text-link" href="/lab">Open the Discovery Lab →</a>}
      </div> : <div className="claim-board">{visible.map(claim => <article key={claim.id} className="claim-card">
        <div className="specimen-meta"><span className="hash">{claim.id}</span><span>{readable(claim.status)}</span></div>
        <h2><a href={`/claims/${claim.id}`}>{claim.target_id}</a></h2>
        <dl><div><dt>Scientific status</dt><dd>{readable(claim.scientific_status || "unconfirmed")}</dd></div>
          <div><dt>Local policy preview</dt><dd>{readable(claim.protocol_result || "not reviewed")}</dd></div>
          <div><dt>Chain evidence decision</dt><dd>{claim.chain_status === "FINALIZED" && claim.chain_execution === "SUCCESS" ? readable(claim.chain_protocol_result || "no result") : "not finalized"}</dd></div></dl>
        <a className="text-link" href={`/claims/${claim.id}`}>Inspect the evidence →</a>
      </article>)}</div>}
      {nextCursor ? <button type="button" className="ghost" disabled={loadingMore} onClick={loadMore}>{loadingMore ? "Loading…" : "Load more claims"}</button> : null}
    </> : null}
  </Shell>;
}
