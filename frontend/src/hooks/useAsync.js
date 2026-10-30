import { useCallback, useEffect, useRef, useState } from "react";
import { errMsg } from "../services/api";

/** Run an async loader on mount / when deps change. Returns {data, error, loading, reload}. */
export function useAsync(fn, deps = []) {
  const [state, set] = useState({ data: null, error: null, loading: true });
  const alive = useRef(true);
  const run = useCallback(() => {
    set((s) => ({ ...s, loading: true, error: null }));
    fn().then((data) => alive.current && set({ data, error: null, loading: false }))
        .catch((e) => alive.current && set({ data: null, error: errMsg(e), loading: false }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  useEffect(() => { alive.current = true; run(); return () => { alive.current = false; }; }, [run]);
  return { ...state, reload: run };
}
