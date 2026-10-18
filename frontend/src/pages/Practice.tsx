import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../api";
import { ProblemStatement, SolutionReveal } from "../components/ProblemView";
import Markdown from "../components/Markdown";
import { Button, Card, ErrorBox, ResultButtons, Spinner, useLoad } from "../components/ui";

export default function Practice() {
  const id = Number(useParams().id);
  const set = useLoad(() => api.set(id), [id]);
  const navigate = useNavigate();

  if (set.loading && !set.data) return <Spinner />;
  if (set.error || !set.data) return <ErrorBox error={set.error} />;
  const s = set.data;
  const done = s.problems?.filter((p) => p.last_result).length ?? 0;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <Link to="/sets" className="text-sm text-slate-500 hover:underline">
            ← Problem sets
          </Link>
          <h1 className="text-2xl font-semibold">{s.title}</h1>
          <p className="text-sm text-slate-500">
            {s.course_name}
            {s.chapter_name && ` · ${s.chapter_name}`} · {done}/{s.problems?.length} attempted
          </p>
        </div>
        <div className="flex gap-2">
          <Link to={`/sets/${s.id}/print`} target="_blank">
            <Button>Export PDF</Button>
          </Link>
          <Button
            variant="danger"
            onClick={async () => {
              if (confirm("Delete this problem set and its attempts?")) {
                await api.deleteSet(s.id);
                navigate("/sets");
              }
            }}
          >
            Delete
          </Button>
        </div>
      </div>

      {s.source_exercise && (
        <Card className="border-indigo-200 bg-indigo-50/40 dark:border-indigo-900 dark:bg-indigo-950/30">
          <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-indigo-700 dark:text-indigo-300">
            Variants of booklet {s.source_exercise.label}
          </div>
          <Markdown breaks className="text-sm">
            {s.source_exercise.statement}
          </Markdown>
        </Card>
      )}

      {s.problems?.map((p, i) => (
        <Card key={p.id} className="space-y-4">
          <ProblemStatement p={p} index={i} />
          <SolutionReveal p={p} />
          <div className="border-t border-slate-100 pt-3 dark:border-slate-800">
            <ResultButtons current={p.last_result} onPick={(r) => api.attempt({ problem_id: p.id, result: r })} />
          </div>
        </Card>
      ))}

      <div className="flex justify-center gap-2 pt-2">
        <Link to="/generate">
          <Button variant="primary">Generate another set</Button>
        </Link>
        <Link to="/dashboard">
          <Button>See my progress</Button>
        </Link>
      </div>
    </div>
  );
}
