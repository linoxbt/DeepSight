"use client";

import { Archives } from "@/components/Archives";
import { Shell } from "@/components/Shell";

export default function TapPage() {
  return (
    <Shell>
      <header className="page-head">
        <div>
          <p className="kicker">NASA Exoplanet Archive</p>
          <h1>Planetary systems table</h1>
        </div>
      </header>
      <p className="fine muted">
        This page queries the live TAP service, table pscomppars. A returned row is a published parameter set. It is not a new confirmation.
      </p>
      <Archives view="tap" />
    </Shell>
  );
}
