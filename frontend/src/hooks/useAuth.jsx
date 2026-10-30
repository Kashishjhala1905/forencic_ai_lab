import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api, tokenStore } from "../services/api";

const Ctx = createContext(null);
export const useAuth = () => useContext(Ctx);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(!!tokenStore.get());

  useEffect(() => {
    if (!tokenStore.get()) return;
    api.get("/api/auth/me").then((r) => setUser(r.data)).catch(() => tokenStore.clear()).finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    const h = () => setUser(null);
    window.addEventListener("fal:unauthorized", h);
    return () => window.removeEventListener("fal:unauthorized", h);
  }, []);

  const finish = (data) => { tokenStore.set(data.access_token); setUser(data.user); return data.user; };
  const login = useCallback((email, password) => api.post("/api/auth/login", { email, password }).then((r) => finish(r.data)), []);
  const register = useCallback((email, name, password) => api.post("/api/auth/register", { email, name, password }).then((r) => finish(r.data)), []);
  const logout = useCallback(() => { tokenStore.clear(); setUser(null); }, []);

  return <Ctx.Provider value={{ user, loading, login, register, logout }}>{children}</Ctx.Provider>;
}
