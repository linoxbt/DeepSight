export type NavLink = { href: string; label: string };

export type NavGroup = { title: string; links: NavLink[] };

export const NAV: NavGroup[] = [
  { title: "Start", links: [
    { href: "/", label: "Home" },
    { href: "/explore", label: "Explore" },
    { href: "/lab", label: "Analyze a light curve" },
    { href: "/jobs", label: "Research runs" },
  ] },
  { title: "Archives", links: [
    { href: "/tap", label: "Exoplanets" },
    { href: "/gaia", label: "Nearby stars" },
    { href: "/horizons", label: "Solar system" },
    { href: "/radio", label: "Radio signals" },
  ] },
  { title: "Records", links: [
    { href: "/dashboard", label: "Public dashboard" },
    { href: "/claims", label: "Claims" },
    { href: "/discoveries", label: "Discoveries" },
    { href: "/evidence", label: "Evidence" },
    { href: "/reviews", label: "Reviews" },
  ] },
  { title: "About", links: [
    { href: "/methodology", label: "How it works" },
    { href: "/sources", label: "Data sources" },
    { href: "/catalogue", label: "Catalogue" },
  ] },
];
