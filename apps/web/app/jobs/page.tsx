"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Shell } from "@/components/Shell";

type Job = { id: string; kind: string; status: string; error: string; created: number; href: string };
export default function JobsPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [error, setError] = useState("");
  const [loaded, setLoaded] = useState(false);
  useEffect(() => {
    let active = true;
    async function refresh() {
      try { const body = await api("/v1/jobs"); if (active) { setJobs(body.jobs); setError(""); setLoaded(true); } }
      catch (reason) { if (active) setError(reason instanceof Error ? reason.message : "Could not load research runs"); }
    }
    refresh();
    const timer = setInterval(refresh, 4000);
    window.addEventListener("deepsight-auth", refresh);
    return () => { active = false; clearInterval(timer); window.removeEventListener("deepsight-auth", refresh); };
  }, []);
  return <Shell active="/jobs">
    <header className="page-head"><div><p className="kicker">Research workspace</p><h1>Research runs</h1></div><a className="primary" href="/lab">New transit analysis</a></header>
    <p className="muted">Your jobs continue in the background. Return here to open completed results.</p>
    {error && <p className="callout fail" role="alert">{error}</p>}
    {loaded && !jobs.length && <p className="callout">No runs yet. Import an observation or start a calibration analysis.</p>}
    <div className="stack">{jobs.map(job => <article className="panel" key={job.id}>
      <div className="page-head"><h2>{job.kind === "analysis" ? "Transit analysis" : job.kind === "radio" ? "Radio screening" : "TESS import"}</h2><span className="mono">{job.status}</span></div>
      <p className="fine muted">{new Date(job.created * 1000).toLocaleString()}</p>
      {job.error && <p className="callout fail">{job.error}</p>}
      {job.href && <a className="ghost" href={job.href}>Open result</a>}
    </article>)}</div>
  </Shell>;
}
