"use client";

import { useEffect, useState } from "react";

export function ThemeToggle() {
  const [paper, setPaper] = useState(false);

  useEffect(() => {
    setPaper(document.documentElement.dataset.theme === "paper");
  }, []);

  function toggle() {
    const next = !paper;
    setPaper(next);
    if (next) document.documentElement.dataset.theme = "paper";
    else delete document.documentElement.dataset.theme;
    localStorage.setItem("deepsight-theme", next ? "paper" : "observation");
  }

  return (
    <button type="button" className="theme-toggle" onClick={toggle} aria-pressed={paper}>
      {paper ? "Observation mode" : "Paper mode"}
    </button>
  );
}
