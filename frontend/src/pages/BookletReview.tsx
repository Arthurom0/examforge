import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, Exercise } from "../api";
import Markdown from "../components/Markdown";
import { Badge, Button, Card, ErrorBox, Field, inputCls, Spinner, useLoad } from "../components/ui";

/** Prefixes given data with a heading unless the text already starts with one ("Données :", "Data:"). */
export function givenText(given: string) {
  return /^\s*(donn|data|given|on donne|valeurs)/i.test(given) ? given : `**Données :** ${given}`;
}

export function CorrectionBadge({ source }: { source: Exercise["correction_source"] }) {
  if (source === "booklet") return <Badge color="green">Correction in booklet</Badge>;
  if (source === "ai") return <Badge color="amber">AI-generated, unverified</Badge>;
  return <Badge>No correction</Badge>;
}

export default function BookletReview() {
  const docId = Number(useParams().docId);
  const doc = useLoad(() => api.document(docId), [docId]);
  const courses = useLoad(api.courses, []);
  const exs = useLoad(() => api.exercises({ document_id: docId }), [docId]);
  const [selected, setSelected] = useState<number | null>(null);
  const [err, setErr] = useState<unknown>(null);
  const [tagging, setTagging] = useState(false);

  useEffect(() => {
    if (exs.data && (selected === null || !exs.data.some((e) => e.id === selected))) setSelected(exs.data[0]?.id ?? null);
  }, [exs.data, selected]);

  const course = courses.data?.find((c) => c.id === doc.data?.course_id);
  const current = exs.data?.find((e) => e.id === selected) ?? null;
  const reviewed = exs.data?.filter((e) => e.reviewed).length ?? 0;

  const autoTag = async () => {
    setTagging(true);
    setErr(null);
    try {
      await api.tagExercises({ document_id: docId });
      await exs.reload();
    } catch (e) {
      setErr(e);
    } finally {
      setTagging(false);
    }
  };

  if (doc.loading && !doc.data) return <Spinner />;
  if (doc.error) return <ErrorBox error={doc.error} />;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <Link to={`/?course=${doc.data?.course_id}`} className="text-sm text-slate-500 hover:underline">
            ← {course?.name ?? "Library"}
          </Link>
          <h1 className="text-2xl font-semibold">{doc.data?.filename}</h1>
          <p className="text-sm text-slate-500">
            {exs.data?.length ?? 0} exercises detected · {reviewed} reviewed
            {doc.data?.ocr_used && " · scanned (OCR): use “Re-transcribe” to fix equations"}
          </p>
        </div>
        <div className="flex gap-2">
          <Button onClick={autoTag} loading={tagging} title="Ask the AI to tag untagged exercises with topics">
            Auto-tag topics
          </Button>
          <Link to={`/exercises?course=${doc.data?.course_id}`}>
            <Button variant="primary">Practice these</Button>
          </Link>
        </div>
      </div>
      <ErrorBox error={err} />

      <div className="grid gap-4 lg:grid-cols-[280px_1fr]">
        <div className="max-h-[75vh] space-y-1 overflow-y-auto pr-1">
          {exs.data?.map((e) => (
            <button
              key={e.id}
              onClick={() => setSelected(e.id)}
              className={`block w-full rounded-lg border px-3 py-2 text-left text-sm ${
                e.id === selected
                  ? "border-indigo-400 bg-indigo-50 dark:border-indigo-700 dark:bg-indigo-950"
                  : "border-transparent hover:bg-slate-100 dark:hover:bg-slate-900"
              }`}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="truncate font-medium">{e.label}</span>
                {e.reviewed && <span className="text-emerald-600">✓</span>}
              </div>
              <div className="mt-0.5 flex items-center gap-2 text-xs text-slate-500">
                p. {e.page_start}
                {e.page_end !== e.page_start && `–${e.page_end}`}
                {e.sub_questions.length > 0 && ` · ${e.sub_questions.length} questions`}
                {e.correction_source !== "none" && <span>· {e.correction_source === "ai" ? "AI corr." : "corr."}</span>}
              </div>
            </button>
          ))}
        </div>
        {current && course ? (
          <ExerciseEditor
            key={current.id}
            ex={current}
            chapters={course.chapters}
            isLast={current.id === exs.data?.[exs.data.length - 1]?.id}
            onChanged={async (selectId) => {
              await Promise.all([exs.reload(), courses.reload()]);
              if (selectId) setSelected(selectId);
            }}
          />
        ) : (
          <Card className="flex items-center justify-between gap-3">
            <span>No exercises detected in this document.</span>
            <Button
              onClick={async () => {
                const ex = await api.createExercise(docId, -1);
                await exs.reload();
                setSelected(ex.id);
              }}
            >
              Add an exercise manually
            </Button>
          </Card>
        )}
      </div>
    </div>
  );
}

