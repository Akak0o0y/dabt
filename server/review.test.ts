import { describe, expect, it } from "vitest";
import { buildEvidenceReview } from "./review";

describe("immutable evidence review", () => {
  it("binds bilingual approval rationale and reviewer identity to the snapshot integrity hash", () => {
    const review = buildEvidenceReview({
      reviewId: "review_001",
      evidenceSnapshotId: "evidence_001",
      evidenceIntegrityHash: "a".repeat(64),
      reviewerUserId: 23,
      disposition: "approved",
      approvedClassification: "Confidential",
      rationaleEn: "The documented minimisation controls and residual risk have been reviewed.",
      rationaleAr: "تمت مراجعة ضوابط تقليل البيانات والمخاطر المتبقية الموثقة.",
      createdAt: new Date("2026-08-17T14:00:00.000Z"),
    });

    expect(review.evidenceSnapshotId).toBe("evidence_001");
    expect(review.reviewerUserId).toBe(23);
    expect(review.approvedClassification).toBe("Confidential");
    expect(review.integrityHash).toMatch(/^[a-f0-9]{64}$/);
    expect(JSON.stringify(review)).not.toContain("source document");
  });

  it("produces a stable integrity hash for the same review evidence", () => {
    const input = {
      reviewId: "review_002",
      evidenceSnapshotId: "evidence_001",
      evidenceIntegrityHash: "b".repeat(64),
      reviewerUserId: 23,
      disposition: "rejected" as const,
      approvedClassification: null,
      rationaleEn: "The lawful basis requires further evidence.",
      rationaleAr: "يتطلب الأساس النظامي مزيداً من الأدلة.",
      createdAt: new Date("2026-08-17T14:00:00.000Z"),
    };
    expect(buildEvidenceReview(input).integrityHash).toBe(buildEvidenceReview(input).integrityHash);
  });
});
