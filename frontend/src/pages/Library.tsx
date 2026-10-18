import { DragEvent, useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api, Course, Doc, Kind } from "../api";
import { Badge, Button, Card, Empty, ErrorBox, Field, inputCls, Spinner, useLoad } from "../components/ui";

const KIND_LABEL: Record<Kind, string> = {
  lecture: "Lecture material",
  exam: "Past exam",
  booklet: "Tutorial booklet",
};

export function useSelectedCourse(courses: Course[] | null) {
  const [params, setParams] = useSearchParams();
  const id = Number(params.get("course")) || courses?.[0]?.id || null;
  const course = courses?.find((c) => c.id === id) ?? courses?.[0] ?? null;
  const select = (cid: number) => {
    const p = new URLSearchParams(params);
    p.set("course", String(cid));
    p.delete("chapter");
    setParams(p);
  };
  return { course, select, params, setParams };
}

export default function Library() {
  const courses = useLoad(api.courses, []);
  const { course, select } = useSelectedCourse(courses.data);
  const [newCourse, setNewCourse] = useState("");
  const [err, setErr] = useState<unknown>(null);

  const addCourse = async () => {
    if (!newCourse.trim()) return;
    try {
      const c = await api.createCourse(newCourse);
      setNewCourse("");
      await courses.reload();
      select(c.id);
    } catch (e) {
      setErr(e);
    }
  };

  return (
    <div className="grid gap-6 md:grid-cols-[240px_1fr]">
      <aside className="space-y-3">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Courses</h2>
        <div className="space-y-1">
          {courses.data?.map((c) => (
            <button
              key={c.id}
              onClick={() => select(c.id)}
              className={`block w-full rounded-lg px-3 py-2 text-left text-sm ${
                course?.id === c.id
                  ? "bg-indigo-50 font-medium text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300"
                  : "hover:bg-slate-100 dark:hover:bg-slate-900"
              }`}
            >
              {c.name}
              <span className="block text-xs text-slate-500">
                {c.documents} docs · {c.exercises} exercises
              </span>
            </button>
          ))}
        </div>
        <form
          className="flex gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            addCourse();
          }}
        >
          <input className={inputCls} placeholder="New course…" value={newCourse} onChange={(e) => setNewCourse(e.target.value)} />
          <Button type="submit" variant="primary">
            Add
          </Button>
        </form>
        <ErrorBox error={err} />
      </aside>

      <section>
        {courses.loading && !courses.data ? (
          <Spinner />
        ) : !course ? (
          <Empty>Create your first course on the left, e.g. "Mécanique des fluides".</Empty>
        ) : (
          <CoursePanel key={course.id} course={course} onChange={courses.reload} />
        )}
      </section>
    </div>
  );
}