function ExerciseEditor({
  ex,
  chapters,
  isLast,
  onChanged,
}: {
  ex: Exercise;
  chapters: { id: number; name: string }[];
  isLast: boolean;
  onChanged: (selectId?: number) => Promise<void>;
}) {
  const [draft, setDraft] = useState<Exercise>(ex);
  const [tags, setTags] = useState(ex.topic_tags.join(", "));
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<unknown>(null);
  const [showPage, setShowPage] = useState(false);
  const [tab, setTab] = useState<"fields" | "raw">("fields");
  const raw = useRef<HTMLTextAreaElement>(null);
  const dirty = JSON.stringify({ ...draft, topic_tags: tags }) !== JSON.stringify({ ...ex, topic_tags: ex.topic_tags.join(", ") });

  const act = async (name: string, fn: () => Promise<unknown>, selectId?: (r: unknown) => number | undefined) => {
    setBusy(name);
    setErr(null);
    try {
      const r = await fn();
      await onChanged(selectId?.(r));
    } catch (e) {
      setErr(e);
    } finally {
      setBusy(null);
    }
  };

  const save = (extra: Partial<Exercise> = {}) =>
    act("save", () =>
      api.updateExercise(ex.id, {
        label: draft.label,
        chapter_id: draft.chapter_id,
        statement: draft.statement,
        given_data: draft.given_data,
        sub_questions: draft.sub_questions.filter((q) => q.text.trim()),
        correction: draft.correction ?? "",
        topic_tags: tags.split(",").map((t) => t.trim()).filter(Boolean),
        ...extra,
      }),
    );

  const set = <K extends keyof Exercise>(k: K, v: Exercise[K]) => setDraft((d) => ({ ...d, [k]: v }));

  return (
    <Card className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <input className={`${inputCls} !max-w-xs font-semibold`} value={draft.label} onChange={(e) => set("label", e.target.value)} />
        <CorrectionBadge source={draft.correction_source} />
        <div className="ml-auto flex flex-wrap gap-1">
          <Button variant="ghost" onClick={() => setShowPage((s) => !s)}>
            {showPage ? "Hide page" : "Show page"}
          </Button>
          <Button
            variant="ghost"
            loading={busy === "transcribe"}
            onClick={() => act("transcribe", () => api.transcribeExercise(ex.id))}
            title="The AI reads the page images and rewrites the exercise with proper LaTeX (needs a provider with vision)"
          >
            Re-transcribe from page images
          </Button>
          <Button variant="ghost" disabled={isLast} loading={busy === "merge"} onClick={() => act("merge", () => api.mergeNext(ex.id))}>
            Merge with next
          </Button>
          <Button
            variant="ghost"
            loading={busy === "add"}
            onClick={() => act("add", () => api.createExercise(ex.document_id, ex.position), (r) => (r as Exercise).id)}
          >
            Add after
          </Button>
          <Button variant="danger" onClick={() => confirm("Delete this exercise?") && act("delete", () => api.deleteExercise(ex.id))}>
            Delete
          </Button>
        </div>
      </div>

      {showPage && (
        <div className="flex gap-2 overflow-x-auto rounded-lg bg-slate-100 p-2 dark:bg-slate-800">
          {Array.from({ length: ex.page_end - ex.page_start + 1 }, (_, i) => ex.page_start + i).map((p) => (
            <img key={p} src={api.pageImageUrl(ex.document_id, p)} alt={`page ${p}`} className="max-h-[70vh] rounded bg-white shadow" />
          ))}
        </div>
      )}

      <div className="flex gap-1 border-b border-slate-200 text-sm dark:border-slate-800">
        {(["fields", "raw"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`-mb-px border-b-2 px-3 py-1.5 ${tab === t ? "border-indigo-500 font-medium" : "border-transparent text-slate-500"}`}
          >
            {t === "fields" ? "Fields" : "Raw text (split here)"}
          </button>
        ))}
      </div>

      {tab === "raw" ? (
        <div className="space-y-2">
          <p className="text-xs text-slate-500">
            This is the text block the parser assigned to this exercise. If two exercises were merged, put the cursor where the
            second one starts and click “Split at cursor”. Editing and re-parsing rebuilds the fields.
          </p>
          <textarea ref={raw} className={`${inputCls} h-80 font-mono text-xs`} value={draft.raw_text} onChange={(e) => set("raw_text", e.target.value)} />
          <div className="flex gap-2">
            <Button
              loading={busy === "split"}
              onClick={() => {
                const pos = raw.current?.selectionStart ?? 0;
                act("split", () => api.splitExercise(ex.id, pos), (r) => (r as { ids: number[] }).ids[1]);
              }}
            >
              Split at cursor
            </Button>
            <Button loading={busy === "reparse"} onClick={() => act("reparse", () => api.updateExercise(ex.id, { raw_text: draft.raw_text }))}>
              Re-parse fields from raw text
            </Button>
          </div>
        </div>
      ) : (
        <div className="grid gap-4 xl:grid-cols-2">
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <Field label="Chapter">
                <select
                  className={inputCls}
                  value={draft.chapter_id ?? ""}
                  onChange={(e) => set("chapter_id", e.target.value ? Number(e.target.value) : null)}
                >
                  <option value="">No chapter</option>
                  {chapters.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Topics (comma separated)">
                <input className={inputCls} value={tags} onChange={(e) => setTags(e.target.value)} placeholder="bernoulli, venturi" />
              </Field>
            </div>
            <Field label="Statement">
              <textarea className={`${inputCls} h-40`} value={draft.statement} onChange={(e) => set("statement", e.target.value)} />
            </Field>
            <Field label="Given data">
              <textarea className={`${inputCls} h-16`} value={draft.given_data} onChange={(e) => set("given_data", e.target.value)} />
            </Field>
            <div>
              <span className="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-500">Sub-questions</span>
              <div className="space-y-2">
                {draft.sub_questions.map((q, i) => (
                  <div key={i} className="flex gap-2">
                    <input
                      className={`${inputCls} !w-14`}
                      value={q.label}
                      onChange={(e) => set("sub_questions", draft.sub_questions.map((x, j) => (j === i ? { ...x, label: e.target.value } : x)))}
                    />
                    <textarea
                      className={`${inputCls} h-14`}
                      value={q.text}
                      onChange={(e) => set("sub_questions", draft.sub_questions.map((x, j) => (j === i ? { ...x, text: e.target.value } : x)))}
                    />
                    <Button variant="danger" onClick={() => set("sub_questions", draft.sub_questions.filter((_, j) => j !== i))}>
                      ×
                    </Button>
                  </div>
                ))}
                <Button
                  variant="ghost"
                  onClick={() =>
                    set("sub_questions", [...draft.sub_questions, { label: String.fromCharCode(97 + draft.sub_questions.length), text: "" }])
                  }
                >
                  + Add sub-question
                </Button>
              </div>
            </div>
            <Field label="Correction" hint={draft.correction_source === "ai" ? "AI-generated: check it before trusting it." : undefined}>
              <textarea className={`${inputCls} h-32`} value={draft.correction ?? ""} onChange={(e) => set("correction", e.target.value)} />
            </Field>
          </div>
          <div className="space-y-3">
            <span className="block text-xs font-semibold uppercase tracking-wide text-slate-500">Preview</span>
            <div className="rounded-lg bg-slate-50 p-4 dark:bg-slate-950">
              <Markdown breaks>{draft.statement}</Markdown>
              {draft.given_data && !draft.statement.includes(draft.given_data) && (
                <div className="mt-2 text-sm">
                  <Markdown breaks>{givenText(draft.given_data)}</Markdown>
                </div>
              )}
              {draft.sub_questions.map((q, i) => (
                <div key={i} className="mt-2 flex items-baseline gap-2">
                  <span className="font-semibold">{q.label})</span>
                  <Markdown compact breaks>{q.text}</Markdown>
                </div>
              ))}
            </div>
            {draft.correction && (
              <div className="rounded-lg border border-slate-200 p-4 dark:border-slate-800">
                <Markdown breaks>{draft.correction}</Markdown>
              </div>
            )}
          </div>
        </div>
      )}

      <ErrorBox error={err} />
      <div className="flex items-center gap-2 border-t border-slate-100 pt-3 dark:border-slate-800">
        <Button variant="primary" disabled={!dirty} loading={busy === "save"} onClick={() => save()}>
          Save
        </Button>
        <Button loading={busy === "reviewed"} onClick={() => act("reviewed", () => api.updateExercise(ex.id, { reviewed: !ex.reviewed }))}>
          {ex.reviewed ? "Mark as not reviewed" : "Mark as reviewed ✓"}
        </Button>
        {dirty && <span className="text-xs text-amber-600">Unsaved changes</span>}
      </div>
    </Card>
  );
}
