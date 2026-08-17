import { index, int, mysqlEnum, mysqlTable, text, timestamp, varchar } from "drizzle-orm/mysql-core";

/**
 * Core user table backing auth flow.
 * Extend this file with additional tables as your product grows.
 * Columns use camelCase to match both database fields and generated types.
 */
export const users = mysqlTable("users", {
  /**
   * Surrogate primary key. Auto-incremented numeric value managed by the database.
   * Use this for relations between tables.
   */
  id: int("id").autoincrement().primaryKey(),
  /** Manus OAuth identifier (openId) returned from the OAuth callback. Unique per user. */
  openId: varchar("openId", { length: 64 }).notNull().unique(),
  name: text("name"),
  email: varchar("email", { length: 320 }),
  loginMethod: varchar("loginMethod", { length: 64 }),
  role: mysqlEnum("role", ["user", "admin"]).default("user").notNull(),
  createdAt: timestamp("createdAt").defaultNow().notNull(),
  updatedAt: timestamp("updatedAt").defaultNow().onUpdateNow().notNull(),
  lastSignedIn: timestamp("lastSignedIn").defaultNow().notNull(),
});

export type User = typeof users.$inferSelect;
export type InsertUser = typeof users.$inferInsert;

/**
 * Immutable, privacy-minimised evidence of a policy decision.
 * The source document and release payload are never stored; only their hash and
 * the decision evidence required for audit/replay are retained.
 */
export const auditEvidenceSnapshots = mysqlTable(
  "auditEvidenceSnapshots",
  {
    id: varchar("id", { length: 64 }).primaryKey(),
    userId: int("userId").notNull().references(() => users.id),
    sourceDocumentHash: varchar("sourceDocumentHash", { length: 64 }).notNull(),
    integrityHash: varchar("integrityHash", { length: 64 }).notNull(),
    decision: varchar("decision", { length: 32 }).notNull(),
    decisionRuleId: varchar("decisionRuleId", { length: 191 }),
    classification: varchar("classification", { length: 32 }).notNull(),
    policyMapVersion: varchar("policyMapVersion", { length: 64 }).notNull(),
    classificationEvidenceJson: text("classificationEvidenceJson").notNull(),
    auditJson: text("auditJson").notNull(),
    legalReviewDisclaimerEn: text("legalReviewDisclaimerEn").notNull(),
    legalReviewDisclaimerAr: text("legalReviewDisclaimerAr").notNull(),
    createdAt: timestamp("createdAt").defaultNow().notNull(),
  },
  table => [index("auditEvidenceSnapshots_user_created_idx").on(table.userId, table.createdAt)],
);

export type AuditEvidenceSnapshot = typeof auditEvidenceSnapshots.$inferSelect;
export type InsertAuditEvidenceSnapshot = typeof auditEvidenceSnapshots.$inferInsert;
