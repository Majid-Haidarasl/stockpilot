import { describe, expect, it } from "vitest";
import { createIdempotentAction } from "./idempotentAction";

describe("createIdempotentAction", () => {
  it("reuses the same Idempotency-Key on retry and mints a new key for a new action", () => {
    const action = createIdempotentAction("orders.reserve:order-1");

    const first = action.begin(3);
    const retry = action.retry();
    expect(retry.idempotencyKey).toBe(first.idempotencyKey);
    expect(action.buildRequest().headers["Idempotency-Key"]).toBe(first.idempotencyKey);
    expect(action.buildRequest().body.expected_version).toBe(3);

    action.clear();
    const second = action.begin(4);
    expect(second.idempotencyKey).not.toBe(first.idempotencyKey);
    expect(action.buildRequest({ note: "x" }).body).toEqual({
      note: "x",
      expected_version: 4,
    });
  });
});
