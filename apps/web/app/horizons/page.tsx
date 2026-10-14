"use client";

import { Archives } from "@/components/Archives";
import { Shell } from "@/components/Shell";

export default function HorizonsPage() {
  return (
    <Shell>
      <header className="page-head">
        <div>
          <p className="kicker">JPL Horizons</p>
          <h1>Observer ephemeris</h1>
        </div>
      </header>
      <p className="fine muted">
        Horizons returns the motion of a known body. An ephemeris is not a transit detection. Stars such as TOI-270 often have no small-body record.
      </p>
      <Archives view="horizons" />
    </Shell>
  );
}
