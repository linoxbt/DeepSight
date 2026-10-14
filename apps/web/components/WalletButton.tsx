"use client";

import { useAppKit, useAppKitAccount } from "@reown/appkit/react";
import { walletReady } from "@/lib/appkit";

function shortAddress(value: string) {
  return `${value.slice(0, 6)}…${value.slice(-4)}`;
}

export function WalletButton() {
  const { open } = useAppKit();
  const { address, isConnected } = useAppKitAccount();

  if (!walletReady) {
    return <span className="wallet-quiet">Wallet unavailable</span>;
  }

  if (isConnected && address) {
    return (
      <button type="button" className="ghost wallet-button" onClick={() => open()}>
        {shortAddress(address)}
      </button>
    );
  }

  return (
    <button type="button" className="primary wallet-button" onClick={() => open()}>
      Connect wallet
    </button>
  );
}
