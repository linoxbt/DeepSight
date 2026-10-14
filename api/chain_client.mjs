import { readFileSync } from "node:fs";
import { createAccount, createClient } from "/usr/local/lib/node_modules/genlayer/node_modules/genlayer-js/dist/index.js";
import { studionet } from "/usr/local/lib/node_modules/genlayer/node_modules/genlayer-js/dist/chains/index.js";
import { Wallet } from "/usr/local/lib/node_modules/genlayer/node_modules/ethers/lib.esm/ethers.js";

const input = JSON.parse(readFileSync(0, "utf8"));

function emit(payload) {
  process.stdout.write(`${JSON.stringify(payload)}\n`);
}

try {
  const wallet = await Wallet.fromEncryptedJson(readFileSync(input.keystore, "utf8"), input.password);
  const account = createAccount(wallet.privateKey);
  const client = createClient({ chain: studionet, account });
  await client.initializeConsensusSmartContract();
  // Gas estimation is a separate StudioNet write. The daily cap is already full,
  // so a deploy uses the fixed fallback and spends one send instead of two.
  client.estimateTransactionGas = async () => 200000n;
  if (input.action === "deploy") {
    const hash = await client.deployContract({ code: readFileSync(input.code_path, "utf8"), args: [] });
    const receipt = await client.waitForTransactionReceipt({ hash, status: "ACCEPTED", retries: 80, interval: 5000 });
    emit(summarize(hash, receipt));
  } else if (input.action === "write") {
    const hash = await client.writeContract({
      address: input.address,
      functionName: input.method,
      args: input.args,
      value: 0n,
    });
    const receipt = await client.waitForTransactionReceipt({ hash, status: "ACCEPTED", retries: 80, interval: 5000 });
    emit(summarize(hash, receipt));
  } else if (input.action === "read") {
    const result = await client.readContract({
      address: input.address,
      functionName: input.method,
      args: input.args,
    });
    emit({ ok: true, result: stringify(result) });
  } else if (input.action === "appeal") {
    const result = await client.appealTransaction({ txId: input.tx_hash });
    emit({ ok: true, result: stringify(result) });
  } else {
    emit({ ok: false, error: "Unknown chain action" });
    process.exit(1);
  }
} catch (error) {
  emit({ ok: false, error: error instanceof Error ? error.message : String(error) });
  process.exit(1);
}

function summarize(hash, receipt) {
  const leader = firstLeader(receipt);
  const execution =
    receipt?.txExecutionResultName ||
    receipt?.execution ||
    leader?.execution_result ||
    "";
  const failed = String(execution).includes("ERROR");
  const detail = failed ? errorText(leader) : "";
  return {
    ok: !failed,
    hash,
    status: receipt?.statusName || receipt?.status_name || String(receipt?.status || ""),
    execution: String(execution),
    contract_address:
      receipt?.data?.contract_address ||
      receipt?.txDataDecoded?.contractAddress ||
      receipt?.contractAddress ||
      "",
    receipt: stringify(receipt),
    error: detail,
  };
}

function firstLeader(receipt) {
  const rows = receipt?.consensus_data?.leader_receipt;
  if (Array.isArray(rows) && rows.length > 0) return rows[0];
  return null;
}

function errorText(leader) {
  const result = leader?.result ?? leader?.genvm_result ?? "";
  if (typeof result === "string" && result.trim()) return result.slice(0, 800);
  if (result && typeof result === "object") {
    const text = JSON.stringify(result);
    if (text && text !== "{}") return text.slice(0, 800);
  }
  return "Contract execution finished with an error";
}

function stringify(value) {
  return JSON.parse(JSON.stringify(value, (_key, item) => (typeof item === "bigint" ? item.toString() : item)));
}
