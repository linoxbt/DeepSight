"use client";

import { useEffect, useRef, useState } from "react";
import { usePathname } from "next/navigation";
import { NAV } from "@/lib/navigation";
import { ThemeToggle } from "@/components/ThemeToggle";
import { ObservatoryMark } from "@/components/ObservatoryMark";
import { WalletButton } from "@/components/WalletButton";

export function SiteChrome({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const [ready, setReady] = useState(false);
  const drawerRef = useRef<HTMLElement>(null);
  const toggleRef = useRef<HTMLButtonElement>(null);

  useEffect(() => setReady(true), []);

  useEffect(() => {
    if (!open) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const focusable = () => Array.from(drawerRef.current?.querySelectorAll<HTMLElement>('a[href], button') || []);
    focusable()[0]?.focus();
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
      if (event.key === "Tab") {
        const items = focusable();
        const first = items[0], last = items[items.length - 1];
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
      }
    }
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = previousOverflow;
      toggleRef.current?.focus();
    };
  }, [open]);

  return (
    <>
      <a className="skip-link" href="#content">Skip to content</a>
      <header className="site-header">
        {pathname !== "/" ? <button
          type="button"
          className="menu-toggle"
          ref={toggleRef}
          aria-label={open ? "Close menu" : "Open menu"}
          disabled={!ready}
          aria-expanded={open}
          aria-controls="site-sidebar"
          onClick={() => setOpen((value) => !value)}
        >
          <span />
          <span />
          <span />
        </button> : null}
        <a className="brand" href="/">
          <ObservatoryMark />
          <strong>DEEPSIGHT</strong>
        </a>
        <nav className="primary-nav" aria-label="Primary">
          {(pathname === "/" ? [["/explore", "The workspace"], ["/methodology", "The method"], ["/claims", "The registry"]] : [["/explore", "Explore"], ["/lab", "Discovery Lab"], ["/jobs", "Research runs"], ["/claims", "Claims"]]).map(([href, label]) => (
            <a key={href} href={href} aria-current={pathname === href || pathname.startsWith(`${href}/`) ? "page" : undefined}>{label}</a>
          ))}
        </nav>
        <div className="header-tools">
          <WalletButton />
          <ThemeToggle />
        </div>
      </header>
      {open ? (
        <button type="button" className="drawer-backdrop" aria-label="Close menu" onClick={() => setOpen(false)} />
      ) : null}
      <aside ref={drawerRef} role="dialog" aria-label="All pages" aria-modal={open ? true : undefined} id="site-sidebar" className={open ? "drawer open" : "drawer"} aria-hidden={!open} inert={!open}>
        <div className="drawer-head">
          <p className="kicker">Explore DeepSight</p>
          <button type="button" className="ghost" onClick={() => setOpen(false)}>
            Close
          </button>
        </div>
        <nav aria-label="Pages">
          {NAV.map((group) => (
            <div key={group.title}>
              <h2>{group.title}</h2>
              <ul>
                {group.links.map((link) => {
                  const current = link.href === "/" ? pathname === "/" : pathname === link.href || pathname.startsWith(`${link.href}/`);
                  return (
                    <li key={link.href}>
                      <a href={link.href} aria-current={current ? "page" : undefined} onClick={() => setOpen(false)}>
                        <strong>{link.label}</strong>
                      </a>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </nav>
      </aside>
      <main id="content">{children}</main>
      <footer className="site-footer">
        <div className="footer-columns">
          <div><a className="brand" href="/"><ObservatoryMark /><strong>DEEPSIGHT</strong></a><p>Explore the universe. Follow the evidence.</p></div>
          <div><p className="kicker">Explore</p><a href="/explore">Get started</a><a href="/lab">Analyze</a><a href="/claims">Records</a></div>
          <div><p className="kicker">About</p><a href="/methodology">How it works</a><a href="/sources">Data sources</a></div>
        </div>
        <div className="footer-bottom"><p>Research workspace · DeepSight</p><p className="mono">GenLayer StudioNet</p></div>
      </footer>
    </>
  );
}
