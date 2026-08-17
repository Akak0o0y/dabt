import { describe, expect, it } from "vitest";
import { buildClassificationComparison } from "./classificationCompare";

describe("classification comparison", () => {
  it("distinguishes an inferred policy level from a qualified reviewer-approved level without calling either authoritative", () => {
    const comparison = buildClassificationComparison({
      inferredClassification: "Secret",
      confidenceLevel: "inferred",
      requiresLegalReview: true,
      reviewerDisposition: "approved",
      approvedClassification: "Confidential",
    });
    expect(comparison.status).toBe("changed");
    expect(comparison.inferred.label).toContain("INFERRED");
    expect(comparison.approved.label).toContain("REVIEWER-APPROVED");
    expect(comparison.caveat).toContain("not authoritative");
  });

  it("shows a pending state when no reviewer decision exists", () => {
    const comparison = buildClassificationComparison({ inferredClassification: "Secret", confidenceLevel: "inferred", requiresLegalReview: true, reviewerDisposition: null, approvedClassification: null });
    expect(comparison.status).toBe("pending");
  });
});
