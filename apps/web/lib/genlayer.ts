export const GENLAYER_STUDIO_EXPLORER = "https://explorer-studio.genlayer.com";
export const PROOF_OF_DISCOVERY_ADDRESS = "0x6B6dC06981Aa6903434dBab601D8b61c5fD57ff8";

export function studioTransactionUrl(hash: string) {
  return `${GENLAYER_STUDIO_EXPLORER}/tx/${encodeURIComponent(hash)}`;
}

export function studioContractUrl(address = PROOF_OF_DISCOVERY_ADDRESS) {
  return `${GENLAYER_STUDIO_EXPLORER}/address/${encodeURIComponent(address)}`;
}
