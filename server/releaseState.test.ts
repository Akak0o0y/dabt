import { describe, expect, it } from "vitest";
import { getReleaseState } from "../client/src/lib/releaseState";

describe("release state", () => {
  it("never renders source payload for a DENY decision", () => {
    expect(getReleaseState("DENY", "sensitive source content")).toEqual({
      kind: "blocked",
      label: "BLOCKED — no payload released under this decision",
      renderPayload: false,
    });
  });

  it("never renders source payload for a REVIEW decision", () => {
    expect(getReleaseState("REVIEW", "sensitive source content")).toEqual({
      kind: "awaiting_review",
      label: "AWAITING HUMAN REVIEW — no payload released",
      renderPayload: false,
    });
  });

  it("renders an actual payload only for ALLOW outcomes", () => {
    expect(getReleaseState("ALLOW", "approved source content").renderPayload).toBe(true);
    expect(getReleaseState("ALLOW_WITH_REDACTION", "redacted content").renderPayload).toBe(true);
  });
});
