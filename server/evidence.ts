import { createHash, randomUUID } from "crypto";
import { and, desc, eq } from "drizzle-orm";
import { auditEvidenceSnapshots, type InsertAuditEvidenceSnapshot } from "../drizzle/schema";
import { getDb } from "./db";

export type DabtEvaluationEvidence = {
  decision: string;
  decision_rule_id: string | null;
  classification: string;
  policy_map_version?: string;
  classification_evidence: Record<string, unknown>;
  audit: Record<string, unknown>;
  legal_review_disclaimer_en: string;
  legal_review_disclaimer_ar: string;
};

type BuildEvidenceSnapshotInput = {
  snapshotId: string;
  userId: number;
  document: string;
  evaluation: DabtEvaluationEvidence;
  createdAt: Date;
};

function canonicalize(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(canonicalize);
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>)
        .sort(([left], [right]) => left.localeCompare(right))
        .map(([key, nested]) => [key, canonicalize(nested)]),
    );
  }
  return value;
}

function sha256(value: string): string {
  return createHash("sha256").update(value, "utf8").digest("hex");
}

function canonicalJson(value: unknown): string {
  return JSON.stringify(canonicalize(value));
}

/**
 * Builds a durable, tamper-evident snapshot without retaining the source or release payload.
 */
export function buildEvidenceSnapshot(input: BuildEvidenceSnapshotInput): InsertAuditEvidenceSnapshot {
  const classificationEvidenceJson = canonicalJson(input.evaluation.classification_evidence);
  const auditJson = canonicalJson(input.evaluation.audit);
  const sourceDocumentHash = sha256(input.document);
  const integrityHash = sha256(
    canonicalJson({
      snapshotId: input.snapshotId,
      userId: input.userId,
      sourceDocumentHash,
      decision: input.evaluation.decision,
      decisionRuleId: input.evaluation.decision_rule_id,
      classification: input.evaluation.classification,
      policyMapVersion: input.evaluation.policy_map_version ?? "unknown",
      classificationEvidenceJson,
      auditJson,
      createdAt: input.createdAt.toISOString(),
    }),
  );
  return {
    id: input.snapshotId,
    userId: input.userId,
    sourceDocumentHash,
    integrityHash,
    decision: input.evaluation.decision,
    decisionRuleId: input.evaluation.decision_rule_id,
    classification: input.evaluation.classification,
    policyMapVersion: input.evaluation.policy_map_version ?? "unknown",
    classificationEvidenceJson,
    auditJson,
    legalReviewDisclaimerEn: input.evaluation.legal_review_disclaimer_en,
    legalReviewDisclaimerAr: input.evaluation.legal_review_disclaimer_ar,
    createdAt: input.createdAt,
  };
}

export async function persistAuditEvidence(userId: number, document: string, evaluation: DabtEvaluationEvidence) {
  const db = await getDb();
  if (!db) throw new Error("Evidence persistence is unavailable because the database is not connected.");
  const snapshot = buildEvidenceSnapshot({
    snapshotId: `evidence_${randomUUID()}`,
    userId,
    document,
    evaluation,
    createdAt: new Date(),
  });
  await db.insert(auditEvidenceSnapshots).values(snapshot);
  return snapshot;
}

export async function listAuditEvidence(userId: number, limit = 20) {
  const db = await getDb();
  if (!db) throw new Error("Evidence persistence is unavailable because the database is not connected.");
  return db
    .select()
    .from(auditEvidenceSnapshots)
    .where(eq(auditEvidenceSnapshots.userId, userId))
    .orderBy(desc(auditEvidenceSnapshots.createdAt))
    .limit(limit);
}

export async function getAuditEvidence(userId: number, snapshotId: string) {
  const db = await getDb();
  if (!db) throw new Error("Evidence persistence is unavailable because the database is not connected.");
  const records = await db
    .select()
    .from(auditEvidenceSnapshots)
    .where(and(eq(auditEvidenceSnapshots.userId, userId), eq(auditEvidenceSnapshots.id, snapshotId)))
    .limit(1);
  return records[0] ?? null;
}
