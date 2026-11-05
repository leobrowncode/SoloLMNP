import { useEffect, useState } from "react";
import { Navigate, Outlet, useLocation } from "react-router-dom";
import { restoreNeonToken } from "../api/neonAuth";
import { loginPath, readToken, storeToken, testAuthMode } from "../api/session";

type Gate = "checking" | "in" | "out";

export default function RequireAuth() {
  const location = useLocation();
  const [restored, setRestored] = useState<{ path: string; gate: Exclude<Gate, "checking"> } | null>(
    null,
  );

  useEffect(() => {
    if (readToken() || testAuthMode()) return;
    let cancelled = false;
    restoreNeonToken(location.search)
      .then((token) => {
        if (cancelled) return;
        if (token) storeToken(token);
        setRestored({ path: location.pathname, gate: token ? "in" : "out" });
      })
      .catch(() => {
        if (!cancelled) setRestored({ path: location.pathname, gate: "out" });
      });
    return () => {
      cancelled = true;
    };
  }, [location.pathname, location.search]);

  if (readToken()) return <Outlet />;
  const next = location.pathname + location.search + location.hash;
  if (testAuthMode()) return <Navigate to={loginPath(next)} replace />;
  const gate = restored?.path === location.pathname ? restored.gate : "checking";
  if (gate === "checking") return <p className="login-wait">Vérification de la session…</p>;
  if (gate === "out") return <Navigate to={loginPath(next)} replace />;
  return <Outlet />;
}
