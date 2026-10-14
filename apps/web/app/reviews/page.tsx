"use client";

import { useEffect, useState } from "react";
import { Shell } from "@/components/Shell";

type Claim = { id: string; target_id: string; scientific_status: string; protocol_result: string };

export default function ReviewsPage() {
  const [claims, setClaims] = useState<Claim[]>([]);
  const [note, setNote] = useState("");
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [error, setError] = useState("");

  async function load() {
    const response = await fetch("/v1/reviews");
    const body = await response.json();
    setClaims(body.claims);
    setNote(body.note);
  }

  useEffect(() => {
    load().catch(() => setError("The review queue could not be loaded."));
  }, []);

  async function save(id: string) {
    setError("");
    const response = await fetch(`/v1/claims/${id}/review-note`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ note: drafts[id] || "" }),
    });
    const body = await response.json();
    if (!response.ok) {
      setError(body.detail || "The note was not stored");
      return;
    }
    await load();
  }

  return (
    <Shell active="/reviews">
      <header className="page-head">
        <div>
          <p className="kicker">Human review</p>
          <h1>Review queue</h1>
        </div>
      </header>
      {error ? <p className="callout fail">{error}</p> : null}
      <section className="panel">
        <p>{note}</p>
        {claims.length === 0 ? <p className="muted">Nothing is waiting for a person.</p> : null}
        <div className="stack">
          {claims.map((claim) => (
            <article key={claim.id} className="event">
              <strong><a href={`/claims/${claim.id}`}>{claim.target_id}</a></strong>
              <div className="muted">{claim.id} · {claim.scientific_status} · {claim.protocol_result}</div>
              <form
                className="actions"
                onSubmit={(event) => {
                  event.preventDefault();
                  save(claim.id).catch(() => setError("The note was not stored"));
                }}
              >
                <input
                  aria-label={`Review note for ${claim.id}`}
                  value={drafts[claim.id] || ""}
                  onChange={(event) => setDrafts({ ...drafts, [claim.id]: event.target.value })}
                  style={{ background: "transparent", border: "1px solid var(--line)", padding: "8px 10px", minWidth: 280 }}
                />
                <button className="primary" type="submit">Record note</button>
              </form>
            </article>
          ))}
        </div>
      </section>
    </Shell>
  );
}
