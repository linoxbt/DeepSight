"use client";

import { useEffect, useState } from "react";

type Mark = { x: number; y: number };
type ImageInfo = { width: number; height: number; histogram: number[] };

export function ImageDesk() {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState("");
  const [info, setInfo] = useState<ImageInfo | null>(null);
  const [marks, setMarks] = useState<Mark[]>([]);
  const [note, setNote] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    if (!file) return;
    const url = URL.createObjectURL(file);
    setPreview(url);
    let cancelled = false;
    const image = new Image();
    image.onload = () => {
      if (cancelled) return;
      const canvas = document.createElement("canvas");
      const scale = Math.min(1, 512 / Math.max(image.naturalWidth, image.naturalHeight));
      canvas.width = Math.max(1, Math.round(image.naturalWidth * scale));
      canvas.height = Math.max(1, Math.round(image.naturalHeight * scale));
      const context = canvas.getContext("2d", { willReadFrequently: true });
      if (!context) { setError("This browser cannot inspect the image."); return; }
      context.drawImage(image, 0, 0, canvas.width, canvas.height);
      const pixels = context.getImageData(0, 0, canvas.width, canvas.height).data;
      const histogram = Array.from({ length: 32 }, () => 0);
      for (let i = 0; i < pixels.length; i += 4) {
        const light = Math.round(0.2126 * pixels[i] + 0.7152 * pixels[i + 1] + 0.0722 * pixels[i + 2]);
        histogram[Math.min(31, Math.floor(light / 8))]++;
      }
      setInfo({ width: image.naturalWidth, height: image.naturalHeight, histogram });
    };
    image.onerror = () => setError("The image could not be opened. Try a JPG, PNG, or WebP file.");
    image.src = url;
    return () => { cancelled = true; URL.revokeObjectURL(url); };
  }, [file]);

  function chooseImage(next: File | undefined) {
    setError(""); setInfo(null); setMarks([]); setNote("");
    if (!next) { setFile(null); return; }
    if (!["image/jpeg", "image/png", "image/webp"].includes(next.type)) {
      setFile(null); setError("Choose a JPG, PNG, or WebP image."); return;
    }
    if (next.size > 15 * 1024 * 1024) {
      setFile(null); setError("Choose an image smaller than 15 MB."); return;
    }
    setFile(next);
  }

  function addMark(event: React.MouseEvent<HTMLButtonElement>) {
    const rect = event.currentTarget.getBoundingClientRect();
    setMarks((current) => [...current, {
      x: Math.round(((event.clientX - rect.left) / rect.width) * 1000) / 10,
      y: Math.round(((event.clientY - rect.top) / rect.height) * 1000) / 10,
    }]);
  }

  function downloadNotes() {
    if (!file || !info) return;
    const report = { type: "deepsight-image-note", image: file.name, width: info.width, height: info.height, note, marks, created_at: new Date().toISOString(), status: "visual observation only" };
    const url = URL.createObjectURL(new Blob([JSON.stringify(report, null, 2)], { type: "application/json" }));
    const link = document.createElement("a"); link.href = url; link.download = "deepsight-image-notes.json"; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  const max = Math.max(1, ...(info?.histogram || []));
  return <section className="panel image-desk" id="image-desk">
    <div className="desk-heading"><div><p className="kicker">Your image</p><h2>Look closer at a sky image</h2><p className="muted">Add a photo, tap points of interest, and keep a note. Your image stays in this browser.</p></div></div>
    <label className="upload-zone">
      <span aria-hidden="true" className="upload-symbol">✦</span>
      <strong>{file ? "Choose a different image" : "Choose a sky image"}</strong>
      <span>JPG, PNG, or WebP · up to 15 MB</span>
      <input aria-label="Choose a sky image" type="file" accept="image/jpeg,image/png,image/webp" onChange={(event) => chooseImage(event.target.files?.[0])} />
    </label>
    {error ? <p role="alert" className="fail">{error}</p> : null}
    {preview && file ? <div className="image-inspection">
      <div>
        <button type="button" className="image-stage" onClick={addMark} aria-label="Mark a point on the image">
          {/* The object URL is a user-selected local file, not a remote image. */}
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={preview} alt={`Uploaded image: ${file.name}`} />
          {marks.map((mark, index) => <span key={index} className="image-pin" style={{ left: `${mark.x}%`, top: `${mark.y}%` }}>{index + 1}</span>)}
        </button>
        <p className="fine muted">Tap the image to mark a feature. This visual notebook does not identify celestial objects or detect transits.</p>
      </div>
      <div className="image-details">
        <p className="kicker">Image details</p>
        <strong>{file.name}</strong>
        {info ? <><p>{info.width.toLocaleString()} × {info.height.toLocaleString()} pixels · {(file.size / 1024 / 1024).toFixed(2)} MB</p>
          <p className="fine muted">Brightness across the image</p>
          <div className="brightness-chart" role="img" aria-label="Image brightness histogram, from dark on the left to bright on the right">{info.histogram.map((value, i) => <span key={i} style={{ height: `${Math.max(2, (value / max) * 100)}%` }} />)}</div>
          <div className="chart-ends"><span>Dark</span><span>Bright</span></div>
        </> : <p>Reading image…</p>}
        <label htmlFor="image-note">What caught your eye?</label>
        <textarea id="image-note" value={note} onChange={(event) => setNote(event.target.value)} placeholder="Describe a feature or question…" rows={4} maxLength={2000} />
        <p className="fine muted">{marks.length} {marks.length === 1 ? "point" : "points"} marked</p>
        <div className="actions"><button type="button" className="primary" disabled={!info} onClick={downloadNotes}>Download notes</button><button type="button" className="ghost" disabled={marks.length === 0} onClick={() => setMarks([])}>Clear marks</button></div>
      </div>
    </div> : null}
  </section>;
}
