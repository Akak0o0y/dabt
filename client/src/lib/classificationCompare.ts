export type ClassificationComparisonInput = {
  inferredClassification: string;
  confidenceLevel: string;
  requiresLegalReview: boolean;
  reviewerDisposition: "approved" | "rejected" | null;
  approvedClassification: string | null;
};

export function buildClassificationComparison(input: ClassificationComparisonInput) {
  const approved = input.reviewerDisposition === "approved" && input.approvedClassification;
  return {
    status: approved ? (approved === input.inferredClassification ? "confirmed" : "changed") : "pending",
    inferred: { label: `INFERRED POLICY CLASSIFICATION · ${input.confidenceLevel.toUpperCase()}`, value: input.inferredClassification },
    approved: approved
      ? { label: "QUALIFIED REVIEWER-APPROVED CLASSIFICATION", value: input.approvedClassification }
      : { label: "QUALIFIED REVIEWER-APPROVED CLASSIFICATION", value: "PENDING REVIEW" },
    caveat: input.requiresLegalReview
      ? "Both values are not authoritative; they remain engineering evidence requiring qualified legal or compliance review before regulatory reliance."
      : "This comparison is not authoritative engineering evidence.",
  };
}
