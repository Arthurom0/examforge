import { useEffect, useState } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { api, Health } from "../api";

const NAV = [
  { to: "/", label: "Library", end: true },
  { to: "/exercises", label: "Booklet exercises" },
  { to: "/generate", label: "Generate" },
  { to: "/sets", label: "Problem sets" },
  { to: "/dashboard", label: "Dashboard" },
  { to: "/settings", label: "Settings" },
];

function ThemeToggle() {
  const [dark, setDark] = useState(() => document.documentElement.classList.contains("dark"));
  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
    try {
      localStorage.setItem("theme", dark ? "dark" : "light");
    } catch {
      /* storage unavailable */
    }
  }, [dark]);
  return (
    <button
      onClick={() => setDark((d) => !d)}
      className="rounded-lg p-2 text-slate-500 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800"
      title="Toggle dark mode"
    >
      {dark ? (
        <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
          <circle cx="12" cy="12" r="4" />
          <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
        </svg>
      ) : (
        <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
          <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z" />
        </svg>
      )}
    </button>
  );
}

export default function Layout() {
  const [health, setHealth] = useState<Health | null>(null);
  const [down, setDown] = useState(false);
  const location = useLocation();
  // Re-check on navigation and after Settings changes so the key banner stays accurate.
  const [settingsVersion, setSettingsVersion] = useState(0);
  useEffect(() => {
    const onChange = () => setSettingsVersion((v) => v + 1);
    window.addEventListener("examforge:settings-changed", onChange);
    return () => window.removeEventListener("examforge:settings-changed", onChange);
  }, []);
  useEffect(() => {
    api
      .health()
      .then((h) => {
        setHealth(h);
        setDown(false);
      })
      .catch(() => setDown(true));
  }, [location.pathname, settingsVersion]);

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-20 border-b border-slate-200 bg-white/80 backdrop-blur dark:border-slate-800 dark:bg-slate-950/80">
        <div className="mx-auto flex max-w-6xl items-center gap-6 px-4 py-3">
          <NavLink to="/" className="flex items-center gap-2 font-semibold">
            <img src="/favicon.svg" className="h-7 w-7" alt="" />
            ExamForge
          </NavLink>
          <nav className="flex flex-1 flex-wrap gap-1">
            {NAV.map((n) => (
              <NavLink
                key={n.to}
                to={n.to}
                end={n.end}
                className={({ isActive }) =>
                  `rounded-lg px-3 py-1.5 text-sm font-medium ${
                    isActive
                      ? "bg-slate-100 text-slate-900 dark:bg-slate-800 dark:text-white"
                      : "text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white"
                  }`
                }
              >
                {n.label}
              </NavLink>
            ))}
          </nav>
          <ThemeToggle />
        </div>
      </header>
      {(down || (health && !health.api_key_configured)) && (
        <div className="border-b border-amber-200 bg-amber-50 text-amber-900 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-200">
          <div className="mx-auto max-w-6xl px-4 py-2 text-sm">
            {down ? (
              "The ExamForge engine is not responding. Restart the app (or `make dev` in development)."
            ) : (
              <>
                No {health?.provider_name ?? "AI"} API key yet. Uploading and practicing work, but generating problems needs one.{" "}
                <Link to="/settings" className="font-medium underline">
                  Add it in Settings
                </Link>
              </>
            )}
          </div>
        </div>
      )}
      <main className="mx-auto max-w-6xl px-4 py-8">
        <Outlet context={health} />
      </main>
    </div>
  );
}
