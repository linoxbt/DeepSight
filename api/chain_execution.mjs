export function executionStatus(receipt) {
  const leader = receipt?.consensus_data?.leader_receipt?.[0];
  const raw = String(receipt?.txExecutionResultName || receipt?.execution || leader?.execution_result || "").toUpperCase();
  if (["SUCCESS", "RETURN", "FINISHED_WITH_RETURN"].includes(raw)) return "SUCCESS";
  if (raw.includes("ERROR") || raw.includes("REVERT")) return "FAILED";
  return "UNKNOWN";
}
