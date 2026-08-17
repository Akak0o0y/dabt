import { useMemo, useState } from "react";
import { Braces, Copy, FileText, Globe2, Layers3, Play, RotateCcw, ShieldCheck, TriangleAlert } from "lucide-react";
import { AuditLog, type DabtAudit } from "@/components/AuditLog";
import { DecisionBadge } from "@/components/DecisionBadge";
import { FindingsPanel, type DabtFinding } from "@/components/FindingsPanel";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { trpc } from "@/lib/trpc";

type DabtResult = {
  decision: string;
  decision_rule_id: string | null;
  classification: string;
  findings: DabtFinding[];
  redacted_document: string;
  audit: DabtAudit;
  legal_review_disclaimer_en: string;
  legal_review_disclaimer_ar: string;
};

const SAMPLE_DOCUMENT = `Customer onboarding note — SYNTHETIC DEMO DATA ONLY

Applicant National ID: 1000000008
Contact: +966501234567
Settlement account: SA03 8000 0000 6080 1016 7519

The customer record includes a medical diagnosis from a partner clinic. Send the submitted information to the overseas AI analyst for document summarisation.`;

const classificationStyle: Record<string, string> = {
  Public: "classification-public",
  Confidential: "classification-confidential",
  Secret: "classification-secret",
  "Top Secret": "classification-top-secret",
};

