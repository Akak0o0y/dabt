import { Fingerprint, Landmark, Smartphone, Stethoscope } from "lucide-react";
import { ConfidenceFlag } from "./ConfidenceFlag";

export type DabtFinding = {
  type: string;
  value: string;
  confidence_tier: "checksum_verified" | "format_detected" | string;
  confidence_level: string;
  checksum_result: boolean | null;
  sensitive_category?: string | null;
};

const labelFor: Record<string, string> = {
  saudi_national_id: "Saudi National ID",
  iqama: "Iqama / Residency ID",
  saudi_iban: "Saudi IBAN",
  saudi_mobile: "Saudi Mobile",
  saudi_commercial_registration: "Commercial Registration",
  sensitive_data: "PDPL Sensitive Data",
};

function FindingIcon({ type }: { type: string }) {
  if (type === "saudi_iban") return <Landmark size={16} />;
  if (type === "saudi_mobile") return <Smartphone size={16} />;
  if (type === "sensitive_data") return <Stethoscope size={16} />;
  return <Fingerprint size={16} />;
}

export function FindingsPanel({ findings }: { findings: DabtFinding[] }) {
  return (
    <section className="blueprint-panel findings-panel">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">02 / DETECTION ARRAY</p>
          <h2>Field findings</h2>
        </div>
        <span className="count-marker">{String(findings.length).padStart(2, "0")}</span>
      </div>
      {!findings.length ? (
        <div className="empty-finding">
          <ScanFrame />
          <p>No regulated identifiers detected in the submitted payload.</p>
        </div>
      ) : (
        <div className="findings-list">
          {findings.map((finding, index) => (
            <article className="finding-row" key={`${finding.type}-${index}-${finding.value}`}>
              <div className="finding-symbol"><FindingIcon type={finding.type} /></div>
              <div className="finding-copy">
                <strong>{labelFor[finding.type] ?? finding.type.replaceAll("_", " ")}</strong>
                <code>{finding.value}</code>
                {finding.sensitive_category ? <span className="finding-category">{finding.sensitive_category}</span> : null}
              </div>
              <div className="finding-assurance">
                {finding.confidence_tier === "checksum_verified" ? (
                  <span className="verification-tier verified-tier">CHECKSUM VERIFIED</span>
                ) : (
                  <span className="verification-tier format-tier">FORMAT DETECTED</span>
                )}
                <ConfidenceFlag level={finding.confidence_level} />
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

function ScanFrame() {
  return <div className="scan-frame"><span /><span /><span /><span /></div>;
}
