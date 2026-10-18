import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { resolve } from "node:path";
import { homedir } from "node:os";
import { createAccount, createClient } from "genlayer-js";
import { studionet } from "genlayer-js/chains";
import { Wallet } from "ethers";

const root = resolve(fileURLToPath(new URL("..", import.meta.url)));
const origin = process.env.DEEPSIGHT_ORIGIN || "https://deepsight-evidence.netlify.app";
const keystore = process.env.DEEPSIGHT_KEYSTORE || resolve(homedir(), ".genlayer/keystores/deepsight-studio.json");
const passwordFile = process.env.DEEPSIGHT_PASSWORD_FILE || resolve(root, "data/genlayer.password");
const recordPath = resolve(root, process.env.DEEPSIGHT_DEPLOYMENT_RECORD || "deployments/studionet-v4.json");

if (!origin.startsWith("https://") || /\/.+\//.test(origin.slice(8))) {
  throw new Error("DEEPSIGHT_ORIGIN must be a bare HTTPS origin");
}
const wallet = await Wallet.fromEncryptedJson(readFileSync(keystore, "utf8"), readFileSync(passwordFile, "utf8").trim());
const account = createAccount(wallet.privateKey);
const client = createClient({ chain: studionet, account });
const code = readFileSync(resolve(root, "contracts/proof_of_discovery.py"), "utf8");
const previous = (() => { try { return JSON.parse(readFileSync(recordPath, "utf8")); } catch { return null; } })();
if (previous?.tx_hash && !process.env.DEEPSIGHT_FORCE_REDEPLOY) {
  throw new Error(`Deployment transaction already recorded: ${previous.tx_hash}. Reconcile it before retrying.`);
}
const hash = await client.deployContract({ code, args: [origin] });
mkdirSync(resolve(root, "deployments"), { recursive: true });
writeFileSync(recordPath, JSON.stringify({ network: "studionet", chain_id: 61999, origin, account: account.address, tx_hash: hash, recorded_at: new Date().toISOString() }, null, 2) + "\n", { mode: 0o600 });
process.stdout.write(JSON.stringify({ tx_hash: hash, network: "studionet", account: account.address, origin, record: recordPath }) + "\n");
