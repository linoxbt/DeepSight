import { Shell } from "@/components/Shell";
import { NAV } from "@/lib/navigation";

export default function HomePage() {
  const sections = NAV.filter((group) => group.title !== "Office");
  return (
    <Shell>
      <section className="landing-hero">
        <div>
          <p className="kicker">GenLayer evidence protocol</p>
          <h1>Explore the unknown. Verify the evidence.</h1>
          <p className="lede">
            DeepSight runs a reproducible transit search and packages the result as an evidence manifest.
            Each tool lives on its own page. The policy checks whether a manifest is complete. It does not confirm a planet.
          </p>
          <div className="actions">
            <a className="primary" href="/explore">Open the Explorer</a>
            <a className="ghost" href="/methodology">Read the protocol</a>
          </div>
        </div>
        <figure className="hero-card">
          <svg viewBox="0 0 640 240" role="img" aria-label="Schematic light curve with a transit dip near day 8. Illustration only, not an observation.">
            <title>Schematic calibration light curve</title>
            {Array.from({ length: 80 }, (_, index) => {
              const x = 36 + index * 7.2;
              const dip = Math.exp(-((index - 32) ** 2) / 8);
              const y = 78 + dip * 78 + ((index * 17) % 5) - 2;
              return <circle key={index} cx={x} cy={y} r="1.6" fill="#00A7A0" />;
            })}
            <text x="36" y="214" fill="currentColor" fontSize="12" fontFamily="IBM Plex Mono, monospace">time (days)</text>
            <text x="36" y="24" fill="currentColor" fontSize="12" fontFamily="IBM Plex Mono, monospace">relative flux</text>
          </svg>
          <figcaption>Schematic calibration curve. Not an archive observation and not a discovered planet.</figcaption>
        </figure>
      </section>

      <section className="landing-index">
        <h2>Each task has its own page</h2>
        <p className="fine muted">Open a page from this index or from the menu. Nothing on this page runs a search.</p>
        {sections.map((group) => (
          <div key={group.title} className="index-group">
            <h3>{group.title}</h3>
            <ul>
              {group.links.map((link) => (
                <li key={link.href}>
                  <a href={link.href}>
                    <strong>{link.label}</strong>
                    <span>{link.summary}</span>
                  </a>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </section>

      <section className="outcome-grid">
        <article>
          <p className="kicker">Sufficient</p>
          <h2>EVIDENCE_SUFFICIENT</h2>
          <p>The manifest met the checklist. The scientific status stays unconfirmed or known. Confirmation stays false.</p>
        </article>
        <article>
          <p className="kicker">Review</p>
          <h2>NEEDS_HUMAN_REVIEW</h2>
          <p>An archive miss, a missing off-target comparison, or a synthetic series stays with a person.</p>
        </article>
        <article>
          <p className="kicker">Insufficient</p>
          <h2>EVIDENCE_INSUFFICIENT</h2>
          <p>The package does not support a protocol pass. That is a record about the evidence, not a rejection of a world.</p>
        </article>
      </section>

      <aside className="callout">
        <strong>Protocol evidence is not peer review.</strong>
        <p>
          The contract refuses statuses such as “planet confirmed” or “extraterrestrial”. A listing on the discoveries page
          is a local protocol result. Chain finality, when a transaction exists, is a separate line on the claim.
        </p>
      </aside>
    </Shell>
  );
}
