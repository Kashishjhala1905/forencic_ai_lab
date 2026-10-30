import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, errMsg } from "../services/api";
import { useAuth } from "../hooks/useAuth";
import { fmtDate } from "../utils/format";
import { btnGhost, btnPrimary, Card, ErrorBanner, input, PageHeader } from "../components/ui";

export default function Profile() {
  const { user, logout } = useAuth(); const nav = useNavigate(); const [f, setF] = useState({ current_password: "", new_password: "" }); const [msg, setMsg] = useState(""); const [err, setErr] = useState("");
  const submit = async (e) => { e.preventDefault(); setErr(""); setMsg(""); try { await api.post("/api/auth/change-password", f); setMsg("Password updated."); setF({ current_password: "", new_password: "" }); } catch (x) { setErr(errMsg(x)); } };
  return (
    <>
      <PageHeader title="Profile & settings" />
      <div className="grid gap-6 md:grid-cols-2">
        <Card title="Account"><dl className="space-y-3 text-sm"><div><dt className="text-xs text-muted">Name</dt><dd>{user.name}</dd></div><div><dt className="text-xs text-muted">Email</dt><dd>{user.email}</dd></div><div><dt className="text-xs text-muted">Role</dt><dd>{user.role}</dd></div><div><dt className="text-xs text-muted">Member since</dt><dd>{fmtDate(user.created_at)}</dd></div></dl>
          <button className={`${btnGhost} mt-5`} onClick={() => { logout(); nav("/login"); }}>Sign out</button></Card>
        <Card title="Change password"><form onSubmit={submit} className="space-y-4">
          <div><label htmlFor="cp" className="mb-1 block text-sm">Current password</label><input id="cp" type="password" className={input} required autoComplete="current-password" value={f.current_password} onChange={(e) => setF({ ...f, current_password: e.target.value })} /></div>
          <div><label htmlFor="np" className="mb-1 block text-sm">New password</label><input id="np" type="password" className={input} required minLength={8} autoComplete="new-password" value={f.new_password} onChange={(e) => setF({ ...f, new_password: e.target.value })} /></div>
          <ErrorBanner message={err} />{msg && <p role="status" className="text-sm text-ok">{msg}</p>}<button className={btnPrimary}>Update password</button></form></Card>
      </div>
    </>
  );
}
