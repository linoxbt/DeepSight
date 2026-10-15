"use client";

import { useEffect, useState } from "react";

export function ThemeToggle() {
  const [paper, setPaper] = useState(true);

  useEffect(() => {
    setPaper(document.documentElement.dataset.theme !== "observation");
  }, []);

  function toggle() {
    const next = !paper;
    setPaper(next);
    if (next) document.documentElement.dataset.theme = "paper";
    else document.documentElement.dataset.theme = "observation";
    try { localStorage.setItem("deepsight-theme", next ? "paper" : "observation"); } catch {}
  }

  return (
    <button type="button" className="theme-toggle" onClick={toggle} aria-pressed={paper}>
      {paper ? "Observation mode" : "Paper mode"}
    </button>
  );
}
