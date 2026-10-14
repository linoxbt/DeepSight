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

  return (
    <figure className="plot">
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={description}>
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
        <text x={pad.left} y={height - 8}>
          {xLabel}
        </text>
        <text x={width - pad.right} y={14} textAnchor="end">
          {yLabel}
        </text>
      </svg>
      <figcaption>{description}</figcaption>
      <p className="alt">{description}</p>
    </figure>
  );
}
