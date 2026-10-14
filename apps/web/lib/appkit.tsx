"use client";

import { createAppKit } from "@reown/appkit/react";
import { WagmiAdapter } from "@reown/appkit-adapter-wagmi";
import { defineChain, type AppKitNetwork } from "@reown/appkit/networks";
import { createConfig, http } from "wagmi";

export const REOWN_PROJECT_ID =
  process.env.NEXT_PUBLIC_REOWN_PROJECT_ID || "f0d6f8162be1beccf221b4e2f8bd7026";

const studio = defineChain({
  id: 61999,
  caipNetworkId: "eip155:61999",
  chainNamespace: "eip155",
  name: "GenLayer Studio Network",
  nativeCurrency: { name: "GEN", symbol: "GEN", decimals: 18 },
  rpcUrls: { default: { http: ["https://studio.genlayer.com/api"] } },
  blockExplorers: { default: { name: "GenLayer Explorer", url: "https://genlayer-explorer.vercel.app" } },
  testnet: true,
}) as AppKitNetwork;

const networks = [studio] as [AppKitNetwork, ...AppKitNetwork[]];

function build() {
  try {
    const adapter = new WagmiAdapter({ networks, projectId: REOWN_PROJECT_ID, ssr: true });
    createAppKit({
      adapters: [adapter],
      networks,
      defaultNetwork: studio,
      projectId: REOWN_PROJECT_ID,
      metadata: {
        name: "DeepSight",
        description: "Evidence manifests for astronomy. Protocol review is not a scientific confirmation.",
        url: "https://deepsight.netlify.app",
        icons: ["https://deepsight.netlify.app/icon.svg"],
      },
      themeMode: "dark",
      themeVariables: {
        "--w3m-accent": "#00A7A0",
        "--w3m-border-radius-master": "1px",
        "--w3m-font-family": "Inter, Segoe UI, sans-serif",
      },
      features: { analytics: false, email: false, socials: [] },
    });
    return { wagmiConfig: adapter.wagmiConfig, ready: true };
  } catch (error) {
    console.warn("Wallet connection is unavailable.", error);
    return {
      wagmiConfig: createConfig({
        chains: [networks[0] as never],
        transports: { [networks[0].id as number]: http() },
      }),
      ready: false,
    };
  }
}

export const { wagmiConfig, ready: walletReady } = build();
