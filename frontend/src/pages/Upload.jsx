import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { FileUp, ShieldCheck } from "lucide-react";
import { api, errMsg } from "../services/api";
import { DOC_TYPES, fmtBytes } from "../utils/format";
import { btnPrimary, Card, ErrorBanner, input, PageHeader } from "../components/ui";

const MAX_MB = 15; // display hint only; the server enforces the real limit
const OK = ["application/pdf", "image/png", "image/jpeg"];

export default function Upload() {
  const nav = useNavigate(); const ref = useRef(); const [file, setFile] = useState(null); const [type, setType] = useState("auto");
  const [err, setErr] = useState(""); const [pct, setPct] = useState(null); const [drag, setDrag] = useState(false);
  const pick = (f) => {
    setErr("");
    if (!f) return;
    if (!OK.includes(f.type) && !/\.(pdf|png|jpe?g)$/i.test(f.name)) return setErr("Unsupported file type. Choose a PDF, PNG or JPEG file.");
    if (f.size > MAX_MB * 1048576) return setErr(`File is larger than ${MAX_MB} MB.`);
    setFile(f);
  };
  const go = async () => {
    setErr(""); setPct(0);
    const fd = new FormData(); fd.append("file", file); fd.append("doc_type", type);
    try {
      const up = await api.post("/api/documents/upload", fd, { onUploadProgress: (e) => setPct(Math.round((e.loaded / (e.total || file.size)) * 100)) });
      await api.post(`/api/documents/${up.data.id}/analyze`);
      nav(`/documents/${up.data.id}/progress`);
    } catch (x) { setErr(errMsg(x)); setPct(null); }
  };
  return (
    <>
      <PageHeader title="Upload document" subtitle="PDF, PNG or JPEG up to 15 MB. Files are analysed on the server you run, never sent to third parties." />
      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <div onDragOver={(e) => { e.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)} onDrop={(e) => { e.preventDefault(); setDrag(false); pick(e.dataTransfer.files[0]); }}
            className={`rounded-xl border-2 border-dashed p-10 text-center transition ${drag ? "border-teal bg-teal/5" : "border-line"}`}>
            <FileUp className="mx-auto h-10 w-10 text-sky" aria-hidden />
            <p className="mt-3 font-medium">{file ? file.name : "Drag a document here"}</p>
            <p className="text-sm text-muted">{file ? fmtBytes(file.size) : "or"}</p>
            <input ref={ref} id="file" type="file" accept=".pdf,.png,.jpg,.jpeg,application/pdf,image/png,image/jpeg" className="sr-only" onChange={(e) => pick(e.target.files[0])} />
            <label htmlFor="file" className="mt-3 inline-block cursor-pointer rounded-lg border border-line px-4 py-2 text-sm hover:bg-panel2 focus-within:outline">Browse files</label>
          </div>
          <div className="mt-5 grid gap-4 sm:grid-cols-2">
            <div><label htmlFor="dt" className="mb-1 block text-sm">Document type</label><select id="dt" className={input} value={type} onChange={(e) => setType(e.target.value)}>{DOC_TYPES.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></div>
          </div>
          <div className="mt-4"><ErrorBanner message={err} /></div>
          {pct !== null && <div className="mt-4" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}><div className="h-2 overflow-hidden rounded bg-panel2"><div className="h-full bg-teal transition-all" style={{ width: `${pct}%` }} /></div><p className="mt-1 text-xs text-muted">Uploading… {pct}%</p></div>}
          <button className={`${btnPrimary} mt-5`} disabled={!file || pct !== null} onClick={go}>Upload &amp; analyse</button>
        </Card>
        <Card title="What happens next">
          <ol className="list-decimal space-y-2 pl-5 text-sm text-muted"><li>The file is validated (real type, size, readability).</li><li>Text is read from the PDF or by local OCR.</li><li>Fields are extracted and cross-checked.</li><li>Forensic checks run where applicable (metadata, ELA, structure, duplicates).</li><li>You get a risk indicator, the evidence behind it, and a downloadable report.</li></ol>
          <p className="mt-4 flex gap-2 text-xs text-muted"><ShieldCheck className="h-4 w-4 shrink-0 text-teal" aria-hidden />Results are indicators for human review, not proof of fraud.</p>
        </Card>
      </div>
    </>
  );
}
