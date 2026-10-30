import { Fragment, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { Download, Info, RefreshCw } from "lucide-react";
import { api, downloadReport, errMsg, get } from "../services/api";
import { useAsync } from "../hooks/useAsync";
import { fmtBytes, fmtDate, typeLabel } from "../utils/format";
import { BlobImage, btnGhost, btnPrimary, Card, ErrorBanner, PageHeader, RiskBadge, SeverityTag, Spinner, StatusPill } from "../components/ui";

const Json = ({ o }) => <dl className="mt-2 grid grid-cols-[auto,1fr] gap-x-3 gap-y-1 text-xs text-muted">{Object.entries(o || {}).filter(([, v]) => v !== null && typeof v !== "object").map(([k, v]) => <Fragment key={k}><dt className="font-mono">{k}</dt><dd className="break-all text-fg/80">{String(v)}</dd></Fragment>)}</dl>;

export default function Results() {
  const { id } = useParams(); const nav = useNavigate();
  const { data: a, error, loading, reload } = useAsync(() => get(`/api/analysis/${id}`), [id]);
  const [busy, setBusy] = useState(""); const [err, setErr] = useState(""); const [tab, setTab] = useState("preview");
  if (loading) return <Spinner />;
  if (error) return <ErrorBanner message={error} onRetry={reload} />;
  if (a.status !== "completed") return <Card><p>This analysis is <b>{a.status}</b>{a.error && `: ${a.error}`}.</p><Link className={`${btnGhost} mt-4`} to={`/documents/${a.document_id}/progress`}>View progress</Link></Card>;
  const r = a.risk, doc = a.document;
  const dl = async () => { setBusy("dl"); setErr(""); try { await downloadReport(a.id, `forensic-report-${doc.original_filename.replace(/\.[^.]+$/, "")}.pdf`); } catch (e) { setErr(e.response ? "Report could not be generated." : errMsg(e)); } finally { setBusy(""); } };
  const redo = async () => { setBusy("re"); setErr(""); try { await api.post(`/api/documents/${a.document_id}/analyze`); nav(`/documents/${a.document_id}/progress`); } catch (e) { setErr(errMsg(e)); setBusy(""); } };
  return (
    <>
      <PageHeader title={doc.original_filename} subtitle={`${typeLabel(a.doc_type)} · ${fmtBytes(doc.size_bytes)} · analysed ${fmtDate(a.completed_at)}`}>
        <button className={btnGhost} onClick={redo} disabled={!!busy}><RefreshCw className="h-4 w-4" aria-hidden />Re-analyse</button>
        <button className={btnPrimary} onClick={dl} disabled={!!busy}><Download className="h-4 w-4" aria-hidden />{busy === "dl" ? "Preparing…" : "Download report"}</button>
      </PageHeader>
      <ErrorBanner message={err} />
      <Card className="mb-6">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div><RiskBadge category={a.category} /><p className="mt-3 max-w-xl text-sm text-muted">{r.insufficient_reasons?.[0] || (r.contributions.length ? `${r.contributions.length} indicator(s) contributed to this score.` : "No scored indicators were triggered.")}</p></div>
          <div className="flex gap-8 text-center">
            <div><p className="text-4xl font-semibold tabular-nums">{r.score}<span className="text-lg text-muted">/100</span></p><p className="text-xs uppercase tracking-wider text-muted">Risk indicator score</p></div>
            <div><p className="text-4xl font-semibold tabular-nums">{Math.round(r.technical_confidence)}<span className="text-lg text-muted">/100</span></p><p className="text-xs uppercase tracking-wider text-muted">Technical confidence</p></div>
          </div>
        </div>
        <div className="mt-4 flex gap-2 rounded-lg border border-line bg-bg/60 p-3 text-xs text-muted"><Info className="mt-0.5 h-4 w-4 shrink-0 text-sky" aria-hidden /><p>{r.disclaimer} Technical confidence measures how much evidence could be evaluated (text quality {r.confidence_breakdown.text_quality}, forensic coverage {r.confidence_breakdown.forensic_coverage}, rule coverage {r.confidence_breakdown.validation_coverage}); it is independent of risk. Thresholds: medium ≥ {r.thresholds.medium}, high ≥ {r.thresholds.high}.</p></div>
      </Card>

      <div className="grid gap-6 lg:grid-cols-5">
        <div className="space-y-6 lg:col-span-3">
          <Card title="Key indicators">
            {r.contributions.length === 0 ? <p className="text-sm text-muted">No indicators were triggered by the checks that could run.</p> :
              <ul className="space-y-3">{r.contributions.map((c) => <li key={c.key} className="rounded-lg border border-line p-3"><div className="flex items-center justify-between gap-2"><p className="font-medium">{c.label}</p><span className="flex items-center gap-2"><SeverityTag severity={c.severity} /><span className="font-mono text-sm text-warn">+{c.points}</span></span></div><p className="mt-1 text-sm text-muted">{c.explanation}</p><p className="mt-1 text-[11px] uppercase tracking-wide text-muted/80">{c.source}</p></li>)}</ul>}
            {r.anomaly && <p className="mt-4 text-xs text-muted"><b>Anomaly model:</b> {r.anomaly.available ? `${r.anomaly.atypicality_percentile}th percentile atypicality versus ${r.anomaly.baseline_size} of your earlier documents (context only; not scored). ${r.anomaly.note}` : r.anomaly.reason}</p>}
          </Card>
          <Card title={`Validation rules (${a.validation.length})`}>
            <ul className="divide-y divide-line">{a.validation.map((v) => <li key={v.rule} className="py-3"><div className="flex flex-wrap items-center justify-between gap-2"><p className="text-sm font-medium">{v.label}</p><span className="flex items-center gap-2"><SeverityTag severity={v.severity} /><StatusPill status={v.status} /></span></div><p className="mt-1 text-sm text-muted">{v.explanation}</p>{Object.keys(v.evidence || {}).length > 0 && <details className="mt-1 text-xs"><summary className="cursor-pointer text-sky">Evidence</summary><pre className="mt-1 overflow-x-auto rounded bg-bg p-2 font-mono text-muted">{JSON.stringify(v.evidence, null, 2)}</pre></details>}</li>)}</ul>
          </Card>
          <Card title="Forensic findings">
            <ul className="space-y-3">{a.forensic.findings.map((f) => <li key={f.key} className="rounded-lg border border-line p-3"><div className="flex flex-wrap items-center justify-between gap-2"><p className="font-medium">{f.name}</p><span className="flex items-center gap-2"><SeverityTag severity={f.flagged ? f.severity : null} /><StatusPill status={f.status} flagged={f.flagged} /></span></div><p className="mt-1 text-sm text-muted">{f.summary}</p>{f.status === "completed" && <Json o={f.details} />}{f.limitation && <p className="mt-2 text-xs italic text-muted/80">Limitation: {f.limitation}</p>}</li>)}</ul>
          </Card>
        </div>
        <div className="space-y-6 lg:col-span-2">
          <Card title="Document">
            <div role="tablist" className="mb-3 flex gap-2 text-sm">{[["preview", "Preview"], ...(a.has_heatmap ? [["ela", "ELA heatmap"]] : [])].map(([k, l]) => <button key={k} role="tab" aria-selected={tab === k} onClick={() => setTab(k)} className={`rounded-md px-3 py-1 ${tab === k ? "bg-teal/15 text-teal" : "text-muted"}`}>{l}</button>)}</div>
            <div className="max-h-[520px] overflow-auto rounded-lg border border-line bg-white/5 scrollbar-thin">
              {tab === "preview" ? <BlobImage path={`/api/documents/${doc.id}/preview`} alt={`Preview of ${doc.original_filename}`} className="w-full" /> : <BlobImage path={`/api/analysis/${a.id}/heatmap`} alt="Error level analysis heatmap" className="w-full" />}
            </div>
            {tab === "ela" && <p className="mt-2 text-xs text-muted">Brighter = larger recompression error. Yellow boxes mark blocks that are outliers versus comparable regions. An indicator only.</p>}
            <p className="mt-2 text-xs text-muted">{doc.file_type.toUpperCase()} · {doc.page_count} page(s) · {doc.width}×{doc.height}</p>
          </Card>
          <Card title={`Extracted fields (${a.fields.length})`}>
            {a.fields.length === 0 ? <p className="text-sm text-muted">No fields could be extracted. Nothing has been guessed.</p> :
              <ul className="space-y-3">{a.fields.map((f) => <li key={f.name} className="text-sm"><div className="flex items-start justify-between gap-2"><span className="text-muted">{f.label}</span><StatusPill status={f.validation_status} /></div><p className="break-words font-medium">{f.value}</p><p className="text-xs text-muted">{f.method} · {f.confidence === null ? "exact text" : `OCR conf ${f.confidence}`} · p.{f.page}{f.conflict && " · CONFLICTING VALUES"}{f.validation_note && ` · ${f.validation_note}`}</p></li>)}</ul>}
          </Card>
          <Card title="OCR / text extraction">
            <ul className="space-y-1 text-sm text-muted"><li>OCR engine: {a.ocr.available ? a.ocr.engine : `unavailable — ${a.ocr.reason}`}</li><li>OCR used: {a.ocr.used ? `yes (pages ${a.ocr.ocr_pages.join(", ")})` : "no"}</li>{a.ocr.mean_confidence != null && <li>Mean word confidence: {a.ocr.mean_confidence} · low-confidence words: {Math.round(a.ocr.low_confidence_ratio * 100)}%</li>}</ul>
            {a.ocr.warnings?.map((w, i) => <p key={i} className="mt-2 text-xs text-warn">{w}</p>)}
            {(!a.text || a.text.length < 30) && <p className="mt-2 text-sm text-warn">Little or no text was extracted, so field and rule checks are limited.</p>}
            <details className="mt-3"><summary className="cursor-pointer text-sm text-sky">Show extracted text ({a.text.length} chars)</summary><pre className="mt-2 max-h-72 overflow-auto whitespace-pre-wrap rounded bg-bg p-3 font-mono text-xs text-muted scrollbar-thin">{a.text || "(none)"}</pre></details>
          </Card>
        </div>
      </div>
    </>
  );
}
