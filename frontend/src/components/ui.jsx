import { useEffect, useState } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { AlertTriangle, CheckCircle2, HelpCircle, Loader2, MinusCircle, ShieldAlert, ShieldCheck, XCircle, Info } from "lucide-react";
import { useAuth } from "../hooks/useAuth";
import { blobUrl } from "../services/api";
import { CATEGORY } from "../utils/format";

const ICONS = { ShieldCheck, AlertTriangle, ShieldAlert, HelpCircle };
const TONES = {
  ok: "text-ok border-ok/40 bg-ok/10", warn: "text-warn border-warn/40 bg-warn/10", bad: "text-bad border-bad/40 bg-bad/10",
  sky: "text-sky border-sky/40 bg-sky/10", mute: "text-muted border-line bg-panel2",
};

export const btn = "inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition disabled:opacity-50 disabled:cursor-not-allowed";
export const btnPrimary = `${btn} bg-teal text-bg hover:bg-teal/90`;
export const btnGhost = `${btn} border border-line text-fg hover:bg-panel2`;
export const btnDanger = `${btn} border border-bad/50 text-bad hover:bg-bad/10`;
export const input = "w-full rounded-lg border border-line bg-bg px-3 py-2 text-sm text-fg placeholder:text-muted/70 focus:border-sky";

export const Card = ({ title, action, children, className = "" }) => (
  <section className={`rounded-xl border border-line bg-panel/90 p-5 ${className}`}>
    {(title || action) && <div className="mb-4 flex items-center justify-between gap-3"><h2 className="text-sm font-semibold uppercase tracking-wider text-muted">{title}</h2>{action}</div>}
    {children}
  </section>
);

export const Spinner = ({ label = "Loading…" }) => (
  <div role="status" className="flex items-center justify-center gap-2 py-10 text-muted"><Loader2 className="h-5 w-5 animate-spin" aria-hidden /> <span>{label}</span></div>
);

export const ErrorBanner = ({ message, onRetry }) => message ? (
  <div role="alert" className="flex items-start gap-3 rounded-lg border border-bad/40 bg-bad/10 p-3 text-sm text-bad">
    <XCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden /><span className="flex-1">{message}</span>
    {onRetry && <button onClick={onRetry} className="underline">Retry</button>}
  </div>) : null;

export const EmptyState = ({ icon: I = Info, title, children }) => (
  <div className="flex flex-col items-center gap-2 py-10 text-center"><I className="h-8 w-8 text-muted" aria-hidden /><p className="font-medium">{title}</p><p className="max-w-md text-sm text-muted">{children}</p></div>
);

export const PageHeader = ({ title, subtitle, children }) => (
  <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
    <div><h1 className="text-2xl font-semibold tracking-tight">{title}</h1>{subtitle && <p className="mt-1 text-sm text-muted">{subtitle}</p>}</div>
    <div className="flex gap-2">{children}</div>
  </div>
);

/** Category badge: icon + full text label, so meaning never relies on colour alone. */
export function RiskBadge({ category, compact = false }) {
  if (!category) return <span className="text-muted">—</span>;
  const c = CATEGORY[category]; const I = ICONS[c.icon];
  return <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-semibold ${TONES[c.tone]}`}><I className="h-3.5 w-3.5" aria-hidden />{compact ? c.short : c.label}</span>;
}

const STATUS = {
  pass: ["Pass", CheckCircle2, "ok"], fail: ["Fail", XCircle, "bad"], not_applicable: ["N/A", MinusCircle, "mute"],
  completed: ["Completed", CheckCircle2, "ok"], processing: ["Processing", Loader2, "sky"], queued: ["Queued", Loader2, "sky"],
  uploaded: ["Uploaded", Info, "mute"], failed: ["Failed", XCircle, "bad"], unavailable: ["Unavailable", MinusCircle, "mute"],
  valid: ["Valid", CheckCircle2, "ok"], invalid: ["Invalid", XCircle, "bad"], unchecked: ["Unchecked", MinusCircle, "mute"],
};
export function StatusPill({ status, flagged }) {
  const [label, I, tone] = flagged ? ["Flagged", AlertTriangle, "warn"] : STATUS[status] || [status, Info, "mute"];
  const spin = status === "processing" || status === "queued";
  return <span className={`inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-xs font-medium ${TONES[tone]}`}><I className={`h-3 w-3 ${spin ? "animate-spin" : ""}`} aria-hidden />{label}</span>;
}

export const SeverityTag = ({ severity }) => severity && severity !== "info"
  ? <span className="rounded border border-line px-1.5 py-0.5 text-[11px] uppercase tracking-wide text-muted">{severity}</span> : null;

export const StatCard = ({ label, value, icon: I, hint, tone = "mute" }) => (
  <div className="rounded-xl border border-line bg-panel/90 p-4">
    <div className="flex items-center justify-between"><p className="text-xs uppercase tracking-wider text-muted">{label}</p><span className={`rounded-lg border p-1.5 ${TONES[tone]}`}><I className="h-4 w-4" aria-hidden /></span></div>
    <p className="mt-2 text-3xl font-semibold tabular-nums">{value}</p>{hint && <p className="mt-1 text-xs text-muted">{hint}</p>}
  </div>
);

export function ProtectedRoute({ children, role }) {
  const { user, loading } = useAuth(); const loc = useLocation();
  if (loading) return <Spinner label="Checking session…" />;
  if (!user) return <Navigate to="/login" replace state={{ from: loc.pathname }} />;
  if (role && user.role !== role) return <Navigate to="/" replace />;
  return children;
}

/** <img> that loads an authenticated endpoint as a blob. */
export function BlobImage({ path, alt, className = "" }) {
  const [state, setState] = useState({ url: null, err: false });
  useEffect(() => {
    let url, dead = false;
    blobUrl(path).then((u) => { url = u; if (!dead) setState({ url: u, err: false }); }).catch(() => !dead && setState({ url: null, err: true }));
    return () => { dead = true; if (url) URL.revokeObjectURL(url); };
  }, [path]);
  if (state.err) return <p className="p-6 text-center text-sm text-muted">Preview unavailable.</p>;
  if (!state.url) return <Spinner label="Loading preview…" />;
  return <img src={state.url} alt={alt} className={className} />;
}

export function Pager({ page, pages, onChange }) {
  return (
    <nav className="mt-4 flex items-center justify-between text-sm" aria-label="Pagination">
      <span className="text-muted">Page {page} of {pages}</span>
      <div className="flex gap-2"><button className={btnGhost} disabled={page <= 1} onClick={() => onChange(page - 1)}>Previous</button><button className={btnGhost} disabled={page >= pages} onClick={() => onChange(page + 1)}>Next</button></div>
    </nav>
  );
}
