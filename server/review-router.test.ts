import { beforeEach, describe, expect, it, vi } from "vitest";
import type { TrpcContext } from "./_core/context";

const approveAuditEvidence = vi.fn();
const getEvidenceReview = vi.fn();

vi.mock("./dabt", () => ({ evaluateDabt: vi.fn(), getDabtComplianceMap: vi.fn() }));
vi.mock("./evidence", () => ({
  persistAuditEvidence: vi.fn(), listAuditEvidence: vi.fn(), getAuditEvidence: vi.fn(),
}));
vi.mock("./review", () => ({ approveAuditEvidence, getEvidenceReview }));

const { appRouter } = await import("./routers");

function adminContext(): TrpcContext {
  return {
    user: { id: 9, openId: "reviewer-admin", name: "Reviewer", email: "reviewer@example.test", loginMethod: "manus", role: "admin", createdAt: new Date(), updatedAt: new Date(), lastSignedIn: new Date() },
    req: {} as TrpcContext["req"], res: {} as TrpcContext["res"],
  };
}

function standardContext(): TrpcContext {
  return { ...adminContext(), user: { ...adminContext().user!, role: "user" } };
}

describe("reviewer approval tRPC procedure", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    approveAuditEvidence.mockResolvedValue({ id: "review_001", disposition: "approved" });
    getEvidenceReview.mockResolvedValue({ id: "review_001", evidenceSnapshotId: "evidence_001", disposition: "approved" });
  });

  it("records an admin's bilingual approval against a REVIEW snapshot", async () => {
    const caller = appRouter.createCaller(adminContext());
    const result = await caller.dabt.reviewEvidence({
      evidenceSnapshotId: "evidence_001",
      disposition: "approved",
      rationaleEn: "The documented minimisation controls and residual risk have been reviewed.",
      rationaleAr: "تمت مراجعة ضوابط تقليل البيانات والمخاطر المتبقية الموثقة.",
    });
    expect(approveAuditEvidence).toHaveBeenCalledWith(expect.objectContaining({ reviewerUserId: 9, evidenceSnapshotId: "evidence_001" }));
    expect(result.disposition).toBe("approved");
  });

  it("forbids non-admin approval attempts", async () => {
    const caller = appRouter.createCaller(standardContext());
    await expect(caller.dabt.reviewEvidence({ evidenceSnapshotId: "evidence_001", disposition: "approved", rationaleEn: "A sufficiently detailed review rationale.", rationaleAr: "سبب مراجعة مفصل وكافٍ لهذا القرار." })).rejects.toMatchObject({ code: "FORBIDDEN" });
  });

  it("retrieves review evidence only through the requesting snapshot owner scope", async () => {
    const caller = appRouter.createCaller(standardContext());
    await caller.dabt.evidenceReviewGet({ evidenceSnapshotId: "evidence_001" });
    expect(getEvidenceReview).toHaveBeenCalledWith(9, "evidence_001");
  });
});
