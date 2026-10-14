"use client";

import { useEffect, useState } from "react";
import { Shell } from "@/components/Shell";

type Claim = {
  id: string;
  target_id: string;
  status: string;
  protocol_result: string;
  scientific_status: string;
  created_at: string;
};

export default function ClaimsPage() {
  const [claims, setClaims] = useState<Claim[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    fetch("/v1/claims")
      .then((response) => response.json())
      .then((body) => setClaims(body.claims))
      .catch(() => setError("Claims could not be loaded."));
  }, []);

  return (
    <Shell active="/claims">
      <header className="page-head">
        <div>
          <p className="kicker">Local registry</p>
          <h1>Claims</h1>
        </div>
      </header>
      {error ? <p className="callout fail">{error}</p> : null}
      <section className="panel">
        {claims.length === 0 ? (
          <p className="muted">No claims yet. A lab run can produce an evidence manifest.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Claim</th>
                <th>Target</th>
                <th>Scientific status</th>
                <th>Protocol evidence</th>
                <th>Record</th>
              </tr>
            </thead>
            <tbody>
              {claims.map((claim) => (
                <tr key={claim.id}>
                  <td><a href={`/claims/${claim.id}`}>{claim.id}</a></td>
                  <td className="mono">{claim.target_id}</td>
                  <td>{claim.scientific_status}</td>
                  <td>{claim.protocol_result || "not reviewed"}</td>
                  <td>{claim.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </Shell>
  );
}
