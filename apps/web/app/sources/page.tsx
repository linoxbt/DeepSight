"use client";

import { useEffect, useState } from "react";
import { Shell } from "@/components/Shell";

type Source = { id: string; name: string; connected: boolean | null };

export default function SourcesPage() {
  const [sources, setSources] = useState<Source[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    fetch("/v1/sources")
      .then((response) => { if (!response.ok) throw new Error("Source status unavailable"); return response.json(); })
      .then((body) => { if (!Array.isArray(body.sources)) throw new Error("Invalid source status"); setSources(body.sources); })
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
      <p className="fine muted">Archive access is checked when you run a query. An available adapter does not establish that its archive is reachable right now.</p>
      {error ? <p className="callout fail">{error}</p> : null}
      <section className="panel">
        <ul className="source-list">
          {sources.map((source) => (
            <li key={source.id}>
              <strong>{source.name}</strong>
              <span className={source.connected ? "pass" : "warn"}>{source.connected === true ? "Local source ready" : source.connected === false ? "Not configured" : "Reachability not checked"}</span>
            </li>
          ))}
        </ul>
      </section>
    </Shell>
  );
}
