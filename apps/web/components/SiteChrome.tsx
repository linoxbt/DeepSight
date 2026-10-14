"use client";

import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { NAV } from "@/lib/navigation";
import { ThemeToggle } from "@/components/ThemeToggle";
import { WalletButton } from "@/components/WalletButton";

export function SiteChrome({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  useEffect(() => {
    setOpen(false);
  }, [pathname]);

  useEffect(() => {
    if (!open) return;
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  return (
    <>
      <header className="site-header">
        <button
          type="button"
          className="menu-toggle"
          aria-label={open ? "Close menu" : "Open menu"}
          aria-expanded={open}
          aria-controls="site-sidebar"
          onClick={() => setOpen((value) => !value)}
        >
          <span />
          <span />
          <span />
        </button>
        <a className="brand" href="/">
          <strong>DEEPSIGHT</strong>
          <span>Proof of Discovery</span>
        </a>
        <div className="header-tools">
          <WalletButton />
          <ThemeToggle />
        </div>
      </header>
      {open ? (
        <button type="button" className="drawer-backdrop" aria-label="Close menu" onClick={() => setOpen(false)} />
      ) : null}
      <aside id="site-sidebar" className={open ? "drawer open" : "drawer"} aria-hidden={!open} inert={!open}>
        <div className="drawer-head">
          <p className="kicker">Pages</p>
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
                        <span>{link.summary}</span>
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
        <p>DeepSight records evidence. It does not certify a planet, a signal, or a discovery.</p>
        <p className="mono">GenLayer StudioNet · No rewards · No staking</p>
      </footer>
    </>
  );
}
