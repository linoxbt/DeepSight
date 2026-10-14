"use client";

import { useEffect, useState } from "react";
import { Plot } from "@/components/Plot";
import { Shell } from "@/components/Shell";

type Target = {
  id: string;
  name: string;
  summary: string;
  ra_deg: number;
  dec_deg: number;
  synthetic: boolean;
  observation_id: string;
  sector?: number | null;
};

type Analysis = {
  id: string;
  target: Target;
  metrics: {
    period_days: number;
    period_uncertainty_days: number;
    duration_days: number;
    depth: number;
    snr_proxy: number;
    odd_even_delta: number;
    secondary_depth: number;
    n_samples: number;
    n_in_transit: number;
  };
  quality_flags: { code: string; message: string }[];
  cross_match: { result: string; note: string };
  series_plot: { time_days: number[]; flux: number[] };
  folded: { phase: number[]; flux: number[] };
  periodogram: { period_days: number[]; power: number[] };
  limitations: string[];
};

export default function LabPage() {
  const [targets, setTargets] = useState<Target[]>([]);
  const [selected, setSelected] = useState("DS-SYN-001");
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [error, setError] = useState("");
  const [running, setRunning] = useState(false);

  useEffect(() => {
    const requested = new URLSearchParams(window.location.search).get("target");
    fetch("/v1/targets")
      .then((response) => response.json())
      .then((body) => {
        setTargets(body.targets);
        if (requested && body.targets.some((item: Target) => item.id === requested)) {
          setSelected(requested);
        }
      })
      .catch(() => setError("The analysis API is not reachable."));
  }, []);

  async function run() {
    setRunning(true);
    setError("");
    setAnalysis(null);
    try {
      const response = await fetch("/v1/analyses", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ target_id: selected }),
      });
      if (!response.ok) throw new Error(await response.text());
      setAnalysis(await response.json());
    } catch {
      setError("The transit search failed.");
    } finally {
      setRunning(false);
    }
  }

  const target = targets.find((item) => item.id === selected);

  return (
    <Shell active="/lab">
      <header className="page-head">
        <div>
          <p className="kicker">Discovery Lab</p>
          <h1>Transit search</h1>
        </div>
        <button className="primary" type="button" onClick={run} disabled={running || targets.length === 0}>
          {running ? "Running BLS…" : "Run BLS analysis"}
        </button>
      </header>
      {error ? <p className="callout fail">{error}</p> : null}
      <div className="grid-2">
        <div className="stack">
          <section className="panel">
            <h2>Target</h2>
            <div className="target-list">
              {targets.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  className="target"
                  aria-pressed={item.id === selected}
                  onClick={() => {
                    setSelected(item.id);
                    setAnalysis(null);
                  }}
                >
                  <strong className="mono">{item.id}</strong>
                  {item.name}
                  <span className="muted"> · {item.synthetic ? "synthetic calibration" : `MAST sector ${item.sector ?? ""}`}</span>
                </button>
              ))}
            </div>
            {target ? (
              <p className="fine muted">
                {target.summary} Coordinates {target.ra_deg}°, {target.dec_deg}° ICRS. Observation id {target.observation_id}.
              </p>
            ) : null}
          </section>
          {analysis ? (
            <>
              <section className="panel">
                <h2>Light curve</h2>
                <Plot
                  x={analysis.series_plot.time_days}
                  y={analysis.series_plot.flux}
                  xLabel="time (days)"
                  yLabel="flux"
                  description={
                    analysis.target.synthetic
                      ? `${analysis.target.id} relative flux over ${analysis.metrics.n_samples} samples. Synthetic calibration series.`
                      : `${analysis.target.id} relative PDCSAP flux over ${analysis.metrics.n_samples} unflagged cadences. TESS sector ${analysis.target.sector}. Not a confirmation.`
                  }
                />
              </section>
              <section className="panel">
                <h2>Phase-folded transit</h2>
                <Plot
                  x={analysis.folded.phase}
                  y={analysis.folded.flux}
                  xLabel="phase"
                  yLabel="median flux"
                  shade={{
                    from: 0.5 - analysis.metrics.duration_days / analysis.metrics.period_days / 2,
                    to: 0.5 + analysis.metrics.duration_days / analysis.metrics.period_days / 2,
                  }}
                  description={`Folded on ${analysis.metrics.period_days} days. Shaded region is the fitted transit duration.`}
                />
              </section>
              <section className="panel">
                <h2>Period search</h2>
                <Plot
                  x={analysis.periodogram.period_days}
                  y={analysis.periodogram.power}
                  xLabel="period (days)"
                  yLabel="box power"
                  description={`Box-least-squares power. Best period ${analysis.metrics.period_days} days.`}
                />
              </section>
            </>
          ) : (
            <section className="panel empty">
              <h2>No run yet</h2>
              <p className="muted">Choose a calibration target and run the search. Nothing is loaded from MAST.</p>
            </section>
          )}
        </div>
        <aside className="stack">
          <section className="panel">
            <h2>Metrics</h2>
            {analysis ? (
              <div className="metrics">
                <Metric label="Period" value={`${analysis.metrics.period_days} d`} />
                <Metric label="Uncertainty" value={`± ${analysis.metrics.period_uncertainty_days} d`} />
                <Metric label="Depth" value={analysis.metrics.depth.toFixed(5)} />
                <Metric label="Duration" value={`${analysis.metrics.duration_days} d`} />
                <Metric label="SNR proxy" value={String(analysis.metrics.snr_proxy)} />
                <Metric label="In transit" value={String(analysis.metrics.n_in_transit)} />
                <Metric label="Odd-even Δ" value={String(analysis.metrics.odd_even_delta)} />
                <Metric label="Secondary" value={analysis.metrics.secondary_depth.toFixed(5)} />
              </div>
            ) : (
              <p className="muted">Metrics appear after a run.</p>
            )}
          </section>
          {analysis ? (
            <section className="panel">
              <h2>Provenance and flags</h2>
              <p className="fine">{analysis.cross_match.note}</p>
              <ul className="flags">
                {analysis.quality_flags.map((flag) => (
                  <li key={flag.code}>{flag.message}</li>
                ))}
              </ul>
              <ul className="flags">
                {analysis.limitations.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
              <div className="actions">
                <a className="primary" href={`/evidence?analysis=${analysis.id}`}>Build evidence</a>
              </div>
            </section>
          ) : null}
        </aside>
      </div>
    </Shell>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}
