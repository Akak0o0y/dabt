import { afterAll, describe, expect, it, vi } from "vitest";
import { callDabtApi, evaluateDabt, shutdownDabtServiceForTests } from "./dabt";

describe("Dabt FastAPI proxy", () => {
  afterAll(() => {
    shutdownDabtServiceForTests();
  });

  it("forwards a retrieval payload and preserves the legal-review caveat", async () => {
    const mockFetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          decision: "ALLOW_WITH_REDACTION",
          legal_review_disclaimer_en: "Legal review required.",
          legal_review_disclaimer_ar: "مراجعة قانونية مطلوبة.",
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );

    const result = await callDabtApi(
      "/v1/retrieval/evaluate",
      "POST",
      { document: "National ID 1000000008", cross_border: true },
      mockFetch,
    );

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/v1/retrieval/evaluate"),
      expect.objectContaining({ method: "POST" }),
    );
    expect(result.legal_review_disclaimer_en).toBe("Legal review required.");
    expect(result.legal_review_disclaimer_ar).toBe("مراجعة قانونية مطلوبة.");
  });

  it("surfaces a non-2xx FastAPI result without dropping its caveat", async () => {
    const mockFetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          detail_en: "not implemented",
          legal_review_disclaimer_en: "Legal review required.",
          legal_review_disclaimer_ar: "مراجعة قانونية مطلوبة.",
        }),
        { status: 501, headers: { "Content-Type": "application/json" } },
      ),
    );

    await expect(callDabtApi("/v1/action/evaluate", "POST", { action: "send" }, mockFetch)).rejects.toMatchObject({
      message: "not implemented",
      payload: expect.objectContaining({ legal_review_disclaimer_en: "Legal review required." }),
    });
  });

  it("starts the FastAPI service and reaches it through the bridge", async () => {
    const result = await evaluateDabt({ document: "National ID 1000000008", crossBorder: true });
    expect(result.decision).toBe("ALLOW_WITH_REDACTION");
    expect(result.legal_review_disclaimer_en).toBeTruthy();
  });
});
