"use client";

import { useEffect, useState } from "react";
import { api, runJob } from "@/lib/api";
import { Shell } from "@/components/Shell";
import { Plot } from "@/components/Plot";

type Observation = {
  utc: string;
  target: string;
  project: string;
  file_type: string;
  size_bytes: number;
  center_freq_mhz: number | null;
  downloaded: boolean;
};
type Hit = { frequency_mhz: number; mad_score: number };
type Analysis = {
  id: string;
  note: string;
  scientific_status: string;
  frequency_range: string;
  time_range: string;
  off_target_comparison: string;
  metrics: { snr_proxy: number; n_hits: number };
  hits: Hit[];
  plot: { frequency_mhz: number[]; relative_power: number[] };
  limitations: string[];
};

const field = { background: "transparent", border: "1px solid var(--line)", padding: "8px 10px", minWidth: 180 };

export default function RadioPage() {
  const [target, setTarget] = useState("VOYAGER1");
  const [rows, setRows] = useState<Observation[]>([]);
  const [catalogNote, setCatalogNote] = useState("");
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [acknowledged, setAcknowledged] = useState(false);
  const [submissionMode, setSubmissionMode] = useState<"wallet" | "relay">("wallet");
  const [claimId, setClaimId] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");

  useEffect(() => {
    const saved = new URLSearchParams(window.location.search).get("analysis");
    if (saved) api(`/v1/radio/analyses/${encodeURIComponent(saved)}`).then(setAnalysis).catch(reason => setError(reason.message));
  }, []);

  async function search(event: React.FormEvent) {
    event.preventDefault();
    setBusy("search");
    setError("");
    try {
      const response = await fetch("/v1/radio/catalog", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ target }),
      });
      const body = await response.json().catch(() => null);
      if (!response.ok || !body) {
        setError(body?.detail || "The analysis API is not reachable.");
        return;
      }
      setRows(body.observations);
      setCatalogNote(body.note);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "The analysis API is not reachable.");
    } finally {
      setBusy("");
    }
  }

  async function analyze() {
    setBusy("analyze");
    setError("");
    setClaimId("");
    try {
      const body = await runJob("radio");
      setAnalysis(body);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "The analysis API is not reachable.");
    } finally {
      setBusy("");
    }
  }

  async function createClaim() {
    if (!analysis) return;
    setBusy("claim");
    setError("");
    try {
      const response = await fetch("/v1/radio/claims", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ analysis_id: analysis.id, acknowledged, submission_mode: submissionMode }),
      });
      const body = await response.json().catch(() => null);
      if (!body) {
        setError("The analysis API is not reachable.");
        return;
      }
      if (!response.ok) {
        const detail = typeof body.detail === "string" ? body.detail : "The claim was not stored";
        const existing = detail.match(/already claimed as (clm_[a-f0-9]+)/);
        if (existing) {
          setClaimId(existing[1]);
          setError("This screen is already stored. Open the existing claim.");
          return;
        }
        setError(detail);
        return;
      }
      setClaimId(body.id);
    } catch {
      setError("The analysis API is not reachable.");
    } finally {
      setBusy("");
    }
  }

  return (
    <Shell active="/radio">
      <header className="page-head">
        <div>
          <p className="kicker">Signal integrity</p>
          <h1>Radio</h1>
        </div>
      </header>
      {error ? <p className="callout fail">{error}</p> : null}
      <div className="stack">
        <section className="panel">
          <h2>Breakthrough Listen catalog</h2>
          <p className="fine muted">
            Search lists public observation rows. DeepSight does not download those files. A baseband product is often several gigabytes.
          </p>
          <form onSubmit={search} className="actions">
            <input aria-label="Breakthrough Listen target" value={target} onChange={(event) => setTarget(event.target.value)} style={field} />
            <button className="primary" type="submit" disabled={busy === "search"}>{busy === "search" ? "Searching…" : "Search catalog"}</button>
          </form>
          {catalogNote ? <p className="fine muted">{catalogNote}</p> : null}
          {rows.length > 0 ? (
            <div className="table-scroll">
              <table>
                <thead><tr><th>UTC</th><th>Target</th><th>Project</th><th>Type</th><th>MHz</th><th>Size</th><th>Fetched</th></tr></thead>
                <tbody>
                  {rows.map((row) => (
                    <tr key={`${row.utc}-${row.file_type}-${row.size_bytes}`}>
                      <td className="mono">{row.utc}</td>
                      <td>{row.target}</td>
                      <td>{row.project}</td>
                      <td>{row.file_type}</td>
                      <td className="mono">{row.center_freq_mhz}</td>
                      <td className="mono">{(row.size_bytes / 1e9).toFixed(2)} GB</td>
                      <td>{row.downloaded ? "yes" : "no"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
        </section>
        <section className="panel">
          <h2>Voyager 1 calibration screen</h2>
          <p className="fine muted">
            This downloads one public tutorial spectrum, about 50 MB, and flags narrow channels with a median-absolute-deviation screen.
            Voyager 1 is a human spacecraft. A spike is not a technosignature.
          </p>
          <button className="primary" type="button" onClick={analyze} disabled={busy === "analyze"}>
            {busy === "analyze" ? "Screening the calibration product…" : "Screen Voyager calibration product"}
          </button>
          {analysis ? (
            <div className="stack" style={{ marginTop: 16 }}>
              <p>{analysis.note}</p>
              <p className="mono">Status {analysis.scientific_status}. Off-target {analysis.off_target_comparison}. MAD score {analysis.metrics.snr_proxy}. Hits {analysis.metrics.n_hits}.</p>
              <p className="fine muted">{analysis.frequency_range}. {analysis.time_range}.</p>
              <Plot x={analysis.plot.frequency_mhz} y={analysis.plot.relative_power}
                xLabel="frequency (MHz)" yLabel="relative power" description="Screened Voyager calibration spectrum; a narrowband excess is not a technosignature." />
              <ul className="flags">
                {analysis.hits.slice(0, 5).map((hit) => (
                  <li key={`${hit.frequency_mhz}-${hit.mad_score}`}>{hit.frequency_mhz} MHz, MAD score {hit.mad_score}</li>
                ))}
                {analysis.limitations.map((item) => <li key={item}>{item}</li>)}
              </ul>
              <label className="check">
                <input type="checkbox" checked={acknowledged} onChange={(event) => setAcknowledged(event.target.checked)} />
                <span>I understand this screen checks a calibration product. It does not confirm a signal.</span>
              </label>
              <label className="fine">GenLayer submission
                <select value={submissionMode} onChange={event => setSubmissionMode(event.target.value as "wallet" | "relay")}>
                  <option value="wallet">My wallet sends transactions (default)</option>
                  <option value="relay">DeepSight relay sends transactions</option>
                </select>
              </label>
              <button className="primary" type="button" onClick={createClaim} disabled={!acknowledged || busy === "claim"}>
                {busy === "claim" ? "Storing…" : "Store radio evidence claim"}
              </button>
              {claimId ? <p><a href={`/claims/${claimId}`}>Open {claimId}</a></p> : null}
            </div>
          ) : null}
        </section>
      </div>
    </Shell>
  );
}
