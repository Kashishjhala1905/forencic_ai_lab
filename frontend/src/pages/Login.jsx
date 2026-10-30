import { useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { ScanSearch } from "lucide-react";
import { useAuth } from "../hooks/useAuth";
import { errMsg } from "../services/api";
import { btnPrimary, ErrorBanner, input } from "../components/ui";

export default function Login() {
  const { user, login, register } = useAuth(); const nav = useNavigate(); const loc = useLocation();
  const [mode, setMode] = useState("login"); const [f, setF] = useState({ email: "", name: "", password: "" });
  const [err, setErr] = useState(""); const [busy, setBusy] = useState(false);
  if (user) return <Navigate to={loc.state?.from || "/"} replace />;
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  const submit = async (e) => {
    e.preventDefault(); setErr(""); setBusy(true);
    try { mode === "login" ? await login(f.email, f.password) : await register(f.email, f.name, f.password); nav(loc.state?.from || "/", { replace: true }); }
    catch (x) { setErr(errMsg(x)); } finally { setBusy(false); }
  };
  return (
    <div className="grid min-h-full place-items-center p-4">
      <div className="w-full max-w-md rounded-2xl border border-line bg-panel/90 p-8 shadow-2xl">
        <div className="mb-6 flex items-center gap-3"><ScanSearch className="h-9 w-9 text-teal" aria-hidden /><div><h1 className="text-xl font-semibold">Forensic AI Lab</h1><p className="text-sm text-muted">Intelligent document fraud detection</p></div></div>
        <div role="tablist" className="mb-5 grid grid-cols-2 rounded-lg border border-line p-1 text-sm">
          {[["login", "Sign in"], ["register", "Create account"]].map(([k, l]) => <button key={k} role="tab" aria-selected={mode === k} onClick={() => { setMode(k); setErr(""); }} className={`rounded-md py-1.5 ${mode === k ? "bg-teal/15 text-teal" : "text-muted"}`}>{l}</button>)}
        </div>
        <form onSubmit={submit} className="space-y-4">
          {mode === "register" && <div><label htmlFor="name" className="mb-1 block text-sm">Full name</label><input id="name" className={input} required maxLength={80} value={f.name} onChange={set("name")} autoComplete="name" /></div>}
          <div><label htmlFor="email" className="mb-1 block text-sm">Email</label><input id="email" type="email" className={input} required value={f.email} onChange={set("email")} autoComplete="email" /></div>
          <div><label htmlFor="pw" className="mb-1 block text-sm">Password</label><input id="pw" type="password" className={input} required minLength={mode === "register" ? 8 : 1} value={f.password} onChange={set("password")} autoComplete={mode === "login" ? "current-password" : "new-password"} />{mode === "register" && <p className="mt-1 text-xs text-muted">At least 8 characters.</p>}</div>
          <ErrorBanner message={err} />
          <button className={`${btnPrimary} w-full`} disabled={busy}>{busy ? "Please wait…" : mode === "login" ? "Sign in" : "Create account"}</button>
        </form>
        <p className="mt-6 text-xs text-muted">All analysis runs locally on the server you host. Results are indicators for human review, not proof of fraud.</p>
      </div>
    </div>
  );
}