function CoursePanel({ course, onChange }: { course: Course; onChange: () => Promise<void> }) {
  const docs = useLoad(() => api.documents(course.id), [course.id]);
  const [chapterName, setChapterName] = useState("");
  const [editing, setEditing] = useState<number | null>(null);
  const [editName, setEditName] = useState("");
  const [err, setErr] = useState<unknown>(null);

  // Poll while documents are being processed.
  const pending = docs.data?.some((d) => d.status === "pending");
  const reloadDocs = docs.reload;
  useEffect(() => {
    if (!pending) return;
    const t = setInterval(() => {
      reloadDocs();
      onChange();
    }, 1500);
    return () => clearInterval(t);
  }, [pending, reloadDocs, onChange]);

  const run = async (fn: () => Promise<unknown>) => {
    try {
      setErr(null);
      await fn();
      await Promise.all([docs.reload(), onChange()]);
    } catch (e) {
      setErr(e);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">{course.name}</h1>
        <div className="flex gap-2">
          <Link to={`/generate?course=${course.id}`}>
            <Button variant="primary">Generate problems</Button>
          </Link>
          <Button
            variant="danger"
            onClick={() => {
              if (confirm(`Delete "${course.name}" with all its documents, problems and attempts?`))
                run(() => api.deleteCourse(course.id));
            }}
          >
            Delete course
          </Button>
        </div>
      </div>
      <ErrorBox error={err} />

      <Card>
        <h2 className="mb-3 font-semibold">Chapters</h2>
        {course.chapters.length === 0 && (
          <p className="mb-3 text-sm text-slate-500">
            No chapters yet. Add them here, or upload a booklet with "Chapitre N" headings and they will be detected.
          </p>
        )}
        <ol className="mb-3 divide-y divide-slate-100 dark:divide-slate-800">
          {course.chapters.map((ch, i) => (
            <li key={ch.id} className="flex items-center gap-3 py-2 text-sm">
              <span className="w-6 text-slate-400">{i + 1}.</span>
              {editing === ch.id ? (
                <form
                  className="flex flex-1 gap-2"
                  onSubmit={(e) => {
                    e.preventDefault();
                    run(() => api.updateChapter(ch.id, editName)).then(() => setEditing(null));
                  }}
                >
                  <input className={inputCls} value={editName} onChange={(e) => setEditName(e.target.value)} autoFocus />
                  <Button type="submit">Save</Button>
                </form>
              ) : (
                <>
                  <span className="flex-1">{ch.name}</span>
                  <span className="text-xs text-slate-500">
                    {ch.documents} docs · {ch.exercises} ex.
                  </span>
                  <Button
                    variant="ghost"
                    onClick={() => {
                      setEditing(ch.id);
                      setEditName(ch.name);
                    }}
                  >
                    Rename
                  </Button>
                  <Button
                    variant="danger"
                    onClick={() => confirm(`Delete chapter "${ch.name}"? Its documents stay in the course.`) && run(() => api.deleteChapter(ch.id))}
                  >
                    Delete
                  </Button>
                </>
              )}
            </li>
          ))}
        </ol>
        <form
          className="flex gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            if (chapterName.trim()) run(() => api.createChapter(course.id, chapterName)).then(() => setChapterName(""));
          }}
        >
          <input className={inputCls} placeholder="New chapter, e.g. Statique des fluides" value={chapterName} onChange={(e) => setChapterName(e.target.value)} />
          <Button type="submit">Add chapter</Button>
        </form>
      </Card>

      <UploadCard course={course} onUploaded={() => Promise.all([docs.reload(), onChange()]).then(() => undefined)} />

      <Card>
        <h2 className="mb-3 font-semibold">Documents</h2>
        {!docs.data?.length ? (
          <p className="text-sm text-slate-500">No documents yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-left text-xs uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="py-2 pr-3">File</th>
                  <th className="pr-3">Type</th>
                  <th className="pr-3">Chapter</th>
                  <th className="pr-3">Status</th>
                  <th />
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {docs.data.map((d) => (
                  <DocRow key={d.id} doc={d} course={course} run={run} />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}

function DocRow({ doc, course, run }: { doc: Doc; course: Course; run: (fn: () => Promise<unknown>) => Promise<void> }) {
  return (
    <tr className="align-top">
      <td className="py-2 pr-3">
        <a href={api.fileUrl(doc.id)} target="_blank" rel="noreferrer" className="font-medium hover:underline">
          {doc.filename}
        </a>
        <div className="text-xs text-slate-500">
          {doc.page_count} pages · {Math.round(doc.char_count / 1000)}k chars
        </div>
      </td>
      <td className="pr-3">
        <Badge color={doc.kind === "booklet" ? "indigo" : "slate"}>{KIND_LABEL[doc.kind]}</Badge>
      </td>
      <td className="pr-3">
        <select
          className={`${inputCls} !w-44 py-1`}
          value={doc.chapter_id ?? ""}
          onChange={(e) => run(() => api.updateDocument(doc.id, { chapter_id: e.target.value ? Number(e.target.value) : null }))}
        >
          <option value="">{doc.kind === "booklet" ? "Per exercise / none" : "No chapter"}</option>
          {course.chapters.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
      </td>
      <td className="pr-3">
        {doc.status === "pending" && (
          <span className="inline-flex items-center gap-2 text-slate-500">
            <Spinner className="h-3 w-3" /> Extracting…
          </span>
        )}
        {doc.status === "ready" && <Badge color="green">Ready</Badge>}
        {doc.status === "error" && (
          <span title={doc.error ?? ""}>
            <Badge color="red">Error</Badge>
            <div className="mt-1 max-w-xs text-xs text-red-600 dark:text-red-400">{doc.error}</div>
          </span>
        )}
        {doc.ocr_used && (
          <div className="mt-1">
            <Badge color="amber">OCR on {doc.ocr_pages} page(s)</Badge>
          </div>
        )}
      </td>
      <td className="whitespace-nowrap text-right">
        {doc.kind === "booklet" && doc.status === "ready" && (
          <Link to={`/booklets/${doc.id}`}>
            <Button variant="ghost">Review split</Button>
          </Link>
        )}
        <Button
          variant="ghost"
          onClick={() =>
            (doc.kind !== "booklet" ||
              confirm("Re-extracting re-splits the booklet and discards your manual fixes. Past attempts stay in the stats. Continue?")) &&
            run(() => api.reprocess(doc.id))
          }
          title="Re-extract text (and re-split a booklet)"
        >
          Re-extract
        </Button>
        <Button variant="danger" onClick={() => confirm(`Delete ${doc.filename}?`) && run(() => api.deleteDocument(doc.id))}>
          Delete
        </Button>
      </td>
    </tr>
  );
}

function UploadCard({ course, onUploaded }: { course: Course; onUploaded: () => Promise<void> }) {
  const [kind, setKind] = useState<Kind>("lecture");
  const [chapter, setChapter] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<unknown>(null);
  const [drag, setDrag] = useState(false);
  const input = useRef<HTMLInputElement>(null);

  const upload = async (files: FileList | File[]) => {
    setBusy(true);
    setErr(null);
    try {
      for (const f of Array.from(files)) await api.upload(course.id, kind, chapter, f);
      await onUploaded();
    } catch (e) {
      setErr(e);
    } finally {
      setBusy(false);
      if (input.current) input.current.value = "";
    }
  };

  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setDrag(false);
    if (e.dataTransfer.files.length) upload(e.dataTransfer.files);
  };

  return (
    <Card>
      <h2 className="mb-3 font-semibold">Upload PDFs</h2>
      <div className="mb-3 grid gap-3 sm:grid-cols-2">
        <Field label="Type">
          <select className={inputCls} value={kind} onChange={(e) => setKind(e.target.value as Kind)}>
            <option value="lecture">Lecture slides / polycopié</option>
            <option value="exam">Past exam</option>
            <option value="booklet">Tutorial booklet (fascicule de TD)</option>
          </select>
        </Field>
        <Field label="Chapter" hint={kind === "booklet" ? "Leave empty to detect chapters from headings in the booklet." : undefined}>
          <select className={inputCls} value={chapter ?? ""} onChange={(e) => setChapter(e.target.value ? Number(e.target.value) : null)}>
            <option value="">{kind === "booklet" ? "Detect from headings" : "Whole course"}</option>
            {course.chapters.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </Field>
      </div>
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDrag(true);
        }}
        onDragLeave={() => setDrag(false)}
        onDrop={onDrop}
        onClick={() => input.current?.click()}
        className={`flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed p-8 text-sm transition ${
          drag ? "border-indigo-500 bg-indigo-50 dark:bg-indigo-950" : "border-slate-300 hover:border-slate-400 dark:border-slate-700"
        }`}
      >
        {busy ? (
          <span className="flex items-center gap-2">
            <Spinner /> Uploading…
          </span>
        ) : (
          <>
            <span className="font-medium">Drop PDFs here or click to choose</span>
            <span className="text-slate-500">Scanned PDFs are OCR'd automatically (French + English)</span>
          </>
        )}
        <input ref={input} type="file" accept="application/pdf" multiple hidden onChange={(e) => e.target.files && upload(e.target.files)} />
      </div>
      <div className="mt-3">
        <ErrorBox error={err} />
      </div>
    </Card>
  );
}
