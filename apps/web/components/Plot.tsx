"use client";

import { useState } from "react";

export function Plot({
  x,
  y,
  xLabel,
  yLabel,
  description,
  shade,
}: {
  x: number[];
  y: number[];
  xLabel: string;
  yLabel: string;
  description: string;
  shade?: { from: number; to: number } | null;
}) {
  const [hovered, setHovered] = useState<number | null>(null);
  const width = 640;
  const height = 260;
  const pad = { left: 56, right: 12, top: 14, bottom: 34 };
  if (x.length < 2 || y.length !== x.length) {
    return <p className="muted">No series to plot.</p>;
  }
  const minX = Math.min(...x);
  const maxX = Math.max(...x);
  const minY = Math.min(...y);
  const maxY = Math.max(...y);
  const spanX = maxX - minX || 1;
  const spanY = maxY - minY || 1;
  const innerW = width - pad.left - pad.right;
  const innerH = height - pad.top - pad.bottom;
  const sx = (value: number) => pad.left + ((value - minX) / spanX) * innerW;
  const sy = (value: number) => pad.top + (1 - (value - minY) / spanY) * innerH;
  const path = x.map((value, index) => `${index === 0 ? "M" : "L"}${sx(value).toFixed(1)},${sy(y[index]).toFixed(1)}`).join(" ");
  const yTicks = [maxY, (maxY + minY) / 2, minY];

  function downloadCsv() {
    const rows = [`${xLabel},${yLabel}`, ...x.map((value, index) => `${value},${y[index]}`)];
    const url = URL.createObjectURL(new Blob([rows.join("\n") + "\n"], { type: "text/csv" }));
    const link = document.createElement("a");
    link.href = url; link.download = "deepsight-plot.csv"; link.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  return (
    <figure className="plot">
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={description}
        onMouseMove={event => {
          const bounds = event.currentTarget.getBoundingClientRect();
          const position = ((event.clientX - bounds.left) / bounds.width) * width;
          const value = minX + ((position - pad.left) / innerW) * spanX;
          let nearest = 0;
          for (let index = 1; index < x.length; index++) if (Math.abs(x[index] - value) < Math.abs(x[nearest] - value)) nearest = index;
          setHovered(nearest);
        }} onMouseLeave={() => setHovered(null)}>
        <title>{description}</title>
        {yTicks.map((tick) => (
          <g key={tick}>
            <line className="grid" x1={pad.left} x2={width - pad.right} y1={sy(tick)} y2={sy(tick)} />
            <text x={pad.left - 8} y={sy(tick) + 4} textAnchor="end">
              {tick.toFixed(4)}
            </text>
          </g>
        ))}
        {shade ? (
          <rect
            className="shade"
            x={sx(shade.from)}
            y={pad.top}
            width={Math.max(1, sx(shade.to) - sx(shade.from))}
            height={innerH}
          />
        ) : null}
        <path className="series" d={path} />
        {hovered !== null ? <circle cx={sx(x[hovered])} cy={sy(y[hovered])} r="5" fill="var(--accent)" /> : null}
        <text x={pad.left} y={height - 8}>
          {xLabel}
        </text>
        <text x={width - pad.right} y={14} textAnchor="end">
          {yLabel}
        </text>
      </svg>
      <figcaption>{description}</figcaption>
      {hovered !== null ? <p className="fine mono" aria-live="polite">{xLabel}: {x[hovered]} · {yLabel}: {y[hovered]}</p> : null}
      <button type="button" className="ghost" onClick={downloadCsv}>Download plot data (CSV)</button>
      <p className="alt">{description}</p>
    </figure>
  );
}
