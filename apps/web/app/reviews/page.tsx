"use client";

import { useEffect, useState } from "react";
import { Shell } from "@/components/Shell";

type Claim = { id: string; target_id: string; scientific_status: string; protocol_result: string };

export default function ReviewsPage() {
  const [claims, setClaims] = useState<Claim[]>([]);
  const [note, setNote] = useState("");
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [decisions, setDecisions] = useState<Record<string, string>>({});
  const [disclosures, setDisclosures] = useState<Record<string, string>>({});
  const [error, setError] = useState("");
  const [saving, setSaving] = useState("");
  const [success, setSuccess] = useState("");

  async function load() {
    const response = await fetch("/v1/reviews");
    if (!response.ok) throw new Error("Review queue unavailable");
    const body = await response.json();
    if (!Array.isArray(body.claims)) throw new Error("Invalid review queue response");
    setClaims(body.claims);
    setNote(body.note);
  }

  useEffect(() => {
    load().catch(() => setError("The review queue could not be loaded."));
  }, []);

  async function save(id: string) {
    setError(""); setSuccess(""); setSaving(id);
    try {
      const response = await fetch(`/v1/claims/${id}/review-note`, {
        method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({ note: drafts[id] || "", decision: decisions[id] || "inconclusive", conflict_disclosure: disclosures[id] || "" }),
      });
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail || "The attestation was not stored");
      await load(); setSuccess(`Attestation recorded for ${id}.`);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "The attestation was not stored"); }
    finally { setSaving(""); }
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
      {success ? <p className="callout" role="status">{success}</p> : null}
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
                <select aria-label={`Decision for ${claim.id}`} value={decisions[claim.id] || "inconclusive"} onChange={event => setDecisions({ ...decisions, [claim.id]: event.target.value })}>
                  <option value="inconclusive">Inconclusive</option><option value="supports_evidence">Supports evidence</option><option value="requests_revision">Requests revision</option>
                </select>
                <input aria-label={`Conflict disclosure for ${claim.id}`} placeholder="Conflict disclosure (write none if applicable)" value={disclosures[claim.id] || ""} onChange={event => setDisclosures({ ...disclosures, [claim.id]: event.target.value })} required minLength={4} maxLength={500} />
                <button className="primary" type="submit" disabled={saving === claim.id || (drafts[claim.id] || "").trim().length < 8}>{saving === claim.id ? "Recording…" : "Record attestation"}</button>
              </form>
            </article>
          ))}
        </div>
      </section>
    </Shell>
  );
}
