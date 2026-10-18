import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, Exercise } from "../api";
import Markdown from "../components/Markdown";
import { Badge, Button, Card, Empty, ErrorBox, inputCls, RESULT_COLOR, RESULT_LABEL, ResultButtons, Spinner, useLoad } from "../components/ui";
import { CorrectionBadge, givenText } from "./BookletReview";
import { useSelectedCourse } from "./Library";

export default function Exercises() {
  const courses = useLoad(api.courses, []);
  const { course, select, params, setParams } = useSelectedCourse(courses.data);
  const chapterId = params.get("chapter") ? Number(params.get("chapter")) : null;
  const exs = useLoad(
    () => (course ? api.exercises({ course_id: course.id, chapter_id: chapterId }) : Promise.resolve([])),
    [course?.id, chapterId],
  );
  const [filter, setFilter] = useState<"all" | "todo" | "wrong" | "nocorr">("all");

  const shown = (exs.data ?? []).filter((e) =>
    filter === "todo" ? !e.attempts : filter === "wrong" ? e.last_result === "wrong" || e.last_result === "partial" : filter === "nocorr" ? e.correction_source === "none" : true,
  );
  const chapterName = (id: number | null) => course?.chapters.find((c) => c.id === id)?.name;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end gap-3">
        <h1 className="mr-auto text-2xl font-semibold">Booklet exercises</h1>
        <select className={`${inputCls} !w-56`} value={course?.id ?? ""} onChange={(e) => select(Number(e.target.value))}>
          {courses.data?.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
        <select
          className={`${inputCls} !w-56`}
          value={chapterId ?? ""}
          onChange={(e) => {
            const p = new URLSearchParams(params);
            if (e.target.value) p.set("chapter", e.target.value);
            else p.delete("chapter");
            setParams(p);
          }}
        >
          <option value="">All chapters</option>
          {course?.chapters.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
        <select className={`${inputCls} !w-48`} value={filter} onChange={(e) => setFilter(e.target.value as typeof filter)}>
          <option value="all">All exercises</option>
          <option value="todo">Not attempted yet</option>
          <option value="wrong">Last attempt wrong/partial</option>
          <option value="nocorr">Without correction</option>
        </select>
      </div>

      {exs.loading && !exs.data ? (
        <Spinner />
      ) : !shown.length ? (
        <Empty>
          No booklet exercises here. Upload a tutorial booklet in the <Link to="/" className="underline">Library</Link>.
        </Empty>
      ) : (
        shown.map((e) => <ExerciseCard key={e.id} ex={e} chapterName={chapterName(e.chapter_id)} onChanged={exs.reload} />)
      )}
    </div>
  );
}

function ExerciseCard({ ex, chapterName, onChanged }: { ex: Exercise; chapterName?: string; onChanged: () => Promise<void> }) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<unknown>(null);
  const [variantForm, setVariantForm] = useState(false);
  const [count, setCount] = useState(3);
  const [kinds, setKinds] = useState<string[]>(["values", "reversed", "twist"]);
  const navigate = useNavigate();

  const run = async (name: string, fn: () => Promise<unknown>) => {
    setBusy(name);
    setErr(null);
    try {
      return await fn();
    } catch (e) {
      setErr(e);
    } finally {
      setBusy(null);
    }
  };

  return (
    <Card className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="font-semibold">{ex.label}</h3>
        {chapterName && <Badge>{chapterName}</Badge>}
        {ex.topic_tags.map((t) => (
          <Badge key={t} color="indigo">
            {t}
          </Badge>
        ))}
        <span className="ml-auto flex items-center gap-2 text-xs text-slate-500">
          {ex.attempts ? `${ex.attempts} attempt(s)` : "never attempted"}
          {ex.last_result && <Badge color={RESULT_COLOR[ex.last_result]}>{RESULT_LABEL[ex.last_result]}</Badge>}
          <Link to={`/booklets/${ex.document_id}`} className="hover:underline">
            edit
          </Link>
        </span>
      </div>
      <Markdown breaks>{ex.statement}</Markdown>
      {ex.given_data && !ex.statement.includes(ex.given_data) && (
        <div className="text-sm">
          <Markdown breaks>{givenText(ex.given_data)}</Markdown>
        </div>
      )}
      {ex.sub_questions.map((q, i) => (
        <div key={i} className="flex items-baseline gap-2">
          <span className="font-semibold">{q.label})</span>
          <Markdown compact breaks>{q.text}</Markdown>
        </div>
      ))}

      {open && ex.correction && (
        <div
          className={`rounded-lg border p-4 ${
            ex.correction_source === "ai" ? "border-amber-300 bg-amber-50/50 dark:border-amber-800 dark:bg-amber-950/30" : "border-slate-200 dark:border-slate-800"
          }`}
        >
          <div className="mb-2">
            <CorrectionBadge source={ex.correction_source} />
          </div>
          <Markdown breaks={ex.correction_source !== "ai"}>{ex.correction}</Markdown>
        </div>
      )}

      {variantForm && (
        <div className="flex flex-wrap items-center gap-3 rounded-lg bg-slate-50 p-3 text-sm dark:bg-slate-950">
          <span>Variants:</span>
          <input type="number" min={1} max={6} className={`${inputCls} !w-16`} value={count} onChange={(e) => setCount(Number(e.target.value))} />
          {[
            ["values", "changed values"],
            ["reversed", "reversed unknowns"],
            ["twist", "added twist"],
          ].map(([k, label]) => (
            <label key={k} className="flex items-center gap-1">
              <input
                type="checkbox"
                checked={kinds.includes(k)}
                onChange={(e) => setKinds((ks) => (e.target.checked ? [...ks, k] : ks.filter((x) => x !== k)))}
              />
              {label}
            </label>
          ))}
          <Button
            variant="primary"
            disabled={!kinds.length}
            loading={busy === "variants"}
            onClick={async () => {
              const set = (await run("variants", () => api.variants(ex.id, count, kinds))) as { id: number } | undefined;
              if (set) navigate(`/sets/${set.id}`);
            }}
          >
            Generate
          </Button>
          {busy === "variants" && <span className="text-xs text-slate-500">Claude is writing and checking the variants…</span>}
        </div>
      )}

      <ErrorBox error={err} />
      <div className="flex flex-wrap items-center gap-2 border-t border-slate-100 pt-3 dark:border-slate-800">
        <ResultButtons
          current={ex.last_result}
          onPick={async (r) => {
            await api.attempt({ exercise_id: ex.id, result: r });
            await onChanged();
          }}
        />
        <div className="ml-auto flex gap-2">
          {ex.correction ? (
            <Button onClick={() => setOpen((o) => !o)}>{open ? "Hide correction" : "Show correction"}</Button>
          ) : null}
          {ex.correction_source !== "booklet" && (
            <Button
              loading={busy === "solve"}
              onClick={() =>
                run("solve", async () => {
                  await api.solveExercise(ex.id);
                  await onChanged();
                  setOpen(true);
                })
              }
              title="Generate a step-by-step solution, labeled AI-generated and unverified"
            >
              {ex.correction_source === "ai" ? "Re-solve with AI" : "Solve with AI"}
            </Button>
          )}
          <Button onClick={() => setVariantForm((v) => !v)}>Variants…</Button>
        </div>
      </div>
    </Card>
  );
}
