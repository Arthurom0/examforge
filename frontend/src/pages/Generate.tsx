import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, Difficulty, Lang, ProblemType, TopicStat } from "../api";
import { Button, Card, Empty, ErrorBox, Field, inputCls, pct, useLoad } from "../components/ui";
import { useSelectedCourse } from "./Library";

const TYPES: [ProblemType, string][] = [
  ["mcq", "Multiple choice"],
  ["numerical", "Numerical calculation"],
  ["derivation", "Derivation"],
  ["conceptual", "Conceptual short answer"],
];

export default function Generate() {
  const courses = useLoad(api.courses, []);
  const { course, select } = useSelectedCourse(courses.data);
  const [chapterId, setChapterId] = useState<number | null>(null);
  const [difficulty, setDifficulty] = useState<Difficulty>("medium");
  const [types, setTypes] = useState<ProblemType[]>(["numerical"]);
  const [language, setLanguage] = useState<Lang>("fr");
  const [count, setCount] = useState(3);
  const [weak, setWeak] = useState(false);
  const [focus, setFocus] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<unknown>(null);
  const [weakTopics, setWeakTopics] = useState<TopicStat[] | null>(null);
  const navigate = useNavigate();

  useEffect(() => setChapterId(null), [course?.id]);
  useEffect(() => {
    if (!course) return;
    api.weakTopics(course.id, chapterId).then(setWeakTopics).catch(() => setWeakTopics(null));
  }, [course, chapterId]);

  const submit = async () => {
    if (!course) return;
    setBusy(true);
    setErr(null);
    try {
      const set = await api.generate({
        course_id: course.id,
        chapter_id: chapterId,
        difficulty,
        types,
        language,
        count,
        weak_spot: weak,
        focus: focus.trim() || undefined,
      });
      navigate(`/sets/${set.id}`);
    } catch (e) {
      setErr(e);
    } finally {
      setBusy(false);
    }
  };

  if (courses.data && !courses.data.length) return <Empty>Create a course and upload material in the Library first.</Empty>;

  return (
    <div className="mx-auto max-w-2xl space-y-5">
      <h1 className="text-2xl font-semibold">Generate practice problems</h1>
      <Card className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Course">
            <select className={inputCls} value={course?.id ?? ""} onChange={(e) => select(Number(e.target.value))}>
              {courses.data?.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Chapter">
            <select className={inputCls} value={chapterId ?? ""} onChange={(e) => setChapterId(e.target.value ? Number(e.target.value) : null)}>
              <option value="">Whole course</option>
              {course?.chapters.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </Field>
        </div>

        <Field label="Difficulty">
          <div className="flex gap-2">
            {(
              [
                ["easy", "Easy"],
                ["medium", "Medium"],
                ["exam", "Exam-level"],
              ] as [Difficulty, string][]
            ).map(([d, label]) => (
              <button
                key={d}
                onClick={() => setDifficulty(d)}
                className={`flex-1 rounded-lg px-3 py-2 text-sm ring-1 ${
                  difficulty === d ? "bg-indigo-600 text-white ring-indigo-600" : "ring-slate-300 hover:bg-slate-50 dark:ring-slate-700 dark:hover:bg-slate-800"
                }`}
              >
                {label}
              </button>
            ))}
          </div>
        </Field>

        <Field label="Problem types" hint="Pick one or more; problems are spread across them.">
          <div className="grid grid-cols-2 gap-2">
            {TYPES.map(([t, label]) => (
              <label
                key={t}
                className={`flex cursor-pointer items-center gap-2 rounded-lg px-3 py-2 text-sm ring-1 ${
                  types.includes(t) ? "bg-indigo-50 ring-indigo-400 dark:bg-indigo-950 dark:ring-indigo-700" : "ring-slate-300 dark:ring-slate-700"
                }`}
              >
                <input
                  type="checkbox"
                  checked={types.includes(t)}
                  onChange={(e) => setTypes((ts) => (e.target.checked ? [...ts, t] : ts.filter((x) => x !== t)))}
                />
                {label}
              </label>
            ))}
          </div>
        </Field>

        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Language">
            <select className={inputCls} value={language} onChange={(e) => setLanguage(e.target.value as Lang)}>
              <option value="fr">Français</option>
              <option value="en">English</option>
            </select>
          </Field>
          <Field label="Number of problems">
            <input type="number" min={1} max={10} className={inputCls} value={count} onChange={(e) => setCount(Math.max(1, Math.min(10, Number(e.target.value))))} />
          </Field>
        </div>

        <Field label="Extra focus (optional)">
          <input className={inputCls} placeholder="e.g. tube de Pitot, écoulement compressible…" value={focus} onChange={(e) => setFocus(e.target.value)} />
        </Field>

        <label className="flex items-start gap-3 rounded-lg bg-slate-50 p-3 text-sm dark:bg-slate-950">
          <input type="checkbox" className="mt-1" checked={weak} onChange={(e) => setWeak(e.target.checked)} />
          <span>
            <span className="font-medium">Weak-spot mode</span>
            <span className="block text-slate-500">
              Target the topics where your success rate is lowest
              {weakTopics?.length ? (
                <>
                  : {weakTopics.slice(0, 3).map((t) => `${t.topic} (${pct(t.success_rate)}, ${t.attempts} tries)`).join(", ")}
                </>
              ) : (
                ". No attempts recorded yet for this scope, so it behaves like normal mode."
              )}
            </span>
          </span>
        </label>

        <ErrorBox error={err} />
        <Button variant="primary" className="w-full py-2.5" disabled={!types.length || !course} loading={busy} onClick={submit}>
          {busy ? "Writing and self-checking the problems…" : `Generate ${count} problem${count > 1 ? "s" : ""}`}
        </Button>
        {busy && <p className="text-center text-xs text-slate-500">This usually takes 30 s to 2 min, longer for exam-level sets.</p>}
      </Card>
    </div>
  );
}
