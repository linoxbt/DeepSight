"use client";

import { useState } from "react";

type Planet = { name: string; hostname: string; period_days: number; tic_id: string };
type GaiaSource = { source_id: string; ra_deg: number | null; dec_deg: number | null; parallax_mas: number | null; phot_g_mean_mag: number | null; separation_arcsec: number | null };
type Horizons = { found: boolean; command: string; note: string; ephemeris: string[]; excerpt: string };

const field = { background: "transparent", border: "1px solid var(--line)", padding: "8px 10px", minWidth: 160 };

export function Archives({ view }: { view: "tap" | "gaia" | "horizons" }) {
  const [tic, setTic] = useState("259377017");
  const [planets, setPlanets] = useState<Planet[] | null>(null);
  const [tapNote, setTapNote] = useState("");
  const [ra, setRa] = useState("68.4155");
  const [dec, setDec] = useState("-51.9562");
  const [sources, setSources] = useState<GaiaSource[] | null>(null);
  const [gaiaNote, setGaiaNote] = useState("");
  const [command, setCommand] = useState("499");
  const [horizons, setHorizons] = useState<Horizons | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");

  async function post(path: string, body: unknown, label: string) {
    setBusy(label);
    setError("");
    try {
      const response = await fetch(path, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(body),
      });
      const payload = await response.json().catch(() => null);
      if (!response.ok || !payload) throw new Error(payload?.detail || "The analysis API is not reachable.");
      return payload;
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "The archive did not answer");
      return null;
    } finally {
      setBusy("");
    }
  }

  return (
    <section className="panel">
      {error ? <p className="callout fail">{error}</p> : null}
      {view === "tap" ? (
      <>
      <form
        className="actions"
        onSubmit={async (event) => {
          event.preventDefault();
          const payload = await post("/v1/archives/tap", { tic }, "tap");
          if (!payload) return;
          setPlanets(payload.rows);
          setTapNote(payload.note);
        }}
      >
        <input aria-label="TAP TIC id" value={tic} onChange={(event) => setTic(event.target.value)} style={field} />
        <button className="primary" type="submit" disabled={busy === "tap"}>{busy === "tap" ? "Querying TAP…" : "Query NASA TAP"}</button>
      </form>
      {tapNote ? <p className="fine muted">{tapNote}</p> : null}
      {planets ? (
        <div className="table-scroll">
          <table>
            <thead><tr><th>Name</th><th>Host</th><th>Period (d)</th><th>TIC</th></tr></thead>
            <tbody>
              {planets.map((row) => (
                <tr key={row.name}>
                  <td>{row.name}</td>
                  <td>{row.hostname}</td>
                  <td className="mono">{row.period_days}</td>
                  <td className="mono">{row.tic_id}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
      </>
      ) : null}
      {view === "gaia" ? (
      <>
      <form
        className="actions"
        onSubmit={async (event) => {
          event.preventDefault();
          const payload = await post("/v1/archives/gaia", { ra_deg: Number(ra), dec_deg: Number(dec), radius_arcsec: 36 }, "gaia");
          if (!payload) return;
          setSources(payload.sources);
          setGaiaNote(payload.note);
        }}
      >
        <input aria-label="Gaia right ascension" value={ra} onChange={(event) => setRa(event.target.value)} style={field} />
        <input aria-label="Gaia declination" value={dec} onChange={(event) => setDec(event.target.value)} style={field} />
        <button className="primary" type="submit" disabled={busy === "gaia"}>{busy === "gaia" ? "Querying Gaia…" : "Query Gaia"}</button>
      </form>
      {gaiaNote ? <p className="fine muted">{gaiaNote}</p> : null}
      {sources ? (
        <div className="table-scroll">
          <table>
            <thead><tr><th>Source</th><th>Separation (arcsec)</th><th>G mag</th><th>Parallax (mas)</th></tr></thead>
            <tbody>
              {sources.map((source) => (
                <tr key={source.source_id}>
                  <td className="mono">{source.source_id}</td>
                  <td className="mono">{source.separation_arcsec}</td>
                  <td className="mono">{source.phot_g_mean_mag}</td>
                  <td className="mono">{source.parallax_mas ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
      </>
      ) : null}
      {view === "horizons" ? (
      <>
      <form
        className="actions"
        onSubmit={async (event) => {
          event.preventDefault();
          const payload = await post("/v1/archives/horizons", { command }, "horizons");
          if (!payload) return;
          setHorizons(payload);
        }}
      >
        <input aria-label="Horizons command" value={command} onChange={(event) => setCommand(event.target.value)} style={field} />
        <button className="primary" type="submit" disabled={busy === "horizons"}>{busy === "horizons" ? "Querying Horizons…" : "Query Horizons"}</button>
      </form>
      <p className="fine muted">499 is Mars. -31 is Voyager 1. A star name such as TOI-270 often has no Horizons body.</p>
      {horizons ? (
        <div>
          <p>{horizons.note}</p>
          {horizons.ephemeris.length > 0 ? <p className="mono">{horizons.ephemeris[0]}</p> : <pre className="mono">{horizons.excerpt.slice(0, 500)}</pre>}
        </div>
      ) : null}
      </>
      ) : null}
    </section>
  );
}
