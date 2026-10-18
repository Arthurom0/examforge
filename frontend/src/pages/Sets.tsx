import { Link } from "react-router-dom";
import { api } from "../api";
import { Badge, Button, Card, Empty, Spinner, useLoad } from "../components/ui";

const MODE: Record<string, { label: string; color: "slate" | "indigo" | "amber" }> = {
  standard: { label: "Standard", color: "slate" },
  weak_spot: { label: "Weak spots", color: "amber" },
  variant: { label: "Booklet variants", color: "indigo" },
};

export default function Sets() {
  const sets = useLoad(() => api.sets(), []);
  const courses = useLoad(api.courses, []);
  const name = (id: number) => courses.data?.find((c) => c.id === id)?.name ?? "";

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Problem sets</h1>
        <Link to="/generate">
          <Button variant="primary">New set</Button>
        </Link>
      </div>
      {sets.loading && !sets.data ? (
        <Spinner />
      ) : !sets.data?.length ? (
        <Empty>No problem sets yet.</Empty>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2">
          {sets.data.map((s) => (
            <Link key={s.id} to={`/sets/${s.id}`}>
              <Card className="h-full transition hover:border-indigo-300 dark:hover:border-indigo-700">
                <div className="mb-1 flex items-center gap-2">
                  <Badge color={MODE[s.mode].color}>{MODE[s.mode].label}</Badge>
                  <span className="text-xs text-slate-500">{new Date(s.created_at).toLocaleString()}</span>
                </div>
                <div className="font-medium">{s.title}</div>
                <div className="text-sm text-slate-500">
                  {name(s.course_id)} · {s.attempted}/{s.problem_count} attempted
                </div>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
