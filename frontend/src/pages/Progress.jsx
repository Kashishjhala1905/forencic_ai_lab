import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { CheckCircle2, Circle, Loader2, XCircle } from "lucide-react";
import { get, errMsg } from "../services/api";
import { STAGES } from "../utils/format";
import { btnGhost, Card, ErrorBanner, PageHeader } from "../components/ui";

export default function Progress() {
  const { id } = useParams(); const nav = useNavigate(); const [d, setD] = useState(null); const [err, setErr] = useState(""); const [fails, setFails] = useState(0);
  useEffect(() => {
    let dead = false, timer;
    const tick = async () => {
      try {
        const x = await get(`/api/documents/${id}`); if (dead) return;
        setD(x); setErr(""); setFails(0);
        if (x.analysis_status === "completed") return nav(`/analysis/${x.analysis_id}`, { replace: true });
        if (x.analysis_status === "failed") return;
      } catch (e) { if (dead) return; setErr(errMsg(e)); setFails((n) => n + 1); }
      timer = setTimeout(tick, 1000);
    };
    tick();
    return () => { dead = true; clearTimeout(timer); };
  }, [id, nav]);
  const idx = Math.max(0, STAGES.findIndex(([k]) => k === d?.stage));
  const failed = d?.analysis_status === "failed";
  return (
    <>
      <PageHeader title="Analysing document" subtitle={d?.original_filename} />
      <Card className="max-w-2xl">
        <ErrorBanner message={err && (fails > 2 ? err : "")} />
        {failed && <div className="mb-4"><ErrorBanner message={d.error || "Analysis failed."} /></div>}
        <div role="progressbar" aria-valuenow={d?.progress || 0} aria-valuemin={0} aria-valuemax={100} className="mb-6 h-2 overflow-hidden rounded bg-panel2">
          <div className={`h-full transition-all duration-500 ${failed ? "bg-bad" : "bg-gradient-to-r from-teal to-sky"}`} style={{ width: `${failed ? 100 : d?.progress || 3}%` }} />
        </div>
        <ol className="space-y-3">
          {STAGES.map(([k, label], i) => {
            const done = !failed && i < idx, cur = i === idx && !failed;
            return <li key={k} className={`flex items-center gap-3 text-sm ${done || cur ? "" : "text-muted"}`}>
              {done ? <CheckCircle2 className="h-5 w-5 text-ok" aria-hidden /> : cur ? <Loader2 className="h-5 w-5 animate-spin text-sky" aria-hidden /> : failed && i === idx ? <XCircle className="h-5 w-5 text-bad" aria-hidden /> : <Circle className="h-5 w-5" aria-hidden />}
              <span>{label}</span><span className="sr-only">{done ? "done" : cur ? "in progress" : "pending"}</span></li>;
          })}
        </ol>
        {failed && <div className="mt-6 flex gap-2"><Link to={`/documents/${id}`} className={btnGhost}>Document details</Link><Link to="/upload" className={btnGhost}>Upload another</Link></div>}
      </Card>
    </>
  );
}
