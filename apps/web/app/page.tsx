import { Shell } from "@/components/Shell";
import { ObservatoryMark } from "@/components/ObservatoryMark";

const steps = [
  ["01", "Observe.", "Bring a TESS light curve into the workspace. Keep the archive and its provenance in view.", "/explore"],
  ["02", "Investigate.", "Search for periodic transits. Inspect the diagnostics, uncertainties, and alternative explanations.", "/lab"],
  ["03", "Document.", "Package the analysis in a reproducible evidence manifest, with artifacts another researcher can inspect.", "/evidence"],
  ["04", "Review.", "Check the evidence against the protocol. Keep local results and chain decisions distinct.", "/reviews"],
];
export default function HomePage() {
  return <Shell>
    <section className="landing-hero">
      <div className="hero-copy">
        <p className="edition"><span /> An open research workspace</p>
        <h1>Wonder,<br /><em>with evidence.</em></h1>
        <p className="lede">The universe gives us signals.<br />Make the case for what they mean.</p>
        <p className="hero-description">Explore astronomical archives, investigate transit candidates, and put reproducible evidence on the record.</p>
        <div className="actions"><a className="primary" href="/explore">Enter the workspace ↗</a><a className="text-link" href="/methodology">How it works →</a></div>
        <p className="micro">OPEN ARCHIVES. TRACEABLE ANALYSIS. HUMAN JUDGMENT.</p>
      </div>
      <figure className="specimen">
        <div className="specimen-meta"><span>Field notes / 001</span><span>Photometry</span></div>
        <h2>A small dip.<br />A question worth asking.</h2>
        <p className="fine muted">A transit leaves a pattern in a star’s light.</p>
        <svg viewBox="0 0 500 240" role="img" aria-label="Illustrative light curve with a transit dip. Schematic, not an observation.">
          {[55,105,155,205].map(y=><line key={y} x1="30" x2="480" y1={y} y2={y} stroke="var(--line)" />)}
          <path d="M30 73H178C197 73 200 157 221 157H276C297 157 300 73 320 73H480" fill="none" stroke="var(--accent)" strokeWidth="1.5" opacity=".4" />
          {Array.from({length:85},(_,i)=>{const x=32+i*5.25; const dip=1/(1+Math.exp(-(x-199)/4))-1/(1+Math.exp(-(x-298)/4));return <circle key={i} cx={x} cy={73+dip*84+((i*17)%13)-6} r="2" fill="var(--accent)" />;})}
          <text x="30" y="233">TIME →</text><text x="30" y="25">RELATIVE FLUX</text>
          <line x1="249" x2="249" y1="170" y2="196" stroke="var(--gold)" /><text x="262" y="193">A candidate, not a conclusion.</text>
        </svg>
        <figcaption><span className="specimen-dot" /> Schematic illustration · not an archive observation</figcaption>
      </figure>
    </section>
    <div className="archive-strip"><span className="micro">A window into the archives</span><a href="/explore">MAST / TESS</a><a href="/tap">NASA Exoplanet Archive</a><a href="/gaia">Gaia</a><a href="/horizons">JPL Horizons</a></div>
    <section className="process-section">
      <div className="section-heading"><div><p className="kicker">From signal to scrutiny</p><h2>Follow the evidence.</h2></div><a className="text-link" href="/methodology">Read the methodology →</a></div>
      <div className="process-grid">{steps.map(([n,title,description,href])=><a key={n} href={href}><span className="step-number">{n}</span><h3>{title}</h3><p>{description}</p><span className="step-arrow" aria-hidden="true">↗</span></a>)}</div>
    </section>
    <section className="review-section">
      <div className="evidence-seal"><ObservatoryMark /><span>PROOF OF DISCOVERY</span><strong>Evidence<br /><em>before certainty.</em></strong><span>OBSERVE · REPRODUCE · REVIEW</span></div>
      <div><p className="kicker">An honest record</p><h2>A protocol can review a case.<br /><em>It cannot confirm a world.</em></h2><p className="review-copy">DeepSight checks whether the evidence is complete, traceable, and ready for scrutiny. A passing checklist is a result about the package. Scientific confirmation belongs to the scientific process.</p><aside className="callout"><strong>Keep every conclusion in context.</strong><p>Local policy previews and chain decisions are recorded separately. Missing comparisons, archive gaps, and synthetic data remain visible.</p></aside><a className="text-link" href="/claims">Explore the evidence registry →</a></div>
    </section>
    <section className="closing-note"><p className="kicker">There is more to look into.</p><h2>Start with a signal.<br /><em>Leave a trail.</em></h2><a className="primary" href="/explore">Open the Explorer ↗</a></section>
  </Shell>;
}
