import assert from "node:assert/strict";
import test from "node:test";
import { executionStatus } from "../chain_execution.mjs";

test("GenLayer finalized success and failure names are normalized", () => {
  assert.equal(executionStatus({ txExecutionResultName: "FINISHED_WITH_RETURN" }), "SUCCESS");
  assert.equal(executionStatus({ txExecutionResultName: "FINISHED_WITH_ERROR" }), "FAILED");
  assert.equal(executionStatus({ txExecutionResultName: "NOT_VOTED" }), "UNKNOWN");
  assert.equal(executionStatus({ consensus_data: { leader_receipt: [{ execution_result: "FINISHED_WITH_RETURN" }] } }), "SUCCESS");
});
