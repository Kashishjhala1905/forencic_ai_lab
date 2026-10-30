import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { RefreshCw, Trash2 } from "lucide-react";
import { api, errMsg, get } from "../services/api";
import { useAsync } from "../hooks/useAsync";
import { fmtBytes, fmtDate, typeLabel } from "../utils/format";
import { BlobImage, btnDanger, btnGhost, Card, ErrorBanner, PageHeader, RiskBadge, Spinner, StatusPill } from "../components/ui";

export default function DocumentDetails() {
  const { id } = useParams(); const nav = useNavigate(); const { data: d, error, loading, reload } = useAsync(() => get(`/api/documents/${id}`), [id]);
  const [err, setErr] = useState(""); const [confirm, setConfirm] = useState(false);
  if (loading) return <Spinner />; if (error) return <ErrorBanner message={error} onRetry={reload} />;
  const run = async () => { try { await api.post(`/api/documents/${id}/analyze`); nav(`/documents/${id}/progress`); } catch (e) { setErr(errMsg(e)); } };
  const del = async () => { try { await api.delete(`/api/documents/${id}`); nav("/history", { replace: true }); } catch (e) { setErr(errMsg(e)); } };
  const rows = [["Type selected", typeLabel(d.doc_type_selected)], ["Format", d.file_type.toUpperCase()], ["Size", fmtBytes(d.size_bytes)], ["Pages", d.page_count], ["Dimensions", `${d.width}×${d.height}`], ["Uploaded", fmtDate(d.created_at)], ["SHA-256", d.sha256]];
  return (
    <>
      <PageHeader title={d.original_filename} subtitle="Document details"><button className={btnGhost} onClick={run}><RefreshCw className="h-4 w-4" aria-hidden />{d.analyses.length ? "Re-analyse" : "Analyse"}</button><button className={btnDanger} onClick={() => setConfirm(true)}><Trash2 className="h-4 w-4" aria-hidden />Delete</button></PageHeader>
      <ErrorBanner message={err} />
      {confirm && <div role="alertdialog" aria-label="Confirm deletion" className="mb-4 rounded-lg border border-bad/40 bg-bad/10 p-4 text-sm"><p>Permanently delete this document, its analyses, heatmaps and reports? Audit events are retained. This cannot be undone.</p><div className="mt-3 flex gap-2"><button className={btnDanger} onClick={del}>Yes, delete</button><button className={btnGhost} onClick={() => setConfirm(false)}>Cancel</button></div></div>}
      <div className="grid gap-6 lg:grid-cols-3">
        <Card title="Metadata" className="lg:col-span-1"><dl className="space-y-2 text-sm">{rows.map(([k, v]) => <div key={k}><dt className="text-xs text-muted">{k}</dt><dd className="break-all">{v}</dd></div>)}</dl></Card>
        <Card title="Preview" className="lg:col-span-2"><div className="max-h-96 overflow-auto rounded-lg border border-line"><BlobImage path={`/api/documents/${id}/preview`} alt={`Preview of ${d.original_filename}`} className="w-full" /></div></Card>
      </div>
      <Card title="Analysis history" className="mt-6">
        {d.analyses.length === 0 ? <p className="text-sm text-muted">This document has not been analysed yet.</p> :
          <ul className="divide-y divide-line">{d.analyses.map((a) => <li key={a.id} className="flex flex-wrap items-center justify-between gap-2 py-3 text-sm"><span>{fmtDate(a.created_at)}</span><span className="flex items-center gap-3"><RiskBadge category={a.category} compact />{a.score != null && <span className="tabular-nums text-muted">{a.score}/100</span>}<StatusPill status={a.status} />{a.status === "completed" ? <Link className="text-sky hover:underline" to={`/analysis/${a.id}`}>Open</Link> : <Link className="text-sky hover:underline" to={`/documents/${id}/progress`}>Progress</Link>}</span></li>)}</ul>}
      </Card>
    </>
  );
}
