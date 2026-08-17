import { FileSearch, Scale } from "lucide-react";
import { ConfidenceFlag } from "./ConfidenceFlag";

export type ClassificationEvidence = {
  mapping_key: string | null;
  confidence_level: string;
  requires_legal_review: boolean;
  rationale_en: string;
  rationale_ar: string;
  citation: { article: string; quote: string; source_url: string } | null;
};

export type DabtAudit = {
  decision: string;
  decision_rule_id: string | null;
  timestamp: string;
  summary_en: string;
  summary_ar: string;
  legal_review_disclaimer_en: string;
  legal_review_disclaimer_ar: string;
  fired_rules: Array<{
    id: string;
    framework: string;
    article: string;
    confidence_level: string;
    rationale_en: string;
    rationale_ar: string;
  }>;
  mapped_controls: Array<{
    framework: string;
    control_id: string;
    granularity: string;
    confidence_level: string;
  }>;
};

export function AuditLog({ audit, classificationEvidence }: { audit: DabtAudit; classificationEvidence?: ClassificationEvidence }) {
  return (
    <section className="blueprint-panel audit-panel">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">04 / EVIDENCE REGISTER</p>
          <h2>Bilingual audit transparency</h2>
        </div>
        <FileSearch size={19} />
      </div>
      <div className="audit-summary-grid">
        <p>{audit.summary_en}</p>
        <p lang="ar" dir="rtl">{audit.summary_ar}</p>
      </div>
      {classificationEvidence?.mapping_key ? (
        <div className="classification-evidence-register">
          <div className="audit-rule-meta">
            <span className="rule-id">CLASSIFICATION EVIDENCE · {classificationEvidence.mapping_key}</span>
            <ConfidenceFlag level={classificationEvidence.confidence_level} />
          </div>
          <p className="citation-line">{classificationEvidence.citation?.article ?? "Mapping evidence"}</p>
          <p>{classificationEvidence.rationale_en}</p>
          <p lang="ar" dir="rtl" className="arabic-rationale">{classificationEvidence.rationale_ar}</p>
          {classificationEvidence.citation ? <blockquote>{classificationEvidence.citation.quote}</blockquote> : null}
        </div>
      ) : null}
      <div className="rule-register">
        {audit.fired_rules.map(rule => (
          <article className="audit-rule" key={rule.id}>
            <div className="audit-rule-meta">
              <span className="rule-id">{rule.id}</span>
              <ConfidenceFlag level={rule.confidence_level} />
            </div>
            <p className="citation-line">{rule.framework} · {rule.article}</p>
            <p>{rule.rationale_en}</p>
            <p lang="ar" dir="rtl" className="arabic-rationale">{rule.rationale_ar}</p>
          </article>
        ))}
      </div>
      <div className="mapping-register">
        <div className="mapping-title"><Scale size={15} /> CONTROL MAPPINGS</div>
        {audit.mapped_controls.map((mapped, index) => (
          <div className="mapping-row" key={`${mapped.framework}-${mapped.control_id}-${index}`}>
            <span>{mapped.framework.replaceAll("_", " ")}</span>
            <code>{mapped.control_id}</code>
            <span className="mapping-granularity">{mapped.granularity}</span>
            <ConfidenceFlag level={mapped.confidence_level} />
          </div>
        ))}
      </div>
      <div className="legal-caveat">
        <span>LEGAL REVIEW REQUIRED</span>
        <p>{audit.legal_review_disclaimer_en}</p>
        <p lang="ar" dir="rtl">{audit.legal_review_disclaimer_ar}</p>
      </div>
    </section>
  );
}
