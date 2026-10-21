"use client";

import { useEffect, useMemo, useState } from "react";
import { Shell } from "@/components/Shell";
import { api } from "@/lib/api";

type Metric = { value: number; unit: string };
type RecordItem = {
  id: string;
  target_id: string;
  target_name: string;
  claim_type: string;
  archive_name: string;
  scientific_status: string;
  status: string;
  protocol_result: string;
  chain_status: string;
  chain_execution: string;
  chain_protocol_result: string;
  created_at: string;
  summary_metrics: Record<string, Metric>;
};

const words = (value: string) => value.replaceAll("_", " ").toLowerCase();
const chainDecided = (item: RecordItem) => item.chain_status === "FINALIZED" && item.chain_execution === "SUCCESS";
const formatDate = (value: string) => new Date(value).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });

export default function PublicDashboard() {
  const [records, setRecords] = useState<RecordItem[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [kind, setKind] = useState("all");

  async function load(next?: string) {
    setBusy(true);
    setError("");
    try {
      const result = await api<{ claims: RecordItem[]; next_cursor: string | null }>(`/v1/claims?limit=100${next ? `&cursor=${encodeURIComponent(next)}` : ""}`);
      if (!Array.isArray(result.claims)) throw new Error("Invalid public records response");
      setRecords(current => next ? [...current, ...result.claims] : result.claims);
      setCursor(result.next_cursor || null);
    } catch {
      setError("The public records service is unavailable. Please retry shortly.");
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => { void load(); }, []);
  const visible = useMemo(() => records.filter(item =>
    (kind === "all" || (kind === "transit" ? !item.claim_type.startsWith("radio_") : item.claim_type.startsWith("radio_"))) &&
    `${item.target_id} ${item.target_name} ${item.id}`.toLowerCase().includes(query.toLowerCase())
  ), [records, kind, query]);
  const finalized = records.filter(chainDecided).length;
  const archive = records.filter(item => item.archive_name && !item.archive_name.toLowerCase().includes("synthetic")).length;

  return <Shell>
    <header className="page-head public-board-head">
      <div><p className="kicker">Public research dashboard</p><h1>Every result, in context.</h1><p className="muted">Browse evidence packages created in DeepSight. A record here is a research claim, never a confirmed discovery.</p></div>
      <a className="primary" href="/lab">Run an analysis ↗</a>
    </header>
    <div className="public-board-stats" aria-label="Loaded record summary">
      <div><span>Research records loaded</span><strong>{records.length}</strong></div>
      <div><span>Archive-backed records</span><strong>{archive}</strong></div>
      <div><span>Finalized chain decisions</span><strong>{finalized}</strong></div>
    </div>
    <section className="public-board-guide" aria-label="How to read these results">
      <div><b>Archive</b><span>Where the underlying observation came from.</span></div>
      <div><b>Local review</b><span>DeepSight&apos;s evidence checklist, separate from science.</span></div>
      <div><b>StudioNet</b><span>Only finalized successful chain execution counts as a chain decision.</span></div>
    </section>
    <div className="registry-controls public-board-controls">
      <div className="registry-filters" role="group" aria-label="Filter research records">
        {[["all", "All records"], ["transit", "Transit light curves"], ["radio", "Radio screens"]].map(([value, label]) =>
          <button key={value} aria-pressed={kind === value} onClick={() => setKind(value)}>{label}</button>)}
      </div>
      <input aria-label="Search public records" placeholder="Search target or record…" value={query} onChange={event => setQuery(event.target.value)} />
    </div>
    {error && <div className="callout fail" role="alert">{error} <button type="button" className="ghost" onClick={() => void load()}>Retry</button></div>}
    {busy && !records.length && <p role="status" className="empty muted">Loading public records…</p>}
    {!busy && !error && !records.length && <div className="panel empty"><h2>No research records yet</h2><p>Run a real archive analysis, review the evidence, and create a claim to make it visible here.</p><a href="/lab" className="text-link">Open Discovery Lab →</a></div>}
    {records.length > 0 && <>
      <p className="micro" aria-live="polite">Showing {visible.length} of {records.length} loaded records{cursor ? "; more available" : ""}</p>
      {visible.length === 0 ? <p className="panel empty">No records match this filter.</p> : <div className="public-board-list">{visible.map(item => {
        const period = item.summary_metrics?.period_days;
        const snr = item.summary_metrics?.snr_proxy;
        return <article className="public-board-record" key={item.id}>
          <div className="public-board-record-top"><span>{item.claim_type.startsWith("radio_") ? "RADIO SCREEN" : "TESS LIGHT CURVE"}</span><time dateTime={item.created_at}>{formatDate(item.created_at)}</time></div>
          <div className="public-board-record-body"><div><h2><a href={`/claims/${item.id}`}>{item.target_name || item.target_id}</a></h2><p className="mono">{item.target_id} · {item.id}</p></div><div className="public-board-record-metric">{period ? <><strong>{period.value} {period.unit}</strong><span>Recovered period</span></> : snr ? <><strong>{snr.value}</strong><span>Signal score</span></> : <><strong>—</strong><span>See evidence</span></>}</div></div>
          <dl className="public-board-record-status"><div><dt>Source</dt><dd>{item.archive_name || "Recorded evidence"}</dd></div><div><dt>Local review</dt><dd>{item.protocol_result ? words(item.protocol_result) : words(item.status)}</dd></div><div><dt>StudioNet</dt><dd>{chainDecided(item) ? words(item.chain_protocol_result || "finalized") : "No finalized decision"}</dd></div></dl>
          <div className="public-board-record-bottom"><span>Scientific status: {words(item.scientific_status)}</span><a href={`/claims/${item.id}`}>View evidence and timeline →</a></div>
        </article>;
      })}</div>}
      {cursor && <button className="ghost public-board-more" disabled={busy} onClick={() => void load(cursor)}>{busy ? "Loading…" : "Load more records"}</button>}
    </>}
  </Shell>;
}
