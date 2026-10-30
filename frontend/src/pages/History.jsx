import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Search } from "lucide-react";
import { get } from "../services/api";
import { useAsync } from "../hooks/useAsync";
import { DOC_TYPES, fmtBytes, fmtDate, typeLabel } from "../utils/format";
import { Card, EmptyState, ErrorBanner, input, PageHeader, Pager, RiskBadge, Spinner, StatusPill } from "../components/ui";

export function useDebounced(v, ms = 300) { const [x, setX] = useState(v); useEffect(() => { const t = setTimeout(() => setX(v), ms); return () => clearTimeout(t); }, [v, ms]); return x; }

export default function History({ reportsMode = false, children }) {
  const [f, setF] = useState({ search: "", risk: "", status: reportsMode ? "completed" : "", doc_type: "", date_from: "", date_to: "" });
  const [page, setPage] = useState(1); const q = useDebounced(f.search);
  const { data, error, loading, reload } = useAsync(() => get("/api/documents", { ...f, search: q, page, page_size: 10 }), [q, f.risk, f.status, f.doc_type, f.date_from, f.date_to, page]);
  const set = (k) => (e) => { setF({ ...f, [k]: e.target.value }); setPage(1); };
  const Sel = ({ k, label, opts }) => <div><label className="mb-1 block text-xs text-muted" htmlFor={k}>{label}</label><select id={k} className={input} value={f[k]} onChange={set(k)}>{opts.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></div>;
  return (
    <>
      {children}
      <Card className="mb-4">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-6">
          <div className="lg:col-span-2"><label htmlFor="s" className="mb-1 block text-xs text-muted">Search filename or type</label><div className="relative"><Search className="absolute left-3 top-2.5 h-4 w-4 text-muted" aria-hidden /><input id="s" className={`${input} pl-9`} value={f.search} onChange={set("search")} placeholder="invoice…" /></div></div>
          <Sel k="risk" label="Risk" opts={[["", "All"], ["LOW", "Low"], ["MEDIUM", "Medium"], ["HIGH", "High"], ["INSUFFICIENT", "Insufficient"]]} />
          {!reportsMode && <Sel k="status" label="Status" opts={[["", "All"], ["uploaded", "Uploaded"], ["processing", "Processing"], ["completed", "Completed"], ["failed", "Failed"]]} />}
          <Sel k="doc_type" label="Type" opts={[["", "All"], ...DOC_TYPES.slice(1)]} />
          <div><label htmlFor="df" className="mb-1 block text-xs text-muted">From</label><input id="df" type="date" className={input} value={f.date_from} onChange={set("date_from")} /></div>
          <div><label htmlFor="dt" className="mb-1 block text-xs text-muted">To</label><input id="dt" type="date" className={input} value={f.date_to} onChange={set("date_to")} /></div>
        </div>
      </Card>
      <ErrorBanner message={error} onRetry={reload} />
      {loading && !data ? <Spinner /> : data && (
        <Card>
          {data.items.length === 0 ? <EmptyState title="No documents match">Adjust the filters or upload a document.</EmptyState> : (
            <div className="overflow-x-auto"><table className="w-full min-w-[720px] text-left text-sm">
              <thead className="text-xs uppercase tracking-wider text-muted"><tr><th className="pb-2">File</th><th>Type</th><th>Risk</th><th>Score</th><th>Status</th><th>Uploaded</th><th className="text-right">Actions</th></tr></thead>
              <tbody className="divide-y divide-line">{data.items.map((d) => (
                <tr key={d.id} className="align-middle"><td className="max-w-[220px] py-3"><Link to={`/documents/${d.id}`} className="block truncate font-medium hover:text-teal">{d.original_filename}</Link><span className="text-xs text-muted">{fmtBytes(d.size_bytes)}</span></td>
                  <td>{typeLabel(d.doc_type || d.doc_type_selected)}</td><td><RiskBadge category={d.category} compact /></td><td className="tabular-nums">{d.score ?? "—"}</td><td><StatusPill status={d.analysis_status || d.status} /></td><td className="text-xs text-muted">{fmtDate(d.created_at)}</td>
                  <td className="text-right">{d.analysis_status === "completed" ? <Link className="text-sky hover:underline" to={`/analysis/${d.analysis_id}`}>{reportsMode ? "Open / download" : "Results"}</Link> : <Link className="text-sky hover:underline" to={`/documents/${d.id}`}>Details</Link>}</td></tr>))}</tbody></table></div>)}
          {data.total > 0 && <Pager page={data.page} pages={data.pages} onChange={setPage} />}
          <p className="mt-2 text-xs text-muted">{data.total} document(s)</p>
        </Card>)}
    </>
  );
}
