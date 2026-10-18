import { Shell } from "@/components/Shell";

export default function MethodologyPage() {
  return (
    <Shell active="/methodology">
      <header className="page-head">
        <div>
          <p className="kicker">Protocol</p>
          <h1>What is verified</h1>
        </div>
      </header>
      <div className="stack">
        <section className="panel">
          <h2>Celestial evidence, version celestial-v3</h2>
          <p>
            The policy looks for a target, coordinates, an observation id, a period, a depth or signal-to-noise metric,
            an artifact checksum, a catalogue snapshot, odd-even and secondary-eclipse notes, limitations, and a
            scientific status that does not claim confirmation.
          </p>
          <p>
            Allowlisted archives are MAST, the NASA Exoplanet Archive, Gaia, and JPL Horizons. Anything else, including
            the local synthetic series, returns NEEDS_HUMAN_REVIEW when the rest of the package is complete.
          </p>
          <p>
            For a known object with an exact TIC identifier, GenLayer validators query NASA TAP themselves and compare
            the measured period and transit depth with published values. A mismatch, missing published depth, or an
            unpublished candidate stays in human review. This comparison does not reprocess the underlying TESS pixels.
          </p>
        </section>
        <section className="panel">
          <h2>Outcomes</h2>
          <p>EVIDENCE_SUFFICIENT means the package met the written checks and the published period and depth agreed with a live archive row. It is not a scientific confirmation.</p>
          <p>EVIDENCE_INSUFFICIENT means a required field is missing, or the text claims a confirmed discovery.</p>
          <p>NEEDS_HUMAN_REVIEW means a person has to judge provenance or completeness before anyone treats the package as settled.</p>
        </section>
        <section className="panel">
          <h2>What this build does not do</h2>
          <p>
            It downloads one TESS SPOC light curve, queries NASA TAP, Gaia DR3, and JPL Horizons, and lists
            Breakthrough Listen catalog rows without downloading the multi-gigabyte files. The radio screen uses one
            public Voyager 1 tutorial spectrum. A chain submission is a StudioNet transaction when a contract address
            is configured. There is no reward.
          </p>
          <p>
            The intelligent contract in <span className="mono">contracts/proof_of_discovery.py</span> is the consensus
            copy of the same rules. Until a contract address is configured, the API stores a local preview and says so
            on the claim.
          </p>
          <p>
            Signal integrity, version signal-v3, requires an observation, a frequency and time range, a noise method,
            calibration, an artifact hash, and at least one RFI test. Missing an off-target comparison stays in human
            review. The outcome is still not a technosignature.
          </p>
        </section>
      </div>
    </Shell>
  );
}
