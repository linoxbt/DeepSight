export type NavLink = { href: string; label: string; summary: string };

export type NavGroup = { title: string; links: NavLink[] };

export const NAV: NavGroup[] = [
  {
    title: "Office",
    links: [
      { href: "/", label: "Home", summary: "What this office publishes, and what it refuses to claim." },
    ],
  },
  {
    title: "Observe",
    links: [
      { href: "/explore", label: "Explorer", summary: "Import one TESS sector from MAST and search local targets." },
      { href: "/tap", label: "NASA Exoplanet Archive", summary: "Live TAP query of published planet parameters." },
      { href: "/gaia", label: "Gaia", summary: "Nearby Gaia DR3 sources. A neighbor is not a planet." },
      { href: "/horizons", label: "JPL Horizons", summary: "Observer ephemerides. An ephemeris is not a transit." },
      { href: "/catalogue", label: "Catalogue extract", summary: "The local fallback table used when TAP is off." },
      { href: "/sources", label: "Source status", summary: "Which archives this build can reach." },
    ],
  },
  {
    title: "Analyze",
    links: [
      { href: "/jobs", label: "Research runs", summary: "Queued work, progress, and completed analyses." },
      { href: "/lab", label: "Discovery Lab", summary: "Box-least-squares on one light curve." },
      { href: "/evidence", label: "Evidence", summary: "The manifest, the hash, and the checklist." },
      { href: "/radio", label: "Radio", summary: "Breakthrough Listen rows and the Voyager calibration screen." },
    ],
  },
  {
    title: "Record",
    links: [
      { href: "/discoveries", label: "Discoveries", summary: "Local records whose evidence met the policy." },
      { href: "/claims", label: "Claims", summary: "Every stored manifest and its protocol status." },
      { href: "/reviews", label: "Human review", summary: "Notes on records that still need a person." },
      { href: "/methodology", label: "Protocol", summary: "What the policy checks, and what it will not say." },
    ],
  },
];
