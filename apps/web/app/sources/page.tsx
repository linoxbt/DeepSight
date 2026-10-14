"use client";

import { useEffect, useState } from "react";
import { Shell } from "@/components/Shell";

type Source = { id: string; name: string; connected: boolean };

export default function SourcesPage() {
  const [sources, setSources] = useState<Source[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    fetch("/v1/sources")
      .then((response) => response.json())
      .then((body) => setSources(body.sources))
      .catch(() => setError("Source status is unavailable."));
  }, []);

  return (
    <Shell>
      <header className="page-head">
        <div>
          <p className="kicker">Adapters</p>
          <h1>Source status</h1>
        </div>
      </header>
      <p className="fine muted">A connected adapter means this build can call that service. It does not mean a target has been confirmed.</p>
      {error ? <p className="callout fail">{error}</p> : null}
      <section className="panel">
        <ul className="source-list">
          {sources.map((source) => (
            <li key={source.id}>
              <strong>{source.name}</strong>
              <span className={source.connected ? "pass" : "warn"}>{source.connected ? "Connected" : "Not connected"}</span>
            </li>
          ))}
        </ul>
      </section>
    </Shell>
  );
}
