import { describe, expect, it } from "vitest";
import { parseApiError } from "./client";

describe("parseApiError", () => {
  it("returns a safe fallback for unknown errors", () => {
    expect(parseApiError(new Error("network"))).toEqual({
      code: "request_failed",
      message: "İstek tamamlanamadı.",
    });
  });
});
