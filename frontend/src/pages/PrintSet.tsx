import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, desktop } from "../api";
import { DIFF_LABEL, ProblemStatement, Solution } from "../components/ProblemView";
import { ErrorBox, Spinner, useLoad } from "../components/ui";

type Mode = "appendix" | "inline" | "none";

/** Print-optimized view of a problem set. "Export PDF" = the browser's Save as PDF, which keeps KaTeX crisp. */
export default function PrintSet() {
  const id = Number(useParams().id);
  const set = useLoad(() => api.set(id), [id]);
  const [mode, setMode] = useState<Mode>("appendix");
  const [savedTo, setSavedTo] = useState<string | null>(null);
  const bridge = desktop();

  // Printing always uses the light theme.
  useEffect(() => {
    const root = document.documentElement;
    const wasDark = root.classList.contains("dark");
    root.classList.remove("dark");
    return () => {
      if (wasDark) root.classList.add("dark");
    };
  }, []);

  useEffect(() => {
    if (set.data) document.title = `ExamForge - ${set.data.title}`;
  }, [set.data]);

  if (set.loading && !set.data) return <Spinner />;
  if (!set.data) return <ErrorBox error={set.error} />;
  const s = set.data;
  const problems = s.problems ?? [];
  const fr = problems[0]?.language !== "en";

  return (
    <div className="min-h-screen bg-white text-slate-900">
      <div className="no-print sticky top-0 z-10 flex flex-wrap items-center gap-3 border-b bg-slate-50 px-6 py-3 text-sm">
        <Link to={`/sets/${s.id}`} className="text-slate-500 hover:underline">
          ← Back
        </Link>
        <span className="font-medium">Solutions:</span>
        {(
          [
            ["appendix", "at the end"],
            ["inline", "after each problem"],
            ["none", "not included"],
          ] as [Mode, string][]
        ).map(([m, label]) => (
          <label key={m} className="flex items-center gap-1">
            <input type="radio" checked={mode === m} onChange={() => setMode(m)} /> {label}
          </label>
        ))}
        {savedTo && <span className="ml-auto text-xs text-emerald-700">Saved to {savedTo}</span>}
        {bridge ? (
          <button
            onClick={async () => {
              const r = await bridge.savePDF(`${s.title.replace(/[\\/:*?"<>|]+/g, "-")}.pdf`);
              if (r.saved && r.path) setSavedTo(r.path);
            }}
            className={`${savedTo ? "" : "ml-auto"} rounded-lg bg-indigo-600 px-4 py-1.5 font-medium text-white hover:bg-indigo-500`}
          >
            Save as PDF…
          </button>
        ) : (
          <button onClick={() => window.print()} className="ml-auto rounded-lg bg-indigo-600 px-4 py-1.5 font-medium text-white hover:bg-indigo-500">
            Print / Save as PDF
          </button>
        )}
        {bridge && (
          <button onClick={() => window.print()} className="rounded-lg px-3 py-1.5 font-medium text-slate-600 hover:bg-slate-200">
            Print…
          </button>
        )}
      </div>

      <article className="mx-auto max-w-[800px] px-10 py-10 print:px-0 print:py-0">
        <header className="mb-8 border-b pb-4">
          <div className="text-xs uppercase tracking-widest text-slate-500">ExamForge · {s.course_name}</div>
          <h1 className="text-2xl font-semibold">{s.title}</h1>
          <div className="text-sm text-slate-500">
            {s.chapter_name && `${s.chapter_name} · `}
            {problems.length} {fr ? "exercices" : "problems"} · {new Date(s.created_at).toLocaleDateString()}
            {problems[0] && ` · ${DIFF_LABEL[problems[0].difficulty]}`}
          </div>
        </header>

        {problems.map((p, i) => (
          <section key={p.id} className="avoid-break mb-8">
            <ProblemStatement p={p} index={i} />
            {mode === "inline" && (
              <div className="mt-3 border-l-2 border-indigo-200 pl-4">
                <Solution p={p} />
              </div>
            )}
          </section>
        ))}

        {mode === "appendix" && (
          <div className="page-break pt-4">
            <h2 className="mb-6 text-xl font-semibold">{fr ? "Corrigés" : "Solutions"}</h2>
            {problems.map((p, i) => (
              <section key={p.id} className="mb-8">
                <h3 className="mb-2 font-semibold">
                  {i + 1}. {p.title}
                </h3>
                <Solution p={p} />
              </section>
            ))}
          </div>
        )}
      </article>
    </div>
  );
}
