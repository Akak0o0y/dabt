import { describe, expect, it } from "vitest";
import { buildEvidenceSnapshot } from "./evidence";

const evaluation = {
  decision: "DENY",
  decision_rule_id: "PDPL-ART6-4-SENSITIVE-LEGITIMATE-INTEREST",
  classification: "Secret",
  policy_map_version: "0.1.0",
  classification_evidence: {
    mapping_key: "sensitive_data.health",
    confidence_level: "inferred",
    requires_legal_review: true,
    rationale_en: "Conservative inference pending review.",
    rationale_ar: "استنتاج تحفظي لحين المراجعة.",
    citation: { article: "NDMO Principle 2", quote: "Impact based.", source_url: "https://example.test" },
  },
  audit: { decision_rule_id: "PDPL-ART6-4-SENSITIVE-LEGITIMATE-INTEREST", fired_rules: [] },
  legal_review_disclaimer_en: "Qualified legal review required.",
  legal_review_disclaimer_ar: "تتطلب مراجعة قانونية مؤهلة.",
};

describe("audit evidence snapshot", () => {
  it("retains the decision evidence but never stores the submitted source payload", () => {
    const snapshot = buildEvidenceSnapshot({
      snapshotId: "evidence_0001",
      userId: 42,
      document: "Saudi National ID 1000000008 and a medical diagnosis",
      evaluation,
      createdAt: new Date("2026-08-17T12:00:00.000Z"),
    });

    expect(snapshot.id).toBe("evidence_0001");
    expect(snapshot.sourceDocumentHash).toMatch(/^[a-f0-9]{64}$/);
    expect(JSON.stringify(snapshot)).not.toContain("1000000008");
    expect(JSON.stringify(snapshot)).not.toContain("medical diagnosis");
    expect(snapshot.decision).toBe("DENY");
    expect(snapshot.policyMapVersion).toBe("0.1.0");
    expect(snapshot.classificationEvidenceJson).toContain("sensitive_data.health");
    expect(snapshot.auditJson).toContain("PDPL-ART6-4-SENSITIVE-LEGITIMATE-INTEREST");
  });

  it("produces a stable integrity hash for the same evidence inputs", () => {
    const input = {
      snapshotId: "evidence_0002",
      userId: 42,
      document: "confidential source",
      evaluation,
      createdAt: new Date("2026-08-17T12:00:00.000Z"),
    };
    expect(buildEvidenceSnapshot(input).integrityHash).toBe(buildEvidenceSnapshot(input).integrityHash);
  });
});
