export type ReleaseDecision = "ALLOW" | "ALLOW_WITH_REDACTION" | "DENY" | "REVIEW" | string;

export type ReleaseState = {
  kind: "payload" | "blocked" | "awaiting_review";
  label: string;
  renderPayload: boolean;
};

export function getReleaseState(decision: ReleaseDecision, _payload: string): ReleaseState {
  if (decision === "DENY") {
    return {
      kind: "blocked",
      label: "BLOCKED — no payload released under this decision",
      renderPayload: false,
    };
  }
  if (decision === "REVIEW") {
    return {
      kind: "awaiting_review",
      label: "AWAITING HUMAN REVIEW — no payload released",
      renderPayload: false,
    };
  }
  return { kind: "payload", label: "RELEASE PAYLOAD", renderPayload: true };
}
