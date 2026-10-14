"use client";

import { Archives } from "@/components/Archives";
import { Shell } from "@/components/Shell";

export default function GaiaPage() {
  return (
    <Shell>
      <header className="page-head">
        <div>
          <p className="kicker">ESA Gaia DR3</p>
          <h1>Nearby sources</h1>
        </div>
      </header>
      <p className="fine muted">
        A cone search returns catalogued sources near a position. A neighbor is a position match. It is not a planet identification.
      </p>
      <Archives view="gaia" />
    </Shell>
  );
}
