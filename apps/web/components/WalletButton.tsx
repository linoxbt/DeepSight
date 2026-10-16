"use client";

import { useEffect, useState } from "react";
import { useAppKit, useAppKitAccount } from "@reown/appkit/react";
import { useSignMessage } from "wagmi";
import { walletReady } from "@/lib/appkit";
import { api } from "@/lib/api";

export function WalletButton() {
  const { open } = useAppKit();
  const { address, isConnected } = useAppKitAccount();
  const { signMessageAsync } = useSignMessage();
  const [session, setSession] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    api("/v1/auth/session").then(body => { if (active) setSession(body.address); }).catch(() => { if (active) setSession(""); });
    return () => { active = false; };
  }, [address]);

  async function signIn() {
    if (!address) { await open(); return; }
    setBusy(true); setError("");
    try {
      const challenge = await api("/v1/auth/challenge", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ address }) });
      const signature = await signMessageAsync({ message: challenge.message });
      const body = await api("/v1/auth/session", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ challenge_id: challenge.id, signature }) });
      setSession(body.address);
      window.dispatchEvent(new Event("deepsight-auth"));
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Sign-in failed"); }
    finally { setBusy(false); }
  }
  async function signOut() {
    try { await api("/v1/auth/session", { method: "DELETE" }); setSession(""); window.dispatchEvent(new Event("deepsight-auth")); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Sign-out failed"); }
  }
  if (!walletReady) return <span className="wallet-quiet">Wallet unavailable</span>;
  const authenticated = !!session && (!isConnected || session.toLowerCase() === address?.toLowerCase());
  return <div className="wallet-session">
    {authenticated ? <button type="button" className="ghost" onClick={signOut} title="Sign out">{session.slice(0, 6)}…{session.slice(-4)} · Sign out</button> :
      <button type="button" className="primary" disabled={busy} onClick={isConnected ? signIn : () => open()}>{busy ? "Signing in…" : isConnected ? "Sign in" : "Connect wallet"}</button>}
    {error && <span role="alert" className="fine fail">{error}</span>}
  </div>;
}
