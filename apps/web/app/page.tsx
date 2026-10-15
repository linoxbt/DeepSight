import { Shell } from "@/components/Shell";
import { ObservatoryMark } from "@/components/ObservatoryMark";
import Image from "next/image";

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
      <figure className="cosmos-hero">
        <div className="cosmos-galaxy"><Image src="/images/andromeda-hubble.jpg" alt="Hubble view of the Andromeda galaxy" fill priority sizes="(max-width: 860px) 100vw, 520px" /></div>
        <div className="cosmos-earth"><Image src="/images/earth-blue-marble.jpg" alt="NASA Blue Marble view of Earth" fill priority sizes="(max-width: 860px) 45vw, 220px" /></div>
        <figcaption><span>Our home, and the wider universe.</span><span>Imagery: <a href="https://science.nasa.gov/resource/blue-marble-2002/">NASA Earth Observatory</a> · <a href="https://science.nasa.gov/asset/hubble/andromeda-galaxy/">NASA/ESA Hubble</a></span></figcaption>
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
