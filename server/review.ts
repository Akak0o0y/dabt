import { createHash, randomUUID } from "crypto";
import { and, eq } from "drizzle-orm";
import { auditEvidenceReviews, auditEvidenceSnapshots, type InsertAuditEvidenceReview } from "../drizzle/schema";
import { getDb } from "./db";

export type ReviewDisposition = "approved" | "rejected";

type BuildEvidenceReviewInput = {
  reviewId: string;
  evidenceSnapshotId: string;
  evidenceIntegrityHash: string;
  reviewerUserId: number;
  disposition: ReviewDisposition;
  rationaleEn: string;
  rationaleAr: string;
  createdAt: Date;
};

function sha256(value: string): string {
  return createHash("sha256").update(value, "utf8").digest("hex");
}

/** Builds a tamper-evident reviewer decision without copying any source or release payload. */
export function buildEvidenceReview(input: BuildEvidenceReviewInput): InsertAuditEvidenceReview {
  const integrityHash = sha256(JSON.stringify({
    reviewId: input.reviewId,
    evidenceSnapshotId: input.evidenceSnapshotId,
    evidenceIntegrityHash: input.evidenceIntegrityHash,
    reviewerUserId: input.reviewerUserId,
    disposition: input.disposition,
    rationaleEn: input.rationaleEn,
    rationaleAr: input.rationaleAr,
    createdAt: input.createdAt.toISOString(),
  }));
  return {
    id: input.reviewId,
    evidenceSnapshotId: input.evidenceSnapshotId,
    evidenceIntegrityHash: input.evidenceIntegrityHash,
    reviewerUserId: input.reviewerUserId,
    disposition: input.disposition,
    rationaleEn: input.rationaleEn,
    rationaleAr: input.rationaleAr,
    integrityHash,
    createdAt: input.createdAt,
  };
}

export async function approveAuditEvidence(input: Omit<BuildEvidenceReviewInput, "reviewId" | "evidenceIntegrityHash" | "createdAt">) {
  const db = await getDb();
  if (!db) throw new Error("Reviewer approval is unavailable because the database is not connected.");
  const snapshots = await db.select().from(auditEvidenceSnapshots).where(eq(auditEvidenceSnapshots.id, input.evidenceSnapshotId)).limit(1);
  const snapshot = snapshots[0];
  if (!snapshot) throw new Error("Evidence snapshot was not found.");
  if (snapshot.decision !== "REVIEW") throw new Error("Only REVIEW decisions may receive reviewer approval.");
  const existing = await db.select().from(auditEvidenceReviews).where(eq(auditEvidenceReviews.evidenceSnapshotId, snapshot.id)).limit(1);
  if (existing[0]) throw new Error("This REVIEW snapshot already has an immutable reviewer decision.");
  const review = buildEvidenceReview({
    ...input,
    reviewId: `review_${randomUUID()}`,
    evidenceIntegrityHash: snapshot.integrityHash,
    createdAt: new Date(),
  });
  await db.insert(auditEvidenceReviews).values(review);
  return review;
}

export async function getEvidenceReview(ownerUserId: number, evidenceSnapshotId: string) {
  const db = await getDb();
  if (!db) throw new Error("Reviewer approval is unavailable because the database is not connected.");
  const records = await db
    .select({ review: auditEvidenceReviews })
    .from(auditEvidenceReviews)
    .innerJoin(auditEvidenceSnapshots, eq(auditEvidenceReviews.evidenceSnapshotId, auditEvidenceSnapshots.id))
    .where(and(eq(auditEvidenceSnapshots.userId, ownerUserId), eq(auditEvidenceReviews.evidenceSnapshotId, evidenceSnapshotId)))
    .limit(1);
  return records[0]?.review ?? null;
}
