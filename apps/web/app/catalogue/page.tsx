"use client";

import { useEffect, useState } from "react";
import { Shell } from "@/components/Shell";

type Row = { name: string; host_tic: string; period_days: number; ra_deg: number; dec_deg: number };

export default function CataloguePage() {
  const [rows, setRows] = useState<Row[]>([]);
  const [note, setNote] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    fetch("/v1/catalogue")
      .then((response) => response.json())
      .then((body) => {
        setRows(body.rows);
        setNote(body.note);
      })
      .catch(() => setError("The catalogue extract is unavailable."));
  }, []);

  return (
    <Shell>
      <header className="page-head">
        <div>
          <p className="kicker">Local fallback</p>
          <h1>Catalogue extract</h1>
        </div>
      </header>
      {error ? <p className="callout fail">{error}</p> : null}
      <section className="panel">
        <p className="fine muted">{note}</p>
        <div className="table-scroll">
          <table>
            <thead>
              <tr><th>Name</th><th>TIC</th><th>Period (d)</th><th>RA</th><th>Dec</th></tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.name}>
                  <td>{row.name}</td>
                  <td className="mono">{row.host_tic}</td>
                  <td className="mono">{row.period_days}</td>
                  <td className="mono">{row.ra_deg}</td>
                  <td className="mono">{row.dec_deg}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </Shell>
  );
}
