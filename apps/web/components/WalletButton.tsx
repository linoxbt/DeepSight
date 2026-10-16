"use client";

import { useEffect, useRef, useState } from "react";
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
  const walletRef = useRef("");
  walletRef.current = isConnected ? address?.toLowerCase() || "" : "";
  useEffect(() => {
    let active = true;
    api("/v1/auth/session").then(body => { if (active) setSession(body.address); }).catch(() => { if (active) setSession(""); });
    return () => { active = false; };
  }, []);

  async function signIn() {
    if (!address) { await open(); return; }
    const signingAddress = address.toLowerCase();
    setBusy(true); setError("");
    try {
      const challenge = await api("/v1/auth/challenge", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ address }) });
      const signature = await signMessageAsync({ message: challenge.message });
      if (walletRef.current !== signingAddress) throw new Error("Wallet changed during sign-in. Connect the intended wallet and try again.");
      const body = await api("/v1/auth/session", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ challenge_id: challenge.id, signature }) });
      setSession(body.address);
      window.dispatchEvent(new Event("deepsight-auth"));
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Sign-in failed"); }
    finally { setBusy(false); }
  }
  async function signOut() {
    setBusy(true); setError("");
    try { await api("/v1/auth/session", { method: "DELETE" }); setSession(""); window.dispatchEvent(new Event("deepsight-auth")); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Sign-out failed"); }
    finally { setBusy(false); }
  }
  if (!walletReady) return <span className="wallet-quiet">Wallet unavailable</span>;
  const account = isConnected && address ? address : "";
  const sessionMatchesWallet = !!session && !!account && session.toLowerCase() === account.toLowerCase();
  return <div className="wallet-session">
    <button type="button" className={account ? "ghost" : "primary"} onClick={() => open(account ? { view: "Account" } : undefined)}
      aria-label={account ? `Wallet ${account}. Open wallet account` : "Connect wallet"}>
      {account ? `${account.slice(0, 6)}…${account.slice(-4)}` : "Connect wallet"}
    </button>
    {account && !session ? <button type="button" className="primary" disabled={busy} onClick={signIn}>{busy ? "Signing in…" : "Sign in to DeepSight"}</button> : null}
    {session ? <button type="button" className="ghost" disabled={busy} onClick={signOut}>{busy ? "Signing out…" : "Sign out of DeepSight"}</button> : null}
    {session && account && !sessionMatchesWallet ? <span role="alert" className="fine fail">This session belongs to another wallet. Sign out before continuing.</span> : null}
    {error && <span role="alert" className="fine fail">{error}</span>}
  </div>;
}
