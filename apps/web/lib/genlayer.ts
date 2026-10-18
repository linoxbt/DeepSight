import deployment from "../../../deployments/studionet-v4.json";

export const GENLAYER_STUDIO_EXPLORER = "https://explorer-studio.genlayer.com";
export const PROOF_OF_DISCOVERY_ADDRESS = deployment.contract_address;

export function studioTransactionUrl(hash: string) {
  return `${GENLAYER_STUDIO_EXPLORER}/tx/${encodeURIComponent(hash)}`;
}

export function studioContractUrl(address = PROOF_OF_DISCOVERY_ADDRESS) {
  return `${GENLAYER_STUDIO_EXPLORER}/address/${encodeURIComponent(address)}`;
}
