import { ButtonHTMLAttributes, ReactNode, useCallback, useEffect, useState } from "react";
import type { Result } from "../api";

type Variant = "primary" | "secondary" | "ghost" | "danger";

const VARIANTS: Record<Variant, string> = {
  primary: "bg-indigo-600 text-white hover:bg-indigo-500 disabled:bg-indigo-400",
  secondary:
    "bg-white text-slate-800 ring-1 ring-slate-300 hover:bg-slate-50 dark:bg-slate-800 dark:text-slate-100 dark:ring-slate-600 dark:hover:bg-slate-700",
  ghost: "text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800",
  danger: "text-red-600 hover:bg-red-50 dark:text-red-400 dark:hover:bg-red-950",
};

export function Button({
  variant = "secondary",
  loading = false,
  className = "",
  children,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; loading?: boolean }) {
  return (
    <button
      {...props}
      disabled={props.disabled || loading}
      className={`inline-flex items-center justify-center gap-2 rounded-lg px-3 py-1.5 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-60 ${VARIANTS[variant]} ${className}`}
    >
      {loading && <Spinner />}
      {children}
    </button>
  );
}

export function Spinner({ className = "h-4 w-4" }: { className?: string }) {
  return <span className={`inline-block animate-spin rounded-full border-2 border-current border-t-transparent ${className}`} />;
}

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div className={`rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900 ${className}`}>
      {children}
    </div>
  );
}

const BADGE: Record<string, string> = {
  slate: "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300",
  indigo: "bg-indigo-50 text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300",
  green: "bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300",
  amber: "bg-amber-50 text-amber-800 dark:bg-amber-950 dark:text-amber-300",
  red: "bg-red-50 text-red-700 dark:bg-red-950 dark:text-red-300",
};

export function Badge({ children, color = "slate" }: { children: ReactNode; color?: keyof typeof BADGE }) {
  return <span className={`inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium ${BADGE[color]}`}>{children}</span>;
}

export function ErrorBox({ error }: { error: unknown }) {
  if (!error) return null;
  return (
    <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-900 dark:bg-red-950 dark:text-red-300">
      {error instanceof Error ? error.message : String(error)}
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="rounded-xl border border-dashed border-slate-300 p-8 text-center text-sm text-slate-500 dark:border-slate-700">{children}</div>;
}

export const inputCls =
  "w-full rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm text-slate-900 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100";

export function Field({ label, children, hint }: { label: string; children: ReactNode; hint?: ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">{label}</span>
      {children}
      {hint && <span className="mt-1 block text-xs text-slate-500">{hint}</span>}
    </label>
  );
}

export const RESULT_LABEL: Record<Result, string> = { correct: "Correct", partial: "Partial", wrong: "Wrong" };
export const RESULT_COLOR: Record<Result, "green" | "amber" | "red"> = { correct: "green", partial: "amber", wrong: "red" };

export function ResultButtons({ current, onPick }: { current?: Result | null; onPick: (r: Result) => Promise<unknown> }) {
  const [busy, setBusy] = useState<Result | null>(null);
  const [last, setLast] = useState<Result | null | undefined>(current);
  useEffect(() => setLast(current), [current]);
  const styles: Record<Result, string> = {
    correct: "ring-emerald-500 text-emerald-700 dark:text-emerald-300 hover:bg-emerald-50 dark:hover:bg-emerald-950",
    partial: "ring-amber-500 text-amber-700 dark:text-amber-300 hover:bg-amber-50 dark:hover:bg-amber-950",
    wrong: "ring-red-500 text-red-700 dark:text-red-300 hover:bg-red-50 dark:hover:bg-red-950",
  };
  const active: Record<Result, string> = {
    correct: "bg-emerald-600 text-white ring-emerald-600 hover:bg-emerald-600",
    partial: "bg-amber-500 text-white ring-amber-500 hover:bg-amber-500",
    wrong: "bg-red-600 text-white ring-red-600 hover:bg-red-600",
  };
  return (
    <div className="flex items-center gap-2">
      <span className="text-xs text-slate-500">My attempt:</span>
      {(["correct", "partial", "wrong"] as Result[]).map((r) => (
        <button
          key={r}
          disabled={busy !== null}
          onClick={async () => {
            setBusy(r);
            try {
              await onPick(r);
              setLast(r);
            } finally {
              setBusy(null);
            }
          }}
          className={`rounded-lg px-3 py-1 text-sm font-medium ring-1 transition ${last === r ? active[r] : styles[r]}`}
        >
          {busy === r ? <Spinner className="h-3 w-3" /> : RESULT_LABEL[r]}
        </button>
      ))}
    </div>
  );
}

/** Small data-loading hook: returns data, error, loading, and a reload function. */
export function useLoad<T>(fn: () => Promise<T>, deps: unknown[]) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const load = useCallback(fn, deps);
  const reload = useCallback(async () => {
    setLoading(true);
    try {
      setData(await load());
      setError(null);
    } catch (e) {
      setError(e);
    } finally {
      setLoading(false);
    }
  }, [load]);
  useEffect(() => {
    reload();
  }, [reload]);
  return { data, error, loading, reload, setData };
}

export function pct(v: number | null | undefined) {
  return v === null || v === undefined ? "–" : `${Math.round(v * 100)} %`;
}
