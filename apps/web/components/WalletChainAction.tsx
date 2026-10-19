"use client";

import { useEffect, useState } from "react";
import { useAccount, useChainId } from "wagmi";
import { createClient } from "genlayer-js";
import { studionet } from "genlayer-js/chains";
import { api } from "@/lib/api";
import { studioTransactionUrl } from "@/lib/genlayer";

type Prepared = { contract: `0x${string}`; method: string; args: string[]; stage: string };

export function WalletChainAction({ claimId, action, label, reason = "", pending = false, onQueued }: {
  claimId: string; action: "submit" | "review" | "challenge" | "retract" | "supersede";
  label: string; reason?: string; pending?: boolean; onQueued: () => void;
}) {
  const { address, connector } = useAccount();
  const chainId = useChainId();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [hash, setHash] = useState("");
  const storageKey = `deepsight:wallet-tx:${claimId}:${action}`;
  useEffect(() => {
    const saved = localStorage.getItem(storageKey);
    if (!saved) { setHash(""); return; }
    try { setHash((JSON.parse(saved) as { hash: string }).hash || ""); }
    catch { localStorage.removeItem(storageKey); setHash(""); }
  }, [storageKey]);

  async function attach(txHash: string, submittedReason: string, publishAcknowledged: boolean) {
    await api(`/v1/claims/${claimId}/wallet/transaction`, {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ action, reason: submittedReason, publish_acknowledged: publishAcknowledged, tx_hash: txHash }),
    });
    localStorage.removeItem(storageKey);
    setHash("");
    onQueued();
  }

  async function send() {
    setBusy(true); setError("");
    try {
      const pending = localStorage.getItem(storageKey);
      if (pending) {
        const saved = JSON.parse(pending) as { hash: string; reason: string; publishAcknowledged: boolean };
        setHash(saved.hash);
        await attach(saved.hash, saved.reason, saved.publishAcknowledged);
        return;
      }
      if (!address || !connector) throw new Error("Connect and sign in with a wallet first.");
      if (chainId !== studionet.id) throw new Error("Switch your wallet to GenLayer StudioNet before submitting.");
      const provider = await connector.getProvider({ chainId: studionet.id });
      if (!provider || typeof (provider as { request?: unknown }).request !== "function") {
        throw new Error("This wallet does not support GenLayer transactions. Connect a wallet that supports StudioNet.");
      }
      const publishes = action === "submit" || action === "supersede";
      if (publishes && !window.confirm("This action publishes your manifest and evidence before the wallet prompt, even if you later cancel the transaction. Continue?")) return;
      const prepared = await api<Prepared>(`/v1/claims/${claimId}/wallet/prepare`, {
        method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({ action, reason, publish_acknowledged: publishes }),
      });
      const client = createClient({ chain: studionet, account: address, provider: provider as never });
      const txHash = await client.writeContract({
        address: prepared.contract, functionName: prepared.method, args: prepared.args, value: BigInt(0),
      });
      if (typeof txHash !== "string" || !/^0x[0-9a-fA-F]{64}$/.test(txHash)) throw new Error("Wallet did not return a GenLayer transaction hash.");
      localStorage.setItem(storageKey, JSON.stringify({ hash: txHash, reason, publishAcknowledged: publishes }));
      setHash(txHash);
      await attach(txHash, reason, publishes);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Wallet transaction failed");
    } finally { setBusy(false); }
  }

  return <div>
    <button className="ghost" type="button" disabled={busy || pending} onClick={send}>{busy ? "Waiting for wallet or GenLayer…" : pending ? "On-chain transaction pending" : hash ? "Attach existing transaction" : label}</button>
    {hash ? <p className="fine hash">Transaction <a href={studioTransactionUrl(hash)} target="_blank" rel="noopener noreferrer">{hash} ↗</a></p> : null}
    {error ? <p className="fine fail" role="alert">{error}{hash ? " You can retry attaching this transaction without sending another." : ""}</p> : null}
  </div>;
}
