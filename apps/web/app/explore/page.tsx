"use client";

import { useState } from "react";
import { runJob } from "@/lib/api";
import { Shell } from "@/components/Shell";

type Target = { id: string; name: string; ra_deg: number; dec_deg: number; summary: string };

export default function ExplorePage() {
  const [targets, setTargets] = useState<Target[]>([]);
  const [note, setNote] = useState("");
  const [query, setQuery] = useState("");
  const [error, setError] = useState("");
  const [tic, setTic] = useState("259377017");
  const [importing, setImporting] = useState(false);
  const [imported, setImported] = useState<{ id: string; summary: string; cached: boolean } | null>(null);

  async function search(event: React.FormEvent) {
    event.preventDefault();
    setError("");
    try {
      const response = await fetch("/v1/datasets/search", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ query }),
      });
      const body = await response.json().catch(() => null);
      if (!response.ok || !body) throw new Error(body?.detail || "The analysis API is not reachable.");
      setTargets(body.results);
      setNote(body.note);
    } catch (reason) {
      setTargets([]);
      setNote("");
      setError(reason instanceof Error ? reason.message : "The analysis API is not reachable.");
    }
  }

  async function importCurve(event: React.FormEvent) {
    event.preventDefault();
    setImporting(true);
    setError("");
    setImported(null);
    try {
      const body = await runJob("import", { tic });
      setImported({ id: body.target.id, summary: body.target.summary, cached: body.cached });
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "MAST import failed");
    } finally {
      setImporting(false);
    }
  }

  return (
    <Shell active="/explore">
      <header className="page-head">
        <div>
          <p className="kicker">Explorer</p>
          <h1>Explorer</h1>
        </div>
      </header>
      {error ? <p className="callout fail">{error}</p> : null}
      <div className="stack">
        <section className="panel">
          <h2>Import one TESS sector</h2>
          <p className="fine muted">
            MAST returns a single SPOC light curve, preferring 120-second cadence. Pixels are not re-reduced.
            A sector is not a confirmed planet.
          </p>
          <form onSubmit={importCurve} className="actions">
            <input
              aria-label="TIC id"
              value={tic}
              onChange={(event) => setTic(event.target.value)}
              placeholder="259377017"
              style={{ background: "transparent", border: "1px solid var(--line)", padding: "8px 10px", minWidth: 180 }}
            />
            <button className="primary" type="submit" disabled={importing}>
              {importing ? "Downloading from MAST…" : "Import light curve"}
            </button>
          </form>
          {imported ? (
            <p>
              {imported.cached ? "Already imported. " : "Imported. "}
              {imported.summary} <a href={`/lab?target=${imported.id}`}>Open in Discovery Lab</a>
            </p>
          ) : null}
        </section>
        <section className="panel">
          <h2>Search local targets</h2>
          <form onSubmit={search} className="actions">
            <input
              aria-label="Search targets"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="DS-SYN or coincidence"
              style={{ background: "transparent", border: "1px solid var(--line)", padding: "8px 10px", minWidth: 240 }}
            />
            <button className="primary" type="submit">Search</button>
          </form>
          <p className="fine muted">{note}</p>
          {targets.length > 0 ? (
            <div className="table-scroll"><table>
              <thead>
                <tr><th>Id</th><th>Name</th><th>RA</th><th>Dec</th></tr>
              </thead>
              <tbody>
                {targets.map((target) => (
                  <tr key={target.id}>
                    <td className="mono">{target.id}</td>
                    <td>{target.name}</td>
                    <td className="mono">{target.ra_deg}</td>
                    <td className="mono">{target.dec_deg}</td>
                  </tr>
                ))}
              </tbody>
            </table></div>
          ) : null}
        </section>
      </div>
    </Shell>
  );
}
