import { BadgeCheck, ScanLine, TriangleAlert } from "lucide-react";

type ConfidenceLevel = "verified" | "inferred" | "needs_verification" | string;

export function ConfidenceFlag({ level }: { level: ConfidenceLevel }) {
  const normalized = level.toLowerCase();
  if (normalized === "verified") {
    return (
      <span className="confidence-flag confidence-verified">
        <BadgeCheck size={12} /> VERIFIED
      </span>
    );
  }
  if (normalized === "needs_verification") {
    return (
      <span className="confidence-flag confidence-review">
        <TriangleAlert size={12} /> NEEDS VERIFICATION
      </span>
    );
  }
  return (
    <span className="confidence-flag confidence-inferred">
      <ScanLine size={12} /> INFERRED
    </span>
  );
}
