import { Link } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, Cell, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis, LabelList } from "recharts";
import { AlertTriangle, FileSearch, HelpCircle, ShieldAlert, ShieldCheck, Upload } from "lucide-react";
import { get } from "../services/api";
import { useAsync } from "../hooks/useAsync";
import { ACTION_LABEL, fmtDate, typeLabel } from "../utils/format";
import { btnPrimary, Card, EmptyState, ErrorBanner, PageHeader, RiskBadge, Spinner, StatCard } from "../components/ui";

const COLORS = { LOW: "#34d399", MEDIUM: "#fbbf24", HIGH: "#f87171", INSUFFICIENT: "#38bdf8" };
const NAMES = { LOW: "Low", MEDIUM: "Medium", HIGH: "High", INSUFFICIENT: "Insufficient" };

export default function Dashboard() {
  const s = useAsync(() => get("/api/dashboard/stats"), []);
  const r = useAsync(() => get("/api/dashboard/recent"), []);
  if (s.loading || r.loading) return <Spinner />;
  if (s.error || r.error) return <ErrorBanner message={s.error || r.error} onRetry={() => { s.reload(); r.reload(); }} />;
  const st = s.data, rec = r.data;
  const dist = Object.keys(COLORS).map((k) => ({ key: k, name: NAMES[k], count: st.risk_distribution[k] }));
  return (
    <>
      <PageHeader title="Dashboard" subtitle="Live statistics from your analysed documents."><Link to="/upload" className={btnPrimary}><Upload className="h-4 w-4" aria-hidden />Upload document</Link></PageHeader>
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
        <StatCard label="Documents" value={st.total_documents} icon={FileSearch} tone="sky" hint={`${st.analyzed} analysed`} />
        <StatCard label="Low risk" value={st.low_risk} icon={ShieldCheck} tone="ok" />
        <StatCard label="Medium risk" value={st.medium_risk} icon={AlertTriangle} tone="warn" />
        <StatCard label="High risk" value={st.high_risk} icon={ShieldAlert} tone="bad" />
        <StatCard label="Manual review" value={st.manual_review} icon={HelpCircle} tone="sky" hint="Not rated low risk" />
      </div>
      {st.total_documents === 0 ? (
        <Card className="mt-6"><EmptyState icon={Upload} title="No documents yet">Upload a PDF, PNG or JPEG to run your first analysis. Nothing on this page is sample data.</EmptyState></Card>
      ) : (
        <div className="mt-6 grid gap-6 lg:grid-cols-2">
          <Card title="Risk distribution">
            <div className="h-64" role="img" aria-label={`Risk distribution: ${dist.map((d) => `${d.name} ${d.count}`).join(", ")}`}>
              <ResponsiveContainer><BarChart data={dist} margin={{ top: 20 }}><CartesianGrid stroke="#263654" vertical={false} /><XAxis dataKey="name" stroke="#9bacc9" /><YAxis allowDecimals={false} stroke="#9bacc9" />
                <Tooltip contentStyle={{ background: "#111a2e", border: "1px solid #263654" }} /><Bar dataKey="count" radius={[6, 6, 0, 0]}>{dist.map((d) => <Cell key={d.key} fill={COLORS[d.key]} />)}<LabelList dataKey="count" position="top" fill="#e6edf7" /></Bar></BarChart></ResponsiveContainer>
            </div>
          </Card>
          <Card title="Analyses completed — last 14 days">
            <div className="h-64" role="img" aria-label="Line chart of analyses completed per day">
              <ResponsiveContainer><LineChart data={st.daily} margin={{ top: 20, right: 10 }}><CartesianGrid stroke="#263654" vertical={false} /><XAxis dataKey="date" stroke="#9bacc9" tickFormatter={(d) => d.slice(5)} /><YAxis allowDecimals={false} stroke="#9bacc9" />
                <Tooltip contentStyle={{ background: "#111a2e", border: "1px solid #263654" }} /><Line type="monotone" dataKey="count" stroke="#2dd4bf" strokeWidth={2} dot={{ r: 3 }} /></LineChart></ResponsiveContainer>
            </div>
          </Card>
        </div>
      )}
      <div className="mt-6 grid gap-6 lg:grid-cols-5">
        <Card title="Recent analyses" className="lg:col-span-3" action={<Link to="/history" className="text-sm text-sky hover:underline">View all</Link>}>
          {rec.recent_analyses.length === 0 ? <p className="text-sm text-muted">No completed analyses yet.</p> : (
            <ul className="divide-y divide-line">{rec.recent_analyses.map((a) => (
              <li key={a.analysis_id} className="flex flex-wrap items-center justify-between gap-2 py-3">
                <Link to={`/analysis/${a.analysis_id}`} className="min-w-0"><p className="truncate font-medium hover:text-teal">{a.original_filename}</p><p className="text-xs text-muted">{typeLabel(a.doc_type)} · {fmtDate(a.completed_at)}</p></Link>
                <div className="flex items-center gap-3"><span className="text-sm tabular-nums text-muted">{a.score}/100</span><RiskBadge category={a.category} compact /></div>
              </li>))}</ul>)}
        </Card>
        <Card title="Recent activity" className="lg:col-span-2">
          {rec.recent_activity.length === 0 ? <p className="text-sm text-muted">No activity.</p> : (
            <ul className="space-y-3 text-sm">{rec.recent_activity.map((e, i) => <li key={i} className="flex justify-between gap-3"><span>{ACTION_LABEL[e.action] || e.action}</span><span className="shrink-0 text-xs text-muted">{fmtDate(e.created_at)}</span></li>)}</ul>)}
        </Card>
      </div>
    </>
  );
}
