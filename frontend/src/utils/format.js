export const fmtDate = (s) => (s ? new Date(s).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }) : "—");
export const fmtBytes = (n) => (n < 1024 ? `${n} B` : n < 1048576 ? `${(n / 1024).toFixed(1)} KB` : `${(n / 1048576).toFixed(1)} MB`);

// Risk categories: each has a text label AND an icon name AND a pattern letter, so colour is never the only signal.
export const CATEGORY = {
  LOW: { label: "LOW RISK", short: "Low", tone: "ok", icon: "ShieldCheck" },
  MEDIUM: { label: "MEDIUM RISK", short: "Medium", tone: "warn", icon: "AlertTriangle" },
  HIGH: { label: "HIGH RISK", short: "High", tone: "bad", icon: "ShieldAlert" },
  INSUFFICIENT: { label: "INSUFFICIENT EVIDENCE / MANUAL REVIEW", short: "Insufficient", tone: "sky", icon: "HelpCircle" },
};
export const DOC_TYPES = [
  ["auto", "Auto-detect"], ["invoice", "Invoice / receipt"], ["id_card", "Identity document"],
  ["certificate", "Certificate / marksheet"], ["bank_statement", "Bank statement"], ["general", "General document"],
];
export const typeLabel = (t) => (DOC_TYPES.find(([k]) => k === t) || [null, t || "—"])[1];
export const STAGES = [
  ["queued", "Queued"], ["extracting_text", "Reading text (PDF text / OCR)"], ["extracting_fields", "Extracting fields"],
  ["forensic_analysis", "Forensic checks"], ["duplicate_checks", "Duplicate checks"], ["validation", "Validating rules"],
  ["risk_scoring", "Scoring risk"], ["done", "Complete"],
];
export const ACTION_LABEL = {
  user_registered: "Account created", login: "Signed in", login_failed: "Failed sign-in", document_uploaded: "Document uploaded",
  analysis_started: "Analysis started", analysis_completed: "Analysis completed", analysis_failed: "Analysis failed",
  document_deleted: "Document deleted", report_downloaded: "Report downloaded", password_changed: "Password changed",
};
