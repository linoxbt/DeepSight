"use client";
import { useState } from "react";
import { useSignMessage } from "wagmi";
import { api } from "@/lib/api";

export function ChainAction({ claimId, action, label, reason = "", txHash = "", onQueued }: { claimId: string; action: string; label: string; reason?: string; txHash?: string; onQueued: () => void }) {
  const { signMessageAsync } = useSignMessage();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function authorize() {
    setBusy(true); setError("");
    try {
      const intent = await api(`/v1/claims/${claimId}/intent`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ action, reason, tx_hash: txHash }) });
      const signature = await signMessageAsync({ message: intent.message });
      await api(`/v1/claims/${claimId}/authorize`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ intent_id: intent.id, signature }) });
      onQueued();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Authorization failed"); }
    finally { setBusy(false); }
  }
  return <div><button className="ghost" disabled={busy} onClick={authorize}>{busy ? "Authorizing…" : label}</button>{error && <p className="fine fail" role="alert">{error}</p>}</div>;
}
