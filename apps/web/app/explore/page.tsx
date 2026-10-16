"use client";

import { useState } from "react";
import { runJob } from "@/lib/api";
import { Shell } from "@/components/Shell";
import { ImageDesk } from "@/components/ImageDesk";

type Target = { id: string; name: string; ra_deg: number; dec_deg: number; summary: string };

export default function ExplorePage() {
  const [targets, setTargets] = useState<Target[]>([]);
  const [note, setNote] = useState("");
  const [query, setQuery] = useState("");
  const [error, setError] = useState("");
  const [tic, setTic] = useState("");
  const [importing, setImporting] = useState(false);
  const [progress, setProgress] = useState("");
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

  async function importCurve(event?: React.FormEvent, example?: string) {
    event?.preventDefault();
    setImporting(true);
    setProgress("Starting import");
    setError("");
    setImported(null);
    try {
      const body = await runJob("import", { tic: example || tic.trim() }, setProgress);
      setImported({ id: body.target.id, summary: body.target.summary, cached: body.cached });
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "MAST import failed");
    } finally {
      setImporting(false);
      setProgress("");
    }
  }

  return (
    <Shell active="/explore">
      <header className="page-head">
        <div>
          <p className="kicker">Start here</p>
          <h1>Explore the sky</h1>
          <p className="muted">Choose a starting point. You do not need a catalogue number to begin.</p>
        </div>
      </header>
      <div className="stack">
        <div className="start-grid">
          <section className="panel start-card"><span className="step-number">01 / LOOK</span><h2>Start with an image</h2><p>Upload your own sky photo. Mark what interests you and save your observations.</p><a className="primary" href="#image-desk">Add an image ↓</a></section>
          <section className="panel start-card"><span className="step-number">02 / ANALYZE</span><h2>Study a star&apos;s light</h2><p>Use a ready-to-load TESS example. DeepSight retrieves its light curve from NASA&apos;s MAST archive.</p><button className="primary" type="button" disabled={importing} onClick={() => importCurve(undefined, "259377017")}>{importing ? "Loading example…" : "Load TESS example"}</button></section>
          <section className="panel start-card"><span className="step-number">03 / EXPLORE</span><h2>Browse the archives</h2><p>Find published exoplanets, nearby stars, and other research data.</p><a className="primary" href="/tap">Browse exoplanets ↗</a></section>
        </div>
        {error ? <p role="alert" className="callout fail">{error === "The analysis API is not reachable." || error.includes("Request failed (500)") ? "The research service is temporarily unavailable. You can still inspect an image below." : error}</p> : null}
        {importing && progress ? <p role="status" className="callout">{progress}…</p> : null}
        <ImageDesk />
        <section className="panel manual-import">
          <h2>Have a star in mind?</h2>
          <p className="muted">A TIC ID identifies a star in the TESS Input Catalog. Find one in the <a href="https://mast.stsci.edu/portal/Mashup/Clients/Mast/Portal.html">MAST search portal ↗</a>, then paste its number here. You can skip this step and use the example above.</p>
          <form onSubmit={(event) => importCurve(event)} className="actions">
            <label htmlFor="tic-id">TIC ID</label>
            <input id="tic-id" inputMode="numeric" pattern="[0-9]+" required value={tic} onChange={(event) => setTic(event.target.value)} placeholder="Enter a TIC number" />
            <button className="primary" type="submit" disabled={importing}>{importing ? "Loading…" : "Load light curve"}</button>
          </form>
          {imported ? (
            <p>
              {imported.cached ? "Already imported. " : "Imported. "}
              {imported.summary} <a href={`/lab?target=${imported.id}`}>Analyze this light curve →</a>
            </p>
          ) : null}
        </section>
        <section className="panel">
          <h2>Search targets already in the workspace</h2>
          <form onSubmit={search} className="actions">
            <input
              aria-label="Search targets"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Try a name or keyword"
            />
            <button className="primary" type="submit">Search</button>
          </form>
          <p className="fine muted">{note}</p>
          {targets.length > 0 ? (
            <div className="table-scroll"><table>
              <thead>
                <tr><th>Target</th><th>Description</th><th></th></tr>
              </thead>
              <tbody>
                {targets.map((target) => (
                  <tr key={target.id}>
                    <td>{target.name}</td>
                    <td>{target.summary}</td>
                    <td><a href={`/lab?target=${target.id}`}>Analyze →</a></td>
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
