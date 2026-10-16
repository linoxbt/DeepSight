"use client";

import { useEffect, useState } from "react";
import { Shell } from "@/components/Shell";
import { api } from "@/lib/api";

type Item = { id: string; target_id: string; headline: string; scientific_status: string };

export default function DiscoveriesPage() {
  const [items, setItems] = useState<Item[]>([]);
  const [note, setNote] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    api("/v1/discoveries")
      .then((body) => {
        if (!Array.isArray(body.discoveries)) throw new Error("Invalid findings response");
        setItems(body.discoveries);
        setNote(body.note || "");
      })
      .catch(() => setError("Findings could not be loaded."));
  }, []);

  return (
    <Shell active="/discoveries">
      <header className="page-head">
        <div>
          <p className="kicker">Public findings</p>
          <h1>Discoveries</h1>
        </div>
      </header>
      {error ? <p className="callout fail">{error}</p> : null}
      <section className="panel">
        <p>{note}</p>
        {items.length === 0 ? (
          <p className="muted">
            Nothing is listed. Calibration claims stay in human review because their light curves are synthetic.
            An empty list is the correct state, not a missing feed of planets.
          </p>
        ) : (
          <ul className="flags">
            {items.map((item) => (
              <li key={item.id}>
                <a href={`/claims/${item.id}`}>{item.target_id}</a> — {item.headline}
              </li>
            ))}
          </ul>
        )}
      </section>
    </Shell>
  );
}
