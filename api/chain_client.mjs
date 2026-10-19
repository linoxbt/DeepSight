import { readFileSync } from "node:fs";
import { abi, createAccount, createClient } from "genlayer-js";
import { studionet } from "genlayer-js/chains";
import { Wallet } from "ethers";
import { executionStatus } from "./chain_execution.mjs";

const input = JSON.parse(readFileSync(0, "utf8"));
const emit = (payload) => process.stdout.write(`${JSON.stringify(payload, (_, v) => typeof v === "bigint" ? v.toString() : v)}\n`);
try {
  const needsSigner = input.action === "broadcast";
  let account;
  if (needsSigner) {
    const wallet = await Wallet.fromEncryptedJson(readFileSync(input.keystore, "utf8"), input.password);
    account = createAccount(wallet.privateKey);
  }
  const client = createClient({ chain: studionet, ...(account ? { account } : {}) });
  if (input.action === "broadcast") {
    const hash = await client.writeContract({ address: input.address, functionName: input.method, args: input.args, value: 0n });
    // Persist this hash before waiting for consensus. The worker owns polling.
    emit({ ok: true, hash, status: "SUBMITTED" });
  } else if (input.action === "read") {
    emit({ ok: true, result: await client.readContract({ address: input.address, functionName: input.method, args: input.args }) });
  } else if (input.action === "receipt") {
    const receipt = await client.getTransaction({ hash: input.tx_hash });
    const execution = executionStatus(receipt);
    emit({ ok: true, status: receipt?.statusName || receipt?.status_name || String(receipt?.status || ""),
      execution, rounds: Number(receipt?.numOfRounds ?? 0), result: receipt?.resultName ?? receipt?.result ?? null });
  } else if (input.action === "inspect") {
    const tx = await client.getTransaction({ hash: input.tx_hash });
    const raw = tx?.data?.calldata?.base64;
    const decodedCall = raw ? abi.calldata.decode(Uint8Array.from(Buffer.from(raw, "base64"))) : null;
    const callData = decodedCall instanceof Map ? Object.fromEntries(decodedCall) : decodedCall;
    emit({ ok: true, from: tx?.from_address || tx?.sender || "", to: tx?.to_address || tx?.recipient || "",
      decoded: tx?.txDataDecoded || (callData ? { callData } : null), status: tx?.statusName || "" });
  } else {
    throw new Error("Unsupported chain action");
  }
} catch (error) {
  emit({ ok: false, error: error instanceof Error ? error.message : String(error) });
  process.exitCode = 1;
}
