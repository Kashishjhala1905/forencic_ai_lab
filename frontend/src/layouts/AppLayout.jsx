import { useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { FileText, History, LayoutDashboard, LogOut, Menu, ScanSearch, Server, Upload, User, X } from "lucide-react";
import { useAuth } from "../hooks/useAuth";
import { btnPrimary } from "../components/ui";

const NAV = [["/", "Dashboard", LayoutDashboard], ["/upload", "Upload", Upload], ["/history", "History", History], ["/reports", "Reports", FileText], ["/profile", "Profile", User]];

export default function AppLayout() {
  const { user, logout } = useAuth(); const nav = useNavigate(); const [open, setOpen] = useState(false);
  const items = user.role === "admin" ? [...NAV, ["/admin", "System", Server]] : NAV;
  const link = ({ isActive }) => `flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition ${isActive ? "bg-teal/15 text-teal" : "text-muted hover:bg-panel2 hover:text-fg"}`;
  return (
    <div className="flex min-h-full">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:bg-panel focus:p-2">Skip to content</a>
      <aside className={`fixed inset-y-0 left-0 z-40 w-64 transform border-r border-line bg-panel p-4 transition md:static md:translate-x-0 ${open ? "translate-x-0" : "-translate-x-full"}`} aria-label="Primary">
        <div className="mb-6 flex items-center justify-between">
          <div className="flex items-center gap-2"><ScanSearch className="h-6 w-6 text-teal" aria-hidden /><span className="font-semibold">Forensic AI Lab</span></div>
          <button className="md:hidden" onClick={() => setOpen(false)} aria-label="Close menu"><X className="h-5 w-5" /></button>
        </div>
        <nav className="space-y-1">{items.map(([to, label, I]) => <NavLink key={to} to={to} end={to === "/"} className={link} onClick={() => setOpen(false)}><I className="h-4 w-4" aria-hidden />{label}</NavLink>)}</nav>
        <div className="absolute inset-x-4 bottom-4 border-t border-line pt-4">
          <p className="truncate text-sm font-medium">{user.name}</p><p className="truncate text-xs text-muted">{user.email}{user.role === "admin" && " · admin"}</p>
          <button onClick={() => { logout(); nav("/login"); }} className="mt-3 flex items-center gap-2 text-sm text-muted hover:text-fg"><LogOut className="h-4 w-4" aria-hidden />Sign out</button>
        </div>
      </aside>
      {open && <div className="fixed inset-0 z-30 bg-black/50 md:hidden" onClick={() => setOpen(false)} aria-hidden />}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-20 flex items-center justify-between border-b border-line bg-bg/80 px-4 py-3 backdrop-blur">
          <button className="md:hidden" onClick={() => setOpen(true)} aria-label="Open menu"><Menu className="h-5 w-5" /></button>
          <p className="hidden text-xs text-muted md:block">Automated analysis supports human review; it does not establish fraud.</p>
          <button className={btnPrimary} onClick={() => nav("/upload")}><Upload className="h-4 w-4" aria-hidden />Upload document</button>
        </header>
        <main id="main" className="fade-in mx-auto w-full max-w-6xl flex-1 p-4 md:p-8"><Outlet /></main>
      </div>
    </div>
  );
}
