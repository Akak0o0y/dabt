import { Check, Eye, ShieldAlert, ShieldCheck } from "lucide-react";

type Decision = "ALLOW" | "ALLOW_WITH_REDACTION" | "DENY" | "REVIEW" | string;

const decisionMeta: Record<string, { label: string; arabic: string; icon: typeof Check }> = {
  ALLOW: { label: "ALLOW", arabic: "مسموح", icon: Check },
  ALLOW_WITH_REDACTION: { label: "ALLOW WITH REDACTION", arabic: "مسموح بعد الحجب", icon: ShieldCheck },
  DENY: { label: "DENY", arabic: "مرفوض", icon: ShieldAlert },
  REVIEW: { label: "REVIEW", arabic: "مراجعة مطلوبة", icon: Eye },
};

export function DecisionBadge({ decision }: { decision: Decision }) {
  const meta = decisionMeta[decision] ?? decisionMeta.REVIEW;
  const Icon = meta.icon;
  return (
    <div className={`decision-badge decision-${decision.toLowerCase().replaceAll("_", "-")}`}>
      <Icon size={17} strokeWidth={2.4} />
      <span>{meta.label}</span>
      <span className="decision-ar" dir="rtl">{meta.arabic}</span>
    </div>
  );
}
