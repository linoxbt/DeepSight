import { readFileSync, writeFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { fileURLToPath } from "node:url";
import { resolve } from "node:path";
import { createClient } from "genlayer-js";
import { studionet } from "genlayer-js/chains";

const root = resolve(fileURLToPath(new URL("..", import.meta.url)));
const recordPath = resolve(root, process.env.DEEPSIGHT_DEPLOYMENT_RECORD || "deployments/studionet-v4.json");
const record = JSON.parse(readFileSync(recordPath, "utf8"));
const client = createClient({ chain: studionet });
const tx = await client.getTransaction({ hash: record.tx_hash });
const result = {
  hash: record.tx_hash,
  status: tx.statusName ?? tx.status,
  execution: tx.txExecutionResultName ?? tx.txExecutionResult,
  result: tx.resultName ?? tx.result,
  contract_address: tx.txDataDecoded?.contractAddress ?? tx.to_address ?? null,
  final: tx.consensus_data?.final ?? false,
  error: tx.consensus_data?.leader_receipt?.[0]?.error ?? null,
  receipt_hash: tx.txReceipt ?? null,
  decoded_type: tx.txDataDecoded?.type ?? null,
};
if (result.status === "FINALIZED" && result.contract_address) {
  const code = await client.getContractCode(result.contract_address);
  result.code_present = Boolean(code);
  if (result.code_present) {
    const source = readFileSync(resolve(root, "contracts/proof_of_discovery.py"), "utf8");
    result.source_sha256 = createHash("sha256").update(source).digest("hex");
    result.deployed_code_sha256 = createHash("sha256").update(code).digest("hex");
    result.code_matches_source = code === source;
    try {
      const ids = await client.readContract({ address: result.contract_address, functionName: "list_claim_ids", args: [] });
      result.readable = Array.isArray(ids);
      result.claim_count = Array.isArray(ids) ? ids.length : null;
    } catch (error) {
      result.read_error = error instanceof Error ? error.message.slice(0, 300) : String(error);
    }
    if (result.code_matches_source && result.readable) {
      record.contract_address = result.contract_address;
      // Verification time is not transaction finality time. Preserve the
      // original finality observation in the deployment record.
      record.checked_at = new Date().toISOString();
      record.finalized_execution = "SUCCESS";
      record.code_matches_source = true;
      record.source_sha256 = result.source_sha256;
      record.deployed_code_sha256 = result.deployed_code_sha256;
      record.read_method_check = "passed";
      writeFileSync(recordPath, JSON.stringify(record, null, 2) + "\n", { mode: 0o600 });
    }
  }
}
if (result.status !== "FINALIZED" || !result.contract_address || !result.code_matches_source || result.readable !== true ||
    (record.contract_address && record.contract_address.toLowerCase() !== result.contract_address.toLowerCase())) {
  process.exitCode = 1;
}
process.stdout.write(JSON.stringify(result) + "\n");