export default function Home() {
  const [document, setDocument] = useState(SAMPLE_DOCUMENT);
  const [crossBorder, setCrossBorder] = useState(true);
  const [lawfulBasis, setLawfulBasis] = useState("legitimate_interest");
  const [result, setResult] = useState<DabtResult | null>(null);
  const [copied, setCopied] = useState(false);

  const evaluate = trpc.dabt.evaluate.useMutation({
    onSuccess: data => setResult(data as DabtResult),
  });

  const outcomeHint = useMemo(() => {
    if (!result) return "Run the gate to produce a traceable retrieval decision.";
    return result.decision === "ALLOW_WITH_REDACTION"
      ? "Payload transformed before transfer."
      : result.decision === "DENY"
        ? "The submitted operation is prohibited under the selected basis."
        : result.decision === "REVIEW"
          ? "Human escalation is required before release."
          : "The requested retrieval may proceed within the presented scope.";
  }, [result]);

  const runEvaluation = () => {
    evaluate.mutate({ document, crossBorder, lawfulBasis, sector: "development", eventType: "disclosure" });
  };

  const reset = () => {
    setDocument(SAMPLE_DOCUMENT);
    setCrossBorder(true);
    setLawfulBasis("legitimate_interest");
    setResult(null);
  };

  const copyRedacted = async () => {
    if (!result) return;
    await navigator.clipboard.writeText(result.redacted_document);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1500);
  };

  return (
    <main className="blueprint-shell">
      <div className="blueprint-grid" aria-hidden="true" />
      <header className="app-header">
        <a className="brand-lockup" href="#top" aria-label="Dabt Core home">
          <span className="brand-mark">D</span>
          <span>
            <strong>DABT</strong>
            <small>CORE / ضبط</small>
          </span>
        </a>
        <div className="header-spec">
          <span>DATA RETRIEVAL GATE</span>
          <span className="status-dot">LIVE REFERENCE BUILD</span>
        </div>
      </header>

      <section className="hero-frame" id="top">
        <div className="measure-line measure-top"><span>01</span><i /><span>REGULATORY ENFORCEMENT / KSA</span></div>
        <div className="hero-copy">
          <p className="eyebrow">SAUDI DATA PRIVACY SYSTEM / V0.1</p>
          <h1>Control the payload<br /><em>before it crosses the line.</em></h1>
          <p className="hero-description">A policy enforcement point for AI retrieval. Detect Saudi identifiers, classify against NDMO, apply PDPL logic, redact where required, and preserve a bilingual audit trail.</p>
        </div>
        <div className="hero-geometry" aria-hidden="true">
          <span className="dimension dimension-a">1200</span><span className="dimension dimension-b">∟ 90°</span>
          <div className="geometry-core"><span /><span /><span /></div>
        </div>
        <div className="hero-controls">
          <span><ShieldCheck size={16} /> PDPL</span><span><Layers3 size={16} /> NCA ECC-2:2024</span><span><Braces size={16} /> SAMA CSF</span>
        </div>
      </section>

      <section className="workbench">
        <section className="blueprint-panel input-panel">
          <div className="panel-heading">
            <div><p className="eyebrow">01 / INPUT PLANE</p><h2>Document payload</h2></div>
            <FileText size={19} />
          </div>
          <label htmlFor="payload" className="input-label">PASTE RETRIEVAL CONTENT <span>SYNTHETIC DEMO DATA ONLY</span></label>
          <textarea id="payload" value={document} onChange={event => setDocument(event.target.value)} spellCheck={false} />
          <div className="input-parameters">
            <div className="toggle-row">
              <div><Globe2 size={16} /><span>Cross-border LLM transfer</span><small>Art. 29 minimisation path</small></div>
              <Switch checked={crossBorder} onCheckedChange={setCrossBorder} aria-label="Cross-border transfer" />
            </div>
            <label className="select-row">
              <span>DECLARED LAWFUL BASIS</span>
              <select value={lawfulBasis} onChange={event => setLawfulBasis(event.target.value)}>
                <option value="legitimate_interest">Legitimate interest</option>
                <option value="consent">Consent</option>
                <option value="legal_obligation">Legal obligation</option>
              </select>
            </label>
          </div>
          <div className="input-actions">
            <Button className="evaluate-button" onClick={runEvaluation} disabled={evaluate.isPending || !document.trim()}>
              <Play size={15} fill="currentColor" /> {evaluate.isPending ? "EVALUATING…" : "RUN RETRIEVAL GATE"}
            </Button>
            <Button variant="ghost" className="reset-button" onClick={reset}><RotateCcw size={15} /> RESET</Button>
          </div>
          {evaluate.error ? <div className="error-plane"><TriangleAlert size={16} />{evaluate.error.message}</div> : null}
        </section>

        <section className="outcome-panel">
          <div className="outcome-crosshair" aria-hidden="true"><span /><span /></div>
          <p className="eyebrow">GATE OUTCOME / LIVE</p>
          {result ? <DecisionBadge decision={result.decision} /> : <div className="decision-placeholder">AWAITING EVALUATION</div>}
          <p className="outcome-hint">{outcomeHint}</p>
          <div className="classification-block">
            <span>NDMO CLASSIFICATION</span>
            <strong className={result ? classificationStyle[result.classification] : "classification-empty"}>{result?.classification ?? "—"}</strong>
          </div>
          <div className="outcome-dimensions"><span>POLICY MAP</span><i /><span>{result?.audit.decision_rule_id ?? "NO DECISION"}</span></div>
        </section>
      </section>

      <section className="results-layout">
        <FindingsPanel findings={result?.findings ?? []} />
        <section className="blueprint-panel redaction-panel">
          <div className="panel-heading">
            <div><p className="eyebrow">03 / TRANSFORMED OUTPUT</p><h2>Release payload</h2></div>
            {result ? <button className="copy-button" onClick={copyRedacted}><Copy size={15} /> {copied ? "COPIED" : "COPY"}</button> : null}
          </div>
          <div className="redacted-document">{result?.redacted_document ?? "Evaluated content will appear here after the gate resolves its obligations."}</div>
          <div className="redaction-note"><span>▣</span> Redaction is an Article 15(5) and Article 29(2)(c) compliance path — not an authority determination.</div>
        </section>
      </section>

      {result ? <AuditLog audit={result.audit} /> : <section className="blueprint-panel audit-panel empty-audit"><p className="eyebrow">04 / EVIDENCE REGISTER</p><h2>Awaiting a policy decision</h2><p>The bilingual record will expose every fired rule, subdomain mapping, confidence status, and the mandatory legal-review caveat.</p></section>}

      <footer className="app-footer">
        <span>RESEARCH-GROUNDED COMPLIANCE MAP</span><i /><span>ALL MAPPINGS REQUIRE QUALIFIED LEGAL REVIEW</span><span lang="ar" dir="rtl">كل التعيينات تتطلب مراجعة قانونية مؤهلة</span>
      </footer>
    </main>
  );
}
