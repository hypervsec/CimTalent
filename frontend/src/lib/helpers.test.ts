import { describe, expect, it } from "vitest";
import { buckets, distribution, parseJsonPayload, renderRequirement } from "./helpers";
describe("frontend helpers", () => {
  it("parses object", () => expect(parseJsonPayload("{}")).toEqual({}));
  it("rejects array", () => expect(() => parseJsonPayload("[]")).toThrow());
  it("rejects invalid json", () => expect(() => parseJsonPayload("{")).toThrow());
  it("renders string requirement", () => expect(renderRequirement("Python")).toBe("Python"));
  it("renders requirement value", () => expect(renderRequirement({ value: "SQL" })).toBe("SQL"));
  it("renders requirement label", () =>
    expect(renderRequirement({ label: "English" })).toBe("English"));
  it("has low bucket", () => expect(buckets([10])[0].value).toBe(1));
  it("has medium bucket", () => expect(buckets([70])[1].value).toBe(1));
  it("has high bucket", () => expect(buckets([90])[2].value).toBe(1));
  it("groups unknown city", () => expect(distribution([null])[0].name).toBe("Belirsiz"));
});
