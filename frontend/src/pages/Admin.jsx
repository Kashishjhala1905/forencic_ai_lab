import { get } from "../services/api";
import { useAsync } from "../hooks/useAsync";
import { ACTION_LABEL, fmtDate } from "../utils/format";
import { Card, ErrorBanner, PageHeader, Spinner, StatCard, StatusPill } from "../components/ui";
import { Database, FileText, Users, ScanText } from "lucide-react";

export default function Admin() {
  const { data, error, loading, reload } = useAsync(() => get("/api/admin/overview"), []);
  if (loading) return <Spinner />; if (error) return <ErrorBanner message={error} onRetry={reload} />;
  const h = data.health;
  return (
    <>
      <PageHeader title="System monitoring" subtitle="Administrator view (role enforced by the backend)." />
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4"><StatCard label="Users" value={data.counts.users} icon={Users} /><StatCard label="Documents" value={data.counts.documents} icon={FileText} tone="sky" /><StatCard label="Analyses" value={data.counts.analyses} icon={ScanText} tone="ok" hint={`${data.failed_analyses} failed`} /><StatCard label="Audit events" value={data.counts.audit_events} icon={Database} /></div>
      <div className="mt-6 grid gap-6 lg:grid-cols-3">
        <Card title="Service health"><ul className="space-y-3 text-sm"><li className="flex justify-between">Database ({h.database.engine}) <StatusPill status={h.database.ok ? "pass" : "fail"} /></li><li className="flex justify-between">OCR engine <StatusPill status={h.ocr.available ? "pass" : "unavailable"} /></li></ul>{h.ocr.available ? <p className="mt-3 text-xs text-muted">{h.ocr.engine}</p> : <p className="mt-3 text-xs text-warn">{h.ocr.reason}</p>}</Card>
        <Card title="Recent events (all users)" className="lg:col-span-2"><ul className="divide-y divide-line text-sm">{data.recent_events.map((e, i) => <li key={i} className="flex flex-wrap justify-between gap-2 py-2"><span>{ACTION_LABEL[e.action] || e.action} <span className="text-muted">· {e.email || "anonymous"}</span></span><span className="text-xs text-muted">{fmtDate(e.created_at)}</span></li>)}</ul></Card>
      </div>
    </>
  );
}
