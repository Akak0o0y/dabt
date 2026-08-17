import { describe, expect, it } from "vitest";
import { buildClassificationComparison } from "../client/src/lib/classificationCompare";

describe("classification comparison", () => {
  it("distinguishes inferred policy evidence from a reviewer-approved level without calling either authoritative", () => {
    const comparison = buildClassificationComparison({ inferredClassification: "Secret", confidenceLevel: "inferred", requiresLegalReview: true, reviewerDisposition: "approved", approvedClassification: "Confidential" });
    expect(comparison.status).toBe("changed");
    expect(comparison.inferred.label).toContain("INFERRED");
    expect(comparison.approved.label).toContain("REVIEWER-APPROVED");
    expect(comparison.caveat).toContain("not authoritative");
  });

  it("shows a pending reviewer comparison when no approval record exists", () => {
    expect(buildClassificationComparison({ inferredClassification: "Secret", confidenceLevel: "inferred", requiresLegalReview: true, reviewerDisposition: null, approvedClassification: null }).status).toBe("pending");
  });
});
